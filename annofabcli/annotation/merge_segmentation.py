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
from annofabapi.pydantic_models.default_annotation_type import DefaultAnnotationType
from annofabapi.pydantic_models.task_status import TaskStatus
from annofabapi.segmentation import read_binary_image, write_binary_image
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor
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


def merge_binary_image_array(binary_image_array_list: list[numpy.ndarray]) -> numpy.ndarray:
    """
    塗りつぶし画像を読み込んだboolのndarrayのlistから、1個のndarrayを作成します。

    Args:
        binary_image_array_list: 塗りつぶし画像を読み込んだboolのndarrayのlist
    """
    if len(binary_image_array_list) == 0:
        raise ValueError("'binary_image_array_list' must not be empty.")

    merged_array = numpy.zeros_like(binary_image_array_list[0], dtype=bool)
    for binary_image_array in binary_image_array_list:
        merged_array = numpy.logical_or(merged_array, binary_image_array)
    return merged_array


class MergeSegmentationMain(CommandLineWithConfirm):
    def __init__(
        self,
        annofab_service: annofabapi.Resource,
        *,
        project_id: str,
        label_ids: Collection[str],
        label_names: Collection[str],
        all_yes: bool,
        is_force: bool,
    ) -> None:
        self.annofab_service = annofab_service
        self.project_id = project_id
        self.is_force = is_force
        self.label_ids = label_ids
        self.label_names = label_names

        super().__init__(all_yes)

    def write_merged_segmentation_file(self, details: list[dict[str, Any]], output_dir: Path) -> tuple[list[str], list[str]]:
        """
        `getEditorAnnotation` APIで取得した`details`から、指定したラベルに対応する塗りつぶしアノテーションを1個にまとめて、
        `output_dir`に出力します。
        塗りつぶし画像のファイル名は`${annotation_id}.png`です。

        Args:
            details: `getEditorAnnotation` APIで取得した`details`
            label_ids: 更新対象のアノテーションに対応するラベルIDのcollection
            output_dir: 塗りつぶし画像の出力先のディレクトリ。

        Returns:
            tuple[0]: 更新対象の塗りつぶしアノテーションのannotation_idのlist（最前面のアノテーション）
            tuple[1]: 削除対象の塗りつぶしアノテーションのannotation_idのlist
        """

        def func(label_id: str) -> tuple[Optional[str], list[str]]:
            updated_annotation_id = None
            deleted_annotation_id_list = []
            binary_image_array_list = []
            segmentation_details = [e for e in details if e["label_id"] == label_id]
            if len(segmentation_details) <= 1:
                return None, []

            updated_annotation_id = segmentation_details[0]["annotation_id"]
            deleted_annotation_id_list = [e["annotation_id"] for e in segmentation_details[1:]]
            for detail in segmentation_details:
                segmentation_response = self.annofab_service.wrapper.execute_http_get(detail["body"]["url"], stream=True)
                segmentation_response.raw.decode_content = True
                binary_image_array_list.append(read_binary_image(segmentation_response.raw))

            merged_binary_image_array = merge_binary_image_array(binary_image_array_list)
            output_file_path = output_dir / f"{updated_annotation_id}.png"
            write_binary_image(merged_binary_image_array, output_file_path)
            return updated_annotation_id, deleted_annotation_id_list

        updated_annotation_id_list = []
        deleted_annotation_id_list = []
        for label_id in self.label_ids:
            updated_annotation_id, sub_deleted_annotation_id_list = func(label_id)
            if updated_annotation_id is not None:
                updated_annotation_id_list.append(updated_annotation_id)

            deleted_annotation_id_list.extend(sub_deleted_annotation_id_list)

        return updated_annotation_id_list, deleted_annotation_id_list

    def merge_segmentation_annotation(self, task_id: str, input_data_id: str, log_message_prefix: str = "") -> bool:
        """
        label_idに対応する複数の塗りつぶしアノテーションを1つにまとめます。

        Args:
            project_id: プロジェクトID
            task_id: タスクID
            annotation_id_list: 更新する塗りつぶし画像のannotation_idのlist
        """
        old_annotation, _ = self.annofab_service.api.get_editor_annotation(self.project_id, task_id, input_data_id, query_params={"v": "2"})
        old_details = old_annotation["details"]
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            updated_annotation_id_list, deleted_annotation_id_list = self.write_merged_segmentation_file(old_details, temp_dir_path)
            if len(updated_annotation_id_list) == 0:
                assert len(deleted_annotation_id_list) == 0
                logger.debug(
                    f"{log_message_prefix}更新対象の塗りつぶしアノテーションはなかった"
                    "（1個のラベルに塗りつぶしアノテーションは複数なかった）ので、スキップします。 :: "
                    f"task_id='{task_id}', input_data_id='{input_data_id}'"
                )
                return False

            logger.debug(
                f"{log_message_prefix}{len(updated_annotation_id_list)} 件の塗りつぶしアノテーションを更新して、"
                f"{len(deleted_annotation_id_list)} 件の塗りつぶしアノテーションを削除します。 :: "
                f"task_id='{task_id}', input_data_id='{input_data_id}', "
                f"更新対象のannotation_id_list={updated_annotation_id_list}, "
                f"削除対象のannotation_id_list={deleted_annotation_id_list}"
            )
            new_details = []
            for detail in old_details:
                annotation_id = detail["annotation_id"]
                if annotation_id in deleted_annotation_id_list:
                    continue

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
        logger.debug(
            f"{log_message_prefix}{len(updated_annotation_id_list)} 件の塗りつぶしアノテーションを更新して、"
            f"{len(deleted_annotation_id_list)} 件の塗りつぶしアノテーションを削除しました。 :: "
            f"task_id='{task_id}', input_data_id='{input_data_id}'"
        )
        return True

    def merge_segmentation_annotation_for_task(self, task_id: str, *, task_index: Optional[int] = None) -> int:
        """
        1個のタスクに対して、label_idに対応する複数の塗りつぶしアノテーションを1つにまとめます。

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

        if not self.confirm_processing(f"task_id='{task_id}'の次のラベル名に対応する複数の塗りつぶしアノテーションを1つにまとめますか？ :: {self.label_names}"):
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
                result = self.merge_segmentation_annotation(task_id, input_data_id, log_message_prefix=log_message_prefix)
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
            return self.merge_segmentation_annotation_for_task(task_id, task_index=task_index)
        except Exception:
            logger.warning(f"task_id='{task_id}' のアノテーションの更新に失敗しました。", exc_info=True)
            return 0

    def main(
        self,
        task_ids: Collection[str],
        parallelism: Optional[int] = None,
    ) -> None:
        logger.info(f"{len(task_ids)} 件のタスクに対して、複数の塗りつぶしアノテーションを1個にまとめます。")
        success_input_data_count = 0
        if parallelism is not None:
            with multiprocessing.Pool(parallelism) as pool:
                result_count_list = pool.map(self.update_segmentation_annotation_for_task_wrapper, enumerate(task_ids))
                success_input_data_count = sum(result_count_list)

        else:
            for task_index, task_id in enumerate(task_ids):
                try:
                    result = self.merge_segmentation_annotation_for_task(task_id, task_index=task_index)
                    success_input_data_count += result
                except Exception:
                    logger.warning(f"task_id='{task_id}' のアノテーションの更新に失敗しました。", exc_info=True)
                    continue

        logger.info(f"{len(task_ids)} 件のタスクに含まれる入力データ {success_input_data_count} 件の塗りつぶしアノテーションを更新しました。")


class MergeSegmentation(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation merge_segmentation: error:"

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
        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER, ProjectMemberRole.WORKER])

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        label_name_list = annofabcli.common.cli.get_list_from_args(args.label_name)

        annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params={"v": "3"})
        accessor = AnnotationSpecsAccessor(annotation_specs)
        label_id_list = []
        invalid_label_name_list = []
        for label_name in label_name_list:
            try:
                label = accessor.get_label(label_name=label_name)
                if label["annotation_type"] not in {DefaultAnnotationType.SEGMENTATION.value, DefaultAnnotationType.SEGMENTATION_V2.value}:
                    invalid_label_name_list.append(label_name)

            except ValueError:
                invalid_label_name_list.append(label_name)
                continue

            label_id_list.append(label["label_id"])

        if len(invalid_label_name_list) > 0:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} --label_name: 次のラベル名(英語)はアノテーション仕様に存在しないか、アノテーションの種類が「塗りつぶし」ではありません。 :: {invalid_label_name_list}",
                file=sys.stderr,
            )
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        main_obj = MergeSegmentationMain(
            self.service,
            project_id=project_id,
            label_ids=label_id_list,
            label_names=label_name_list,
            all_yes=self.all_yes,
            is_force=args.force,
        )

        main_obj.main(task_id_list, parallelism=args.parallelism)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    MergeSegmentation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    argument_parser.add_task_id()

    parser.add_argument(
        "--label_name",
        type=str,
        nargs="+",
        required=True,
        help="変更対象のアノテーションのラベル名(英語)を指定します。",
    )

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
    subcommand_name = "merge_segmentation"
    subcommand_help = "複数の塗りつぶしアノテーションを1つにまとめます。"
    description = (
        "複数の塗りつぶしアノテーションを1つにまとめます。"
        "ラベルの種類を「塗りつぶし（インスタンスセグメンテーション）」から「塗りつぶしv2（セマンティックセグメンテーション）」に変更する場合などに有用です。"
    )
    epilog = "オーナー、チェッカーまたはアノテータロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
