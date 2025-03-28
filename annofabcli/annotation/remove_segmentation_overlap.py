from __future__ import annotations

import argparse
import copy
import logging
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

import annofabapi
import numpy
import numpy as np
from annofabapi.segmentation import read_binary_image, write_binary_image

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


def remove_overlap_of_binary_image_array(
    binary_image_array_by_annotation: dict[str, np.ndarray], annotation_id_list: list[str]
) -> dict[str, np.ndarray]:
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

        whole_2d_array = np.where(input_binary_image_array, annotation_id, whole_2d_array)

    output_binary_image_array_by_annotation = {}
    for annotation_id in annotation_id_list:
        output_binary_image_array = whole_2d_array == annotation_id
        output_binary_image_array_by_annotation[annotation_id] = output_binary_image_array

    return output_binary_image_array_by_annotation


class RemoveSegmentationOverlapMain(CommandLineWithConfirm):
    def __init__(self, service: annofabapi.Resource, *, project_id: str, all_yes: bool, is_force: bool) -> None:
        self.service = service
        self.project_id = project_id
        self.is_force = is_force

    def get_and_process_annotations(self, project_id: str, task_id: str, output_dir: Path) -> list[str]:
        """
        `getEditorAnnotation` APIを使用してアノテーションを取得し、重なりを除去して保存します。

        Args:
            project_id: プロジェクトID
            task_id: タスクID
            output_dir: 塗りつぶし画像の出力先のディレクトリ。

        Returns:
            重なりの除去が必要な塗りつぶし画像のannotation_idのlist
        """
        # Annofab APIを使用してアノテーションを取得
        details = self.annofab_service.api.get_editor_annotation(project_id, task_id)

        # 重なりを除去して保存
        return self.remove_segmentation_overlap_and_save(details, output_dir)

    def remove_segmentation_overlap_and_save(self, details: list[dict[str, Any]], output_dir: Path) -> list[str]:
        """
        `getEditorAnnotation` APIで取得した`details`から、塗りつぶし画像の重なりの除去が必要な場合に、重なりを除去した塗りつぶし画像を`output_dir`に出力します。
        塗りつぶし画像のファイル名は`${annotation_id}.png`です。

        Args:
            details: `getEditorAnnotation` APIで取得した`details`
            output_dir: 塗りつぶし画像の出力先のディレクトリ。

        Returns:
            重なりの除去が必要な塗りつぶし画像のannotation_idのlist
        """
        input_binary_image_array_by_annotation = {}
        for detail in details:
            if detail["body"]["_type"] != "Outer":
                continue

            segmentation_response = self.annofab_service.api._execute_http_request("get", detail["body"]["url"], stream=True)
            segmentation_response.raw.decode_content = True
            input_binary_image_array_by_annotation[detail["annotation_id"]] = read_binary_image(segmentation_response.raw)

        output_binary_image_array_by_annotation = remove_overlap_of_binary_image_array(input_binary_image_array_by_annotation)

        annotation_id_list = []
        for annotation_id, output_binary_image_array in output_binary_image_array_by_annotation.items():
            input_binary_image_array = input_binary_image_array_by_annotation[annotation_id]
            if not np.array_equal(input_binary_image_array, output_binary_image_array):
                output_file_path = output_dir / f"{annotation_id}.png"
                write_binary_image(output_binary_image_array, output_file_path)
                annotation_id_list.append(annotation_id)
        return annotation_id_list

    def update_segmentation_annotation(self, task_id: str, input_data_id: str) -> None:
        """
        `updateAnnotation` APIを使用して、重なりを除去した塗りつぶし画像を更新します。

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

            logger.debug(
                f"{len(updated_annotation_id_list)} 件の塗りつぶしアノテーションを更新します。 :: task_id='{task_id}, input_data_id='{input_data_id}', {updated_annotation_id_list}"
            )
            new_details = []
            for detail in old_details:
                annotation_id = detail["annotation_id"]
                new_detail = copy.deepcopy(detail)
                new_detail["_type"] = "Update"
                if annotation_id in updated_annotation_id_list:
                    with open(temp_dir_path / f"{annotation_id}.png", "rb") as f:
                        s3_path = self.annofab_service.wrapper.upload_data_to_s3(self.project_id, data=f, content_type="image/png")

                    new_detail["body"]["path"] = s3_path

                else:
                    # 更新しない場合は、`body`をNoneにする
                    new_detail["body"] = None
                    new_details.append(new_detail)
                    continue

                # 塗りつぶし画像の更新
                new_detail = detail.copy()
                new_detail["url"] = str(temp_dir_path / f"{detail['annotation_id']}.png")
                new_details.append(new_detail)

        new_details
        request_body = {
            "project_id": self.project_id,
            "task_id": task_id,
            "input_data_id": input_data_id,
            "details": new_details,
            # "format_version": "2.0.0",
            "updated_datetime": old_annotation["updated_datetime"],
        }
        self.annofab_service.api.put_annotation(self.project_id, task_id, input_data_id, query_params={"v": 2}, request_body=request_body)


class CopyAnnotation(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation copy: error:"

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

        # main_obj = CopyAnnotationMain(
        #     self.service,
        #     project_id=project_id,
        #     all_yes=self.all_yes,
        #     overwrite=args.overwrite,
        #     merge=args.merge,
        #     force=args.force,
        # )
        # main_obj.copy_annotations(copy_target_list, parallelism=args.parallelism)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CopyAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    INPUT_HELP_MESSAGE = """
    アノテーションのコピー元とコピー先を':'で区切って指定します。

    タスク単位でコピーする場合の例： ``src_task_id:dest_task_id``
    入力データ単位でコピーする場合： ``src_task_id/src_input_data_id:dest_task_id/dest_input_data_id``
    ``file://`` を先頭に付けると、コピー元とコピー先が記載されているファイルを指定できます。
    """  # noqa: N806
    parser.add_argument("--input", type=str, nargs="+", required=True, help=INPUT_HELP_MESSAGE)

    overwrite_merge_group = parser.add_mutually_exclusive_group()
    overwrite_merge_group.add_argument(
        "--overwrite",
        action="store_true",
        help="コピー先にアノテーションが存在する場合、 ``--overwrite`` を指定していれば、すでに存在するアノテーションを削除してコピーします。"
        "指定しなければ、アノテーションのコピーをスキップします。",
    )
    overwrite_merge_group.add_argument(
        "--merge",
        action="store_true",
        help="コピー先にアノテーションが存在する場合、 ``--merge`` を指定していればアノテーションをannotation_id単位でマージしながらコピーします。"
        "annotation_idが一致すればアノテーションを上書き、一致しなければアノテーションを追加します。"
        "指定しなければ、アノテーションのコピーをスキップします。",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="過去に割り当てられていて現在の担当者が自分自身でない場合、タスクの担当者を一時的に自分自身に変更してからアノテーションをコピーします。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="並列度。指定しない場合は、逐次的に処理します。指定した場合は、``--yes`` も指定してください。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "fix_segmentation_overlap"
    subcommand_help = "塗りつぶしアノテーションの重なりを除去します。"
    description = (
        "塗りつぶしアノテーションの重なりを除去します。インスタンスセグメンテーションは重ねることができてしまいます。この重なりを除去できます。"
    )
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
