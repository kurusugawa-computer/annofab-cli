from __future__ import annotations
import annofabapi
import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Optional

import numpy
import numpy as np
from annofabapi.segmentation import read_binary_image, write_binary_image

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
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

class RemoveSegmentationOverlapMain:
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
    def __init__(self, annofab_service: annofabapi.Resource):
        self.annofab_service = annofab_service
        
        
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
    

    # def __to_dest_annotation_detail(
    #     self,
    #     dest_project_id: str,
    #     detail: dict[str, Any],
    #     account_id: str,
    # ) -> dict[str, Any]:
    #     """
    #     コピー元の１個のアノテーションを、コピー先用に変換する。
    #     塗りつぶし画像などの外部アノテーションファイルがある場合、S3にアップロードする。

    #     Notes:
    #         annotation_id をUUIDv4で生成すると、アノテーションリンク属性をコピーしたときに対応できないので、暫定的にannotation_idは維持するようにする。

    #     Raises:
    #         CheckSumError: アップロードした外部アノテーションファイルのMD5ハッシュ値が、S3にアップロードしたときのレスポンスのETagに一致しない

    #     """  # noqa: E501
    #     dest_detail = detail
    #     dest_detail["account_id"] = account_id
    #     if detail["data_holding_type"] == AnnotationDataHoldingType.OUTER.value:
    #         try:
    #             outer_file_url = detail["url"]
    #             src_response = self.api.("get", outer_file_url)
    #             s3_path = self.upload_data_to_s3(dest_project_id, data=src_response.content, content_type=src_response.headers["Content-Type"])
    #             dest_detail["path"] = s3_path
    #             dest_detail["url"] = None
    #             dest_detail["etag"] = None

    #         except CheckSumError as e:
    #             message = (
    #                 f"外部アノテーションファイル {outer_file_url} のレスポンスのMD5ハッシュ値('{e.uploaded_data_hash}')が、"
    #                 f"AWS S3にアップロードしたときのレスポンスのETag('{e.response_etag}')に一致しませんでした。アップロード時にデータが破損した可能性があります。"  # noqa: E501
    #             )
    #             raise CheckSumError(message=message, uploaded_data_hash=e.uploaded_data_hash, response_etag=e.response_etag) from e

    #     return dest_detail

    # def _create_request_body_for_copy_annotation(
    #     self,
    #     project_id: str,
    #     task_id: str,
    #     input_data_id: str,
    #     src_details: list[dict[str, Any]],
    #     account_id: Optional[str] = None,
    #     annotation_specs_relation: Optional[AnnotationSpecsRelation] = None,
    # ) -> dict[str, Any]:
    #     if account_id is None:
    #         account_id = self.api.account_id
    #     dest_details: list[dict[str, Any]] = []

    #     for src_detail in src_details:
    #         if annotation_specs_relation is not None:
    #             tmp_detail = self.__replace_annotation_specs_id(src_detail, annotation_specs_relation)
    #             if tmp_detail is None:
    #                 continue
    #             src_detail = tmp_detail  # noqa: PLW2901

    #         dest_detail = self.__to_dest_annotation_detail(project_id, src_detail, account_id=account_id)
    #         dest_details.append(dest_detail)

    #     request_body = {
    #         "project_id": project_id,
    #         "task_id": task_id,
    #         "input_data_id": input_data_id,
    #         "details": dest_details,
    #     }
    #     return request_body





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
