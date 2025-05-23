from __future__ import annotations

import argparse
import copy
import logging
import multiprocessing
import sys
import tempfile
from collections.abc import Collection
from pathlib import Path
from typing import Any, Optional

import annofabapi
import numpy
from annofabapi.models import ProjectMemberRole
from annofabapi.pydantic_models.task_status import TaskStatus
from annofabapi.segmentation import read_binary_image, write_binary_image
from annofabapi.utils import can_put_annotation

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


def remove_overlap_of_binary_image_array(binary_image_array_by_annotation: dict[str, numpy.ndarray], annotation_id_list: list[str]) -> dict[str, numpy.ndarray]:
    """
    塗りつぶし画像の重なりを除去したbool配列をdictで返します。

    Args:
        binary_image_array_by_annotation: annotation_idをkeyとし、塗りつぶし画像のbool配列をvalueとするdict
        annotation_id_list: 塗りつぶし画像のannotation_idのlist。背面から前面の順に格納されている

    Returns:
        重なりを除去した塗りつぶし画像のbool配列が格納されているdict。keyはannotation_id

    """
    assert set(binary_image_array_by_annotation.keys()) == set(annotation_id_list)

    whole_2d_array = None  # 複数の塗りつぶしアノテーションを1枚に重ね合わせた状態。各要素はannotation_id

    # 背面から塗りつぶしアノテーションのbool配列を重ねていく
    for annotation_id in annotation_id_list:
        input_binary_image_array = binary_image_array_by_annotation[annotation_id]
        if whole_2d_array is None:
            whole_2d_array = numpy.full(input_binary_image_array.shape, "", dtype=str)

        whole_2d_array = numpy.where(input_binary_image_array, annotation_id, whole_2d_array)

    output_binary_image_array_by_annotation = {}
    for annotation_id in annotation_id_list:
        output_binary_image_array: numpy.ndarray = whole_2d_array == annotation_id  # type: ignore[assignment]
        output_binary_image_array_by_annotation[annotation_id] = output_binary_image_array

    return output_binary_image_array_by_annotation


class RemoveSegmentationOverlapMain(CommandLineWithConfirm):
    def __init__(self, annofab_service: annofabapi.Resource, *, project_id: str, all_yes: bool, is_force: bool) -> None:
        self.annofab_service = annofab_service
        self.project_id = project_id
        self.is_force = is_force
        super().__init__(all_yes)

    def remove_segmentation_overlap_and_save(self, details: list[dict[str, Any]], output_dir: Path) -> list[str]:
        """
        `getEditorAnnotation` APIで取得した`details`から、塗りつぶし画像の重なりの除去が必要な場合に、
        重なりを除去した塗りつぶし画像を`output_dir`に出力します。
        塗りつぶし画像のファイル名は`${annotation_id}.png`です。

        Args:
            details: `getEditorAnnotation` APIで取得した`details`
            output_dir: 塗りつぶし画像の出力先のディレクトリ。

        Returns:
            重なりの除去が必要な塗りつぶし画像のannotation_idのlist
        """
        input_binary_image_array_by_annotation = {}
        segmentation_annotation_id_list = []

        for detail in details:
            if detail["body"]["_type"] != "Outer":
                continue

            segmentation_response = self.annofab_service.wrapper.execute_http_get(detail["body"]["url"], stream=True)
            segmentation_response.raw.decode_content = True
            input_binary_image_array_by_annotation[detail["annotation_id"]] = read_binary_image(segmentation_response.raw)
            segmentation_annotation_id_list.append(detail["annotation_id"])

        # reversedを使っている理由:
        # `details`には、前面から背面の順にアノテーションが格納されているため、
        output_binary_image_array_by_annotation = remove_overlap_of_binary_image_array(input_binary_image_array_by_annotation, list(reversed(segmentation_annotation_id_list)))

        updated_annotation_id_list = []
        for annotation_id, output_binary_image_array in output_binary_image_array_by_annotation.items():
            input_binary_image_array = input_binary_image_array_by_annotation[annotation_id]
            if not numpy.array_equal(input_binary_image_array, output_binary_image_array):
                output_file_path = output_dir / f"{annotation_id}.png"
                write_binary_image(output_binary_image_array, output_file_path)
                updated_annotation_id_list.append(annotation_id)

        return updated_annotation_id_list

    def update_segmentation_annotation(self, task_id: str, input_data_id: str, log_message_prefix: str = "") -> bool:
        """
        塗りつぶしアノテーションの重なりがあれば、`putAnnotation` APIを使用して重なりを除去します。

        Args:
            project_id: プロジェクトID
            task_id: タスクID
            annotation_id_list: 更新する塗りつぶし画像のannotation_idのlist
        """
        old_annotation, _ = self.annofab_service.api.get_editor_annotation(self.project_id, task_id, input_data_id, query_params={"v": "2"})
        old_details = old_annotation["details"]
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            updated_annotation_id_list = self.remove_segmentation_overlap_and_save(old_details, temp_dir_path)
            if len(updated_annotation_id_list) == 0:
                logger.debug(f"{log_message_prefix}塗りつぶしアノテーションの重なりはなかったので、スキップします。 :: task_id='{task_id}', input_data_id='{input_data_id}'")
                return False

            logger.debug(
                f"{log_message_prefix}{len(updated_annotation_id_list)} 件の塗りつぶしアノテーションを更新します。 :: "
                f"task_id='{task_id}', input_data_id='{input_data_id}', annotation_id_list={updated_annotation_id_list}"
            )
            new_details = []
            for detail in old_details:
                annotation_id = detail["annotation_id"]
                new_detail = copy.deepcopy(detail)
                new_detail["_type"] = "Update"
                if annotation_id in updated_annotation_id_list:
                    with (temp_dir_path / f"{annotation_id}.png").open("rb") as f:
                        s3_path = self.annofab_service.wrapper.upload_data_to_s3(self.project_id, data=f, content_type="image/png")

                    new_detail["body"]["path"] = s3_path

                else:
                    # 更新しない場合は、`body`をNoneにする
                    new_detail["body"] = None

                new_details.append(new_detail)

        request_body = {
            "project_id": self.project_id,
            "task_id": task_id,
            "input_data_id": input_data_id,
            "details": new_details,
            "format_version": "2.0.0",
            "updated_datetime": old_annotation["updated_datetime"],
        }
        self.annofab_service.api.put_annotation(self.project_id, task_id, input_data_id, query_params={"v": "2"}, request_body=request_body)
        logger.debug(f"{log_message_prefix}{len(updated_annotation_id_list)} 件の塗りつぶしアノテーションを更新しました。 :: task_id='{task_id}', input_data_id='{input_data_id}'")
        return True

    def update_segmentation_annotation_for_task(self, task_id: str, *, task_index: Optional[int] = None) -> int:
        """
        1個のタスクに対して、塗りつぶしアノテーションの重なりを除去します。

        Returns:
            アノテーションを更新した入力データ数（フレーム数）
        """
        log_message_prefix = f"{task_index + 1} 件目 :: " if task_index is not None else ""

        task = self.annofab_service.wrapper.get_task_or_none(project_id=self.project_id, task_id=task_id)
        if task is None:
            logger.warning(f"{log_message_prefix}task_id='{task_id}'であるタスクは存在しません。")
            return 0

        if task["status"] in {TaskStatus.WORKING.value, TaskStatus.COMPLETE.value}:
            logger.debug(f"{log_message_prefix}task_id='{task_id}'のタスクの状態は「作業中」または「完了」であるため、アノテーションの更新をスキップします。  :: status='{task['status']}'")
            return 0

        if not self.confirm_processing(f"task_id='{task_id}'の塗りつぶしアノテーションの重なりを除去しますか？"):
            return 0

        # 担当者割り当て変更チェック
        changed_operator = False
        original_operator_account_id = task["account_id"]
        if not can_put_annotation(task, self.annofab_service.api.account_id):
            if self.is_force:
                logger.debug(f"{log_message_prefix}task_id='{task_id}' のタスクの担当者を自分自身に変更します。")
                changed_operator = True
                task = self.annofab_service.wrapper.change_task_operator(
                    self.project_id,
                    task_id,
                    self.annofab_service.api.account_id,
                    last_updated_datetime=task["updated_datetime"],
                )
            else:
                logger.debug(
                    f"{log_message_prefix}task_id='{task_id}' のタスクは、過去に誰かに割り当てられたタスクで、"
                    f"現在の担当者が自分自身でないため、アノテーションの更新をスキップします。"
                    f"担当者を自分自身に変更してアノテーションを更新する場合は、コマンドライン引数 '--force' を指定してください。"
                )
                return 0

        success_input_data_count = 0
        for input_data_id in task["input_data_id_list"]:
            try:
                result = self.update_segmentation_annotation(task_id, input_data_id, log_message_prefix=log_message_prefix)
                if result:
                    success_input_data_count += 1
            except Exception:
                logger.warning(f"{log_message_prefix}task_id='{task_id}', input_data_id='{input_data_id}'のアノテーションの更新に失敗しました。", exc_info=True)
                continue

        # 担当者を元に戻す
        if changed_operator:
            logger.debug(f"{log_message_prefix}task_id='{task_id}' のタスクの担当者を、元の担当者（account_id='{original_operator_account_id}'）に変更します。")
            self.annofab_service.wrapper.change_task_operator(
                self.project_id,
                task_id,
                original_operator_account_id,
                last_updated_datetime=task["updated_datetime"],
            )

        return success_input_data_count

    def update_segmentation_annotation_for_task_wrapper(self, tpl: tuple[int, str]) -> int:
        try:
            task_index, task_id = tpl
            return self.update_segmentation_annotation_for_task(task_id, task_index=task_index)
        except Exception:
            logger.warning(f"task_id='{task_id}' のアノテーションの更新に失敗しました。", exc_info=True)
            return 0

    def main(
        self,
        task_ids: Collection[str],
        parallelism: Optional[int] = None,
    ) -> None:
        logger.info(f"{len(task_ids)} 件のタスクの塗りつぶしアノテーションの重なりを除去します。")
        success_input_data_count = 0
        if parallelism is not None:
            with multiprocessing.Pool(parallelism) as pool:
                result_count_list = pool.map(self.update_segmentation_annotation_for_task_wrapper, enumerate(task_ids))
                success_input_data_count = sum(result_count_list)

        else:
            for task_index, task_id in enumerate(task_ids):
                try:
                    result = self.update_segmentation_annotation_for_task(task_id, task_index=task_index)
                    success_input_data_count += result
                except Exception:
                    logger.warning(f"task_id='{task_id}' のアノテーションの更新に失敗しました。", exc_info=True)
                    continue

        logger.info(f"{len(task_ids)} 件のタスクに含まれる入力データ {success_input_data_count} 件の塗りつぶしアノテーションを更新しました。")


class RemoveSegmentationOverlap(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation remove_segmentation_overlap: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、'--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER, ProjectMemberRole.WORKER])

        main_obj = RemoveSegmentationOverlapMain(
            self.service,
            project_id=project_id,
            all_yes=self.all_yes,
            is_force=args.force,
        )

        main_obj.main(task_id_list, parallelism=args.parallelism)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    RemoveSegmentationOverlap(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    argument_parser.add_task_id()

    parser.add_argument(
        "--force",
        action="store_true",
        help="過去に担当者を割り当てられていて、かつ現在の担当者が自分自身でない場合、タスクの担当者を一時的に自分自身に変更してからアノテーションをコピーします。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="並列度。指定しない場合は、逐次的に処理します。指定した場合は、``--yes`` も指定してください。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "remove_segmentation_overlap"
    subcommand_help = "塗りつぶしアノテーションの重なりを除去します。"
    description = "塗りつぶしアノテーションの重なりを除去します。Annofabでインスタンスセグメンテーションは重ねることができてしまいます。この重なりをなくしたいときに有用です。"
    epilog = "オーナー、チェッカーまたはアノテータロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
