# pylint: disable=too-many-lines
from __future__ import annotations

import argparse
import logging
import sys
import tempfile
import zipfile
from collections.abc import Collection, Iterator
from pathlib import Path
from typing import Any, Literal, assert_never

import pandas
import pydantic
from annofabapi.models import ProjectMemberRole
from annofabapi.parser import (
    SimpleAnnotationParser,
    lazy_parse_simple_annotation_dir,
    lazy_parse_simple_annotation_zip,
)
from annofabapi.util.page import create_3dpc_editor_url, create_image_editor_url, create_video_editor_url

import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import (
    AnnofabApiFacade,
    TaskQuery,
    match_annotation_with_task_query,
)
from annofabcli.common.utils import print_csv, print_json

logger = logging.getLogger(__name__)

AnnotationEditorType = Literal["image", "video", "3dpc"]
"""アノテーションエディタの種類。"""

ANNOTATION_EDITOR_TYPE_CHOICES: tuple[AnnotationEditorType, ...] = ("image", "video", "3dpc")
"""``--annotation_editor_type`` に指定できる値。"""


def lazy_parse_simple_annotation_by_input_data(annotation_path: Path) -> Iterator[SimpleAnnotationParser]:
    if not annotation_path.exists():
        raise RuntimeError(f"'{annotation_path}' は存在しません。")

    if annotation_path.is_dir():
        return lazy_parse_simple_annotation_dir(annotation_path)
    elif zipfile.is_zipfile(str(annotation_path)):
        return lazy_parse_simple_annotation_zip(annotation_path)
    else:
        raise RuntimeError(f"'{annotation_path}'は、zipファイルまたはディレクトリではありません。")


class AnnotationAttribute(pydantic.BaseModel):
    """
    入力データまたはタスク単位の区間アノテーションの長さ情報。
    """

    project_id: str
    task_id: str
    task_status: str
    task_phase: str
    task_phase_stage: int

    input_data_id: str
    input_data_name: str
    updated_datetime: str | None
    """アノテーションJSONに格納されているアノテーションの更新日時"""
    annotation_id: str
    annotation_editor_url: str
    label: str
    attributes: dict[str, str | int | bool]


def get_seek_seconds_for_video_editor(detail: dict[str, Any]) -> float | None:
    """
    動画エディタで再生位置を指定する秒数を取得します。

    Args:
        detail: アノテーションJSONのdetails配下の要素
    """
    if detail["data"]["_type"] != "Range":
        return None

    return detail["data"]["begin"] / 1000


def create_annotation_editor_url(simple_annotation: dict[str, Any], detail: dict[str, Any], annotation_editor_type: AnnotationEditorType | None = None) -> str:
    """
    アノテーションエディタ画面のURLを生成します。

    Args:
        simple_annotation: アノテーションJSONファイルの内容
        detail: アノテーションJSONのdetails配下の要素
        annotation_editor_type: アノテーションエディタの種類
    """
    if annotation_editor_type == "image":
        return create_image_editor_url(
            simple_annotation["project_id"],
            simple_annotation["task_id"],
            input_data_id=simple_annotation["input_data_id"],
            annotation_id=detail["annotation_id"],
        )
    elif annotation_editor_type == "video":
        return create_video_editor_url(
            simple_annotation["project_id"],
            simple_annotation["task_id"],
            annotation_id=detail["annotation_id"],
            seek_seconds=get_seek_seconds_for_video_editor(detail),
        )
    elif annotation_editor_type == "3dpc":
        return create_3dpc_editor_url(
            simple_annotation["project_id"],
            simple_annotation["task_id"],
            input_data_id=simple_annotation["input_data_id"],
            annotation_id=detail["annotation_id"],
        )
    elif annotation_editor_type is not None:
        assert_never(annotation_editor_type)

    annotation_type = detail["data"]["_type"]
    if annotation_type == "Range":
        return create_video_editor_url(
            simple_annotation["project_id"],
            simple_annotation["task_id"],
            annotation_id=detail["annotation_id"],
            seek_seconds=get_seek_seconds_for_video_editor(detail),
        )
    elif annotation_type == "Unknown":
        return create_3dpc_editor_url(
            simple_annotation["project_id"],
            simple_annotation["task_id"],
            input_data_id=simple_annotation["input_data_id"],
            annotation_id=detail["annotation_id"],
        )

    return create_image_editor_url(
        simple_annotation["project_id"],
        simple_annotation["task_id"],
        input_data_id=simple_annotation["input_data_id"],
        annotation_id=detail["annotation_id"],
    )


def get_annotation_attribute_list_from_annotation_json(
    simple_annotation: dict[str, Any],
    *,
    target_labels: Collection[str] | None = None,
    annotation_editor_type: AnnotationEditorType | None = None,
) -> list[AnnotationAttribute]:
    """
    1個のアノテーションJSONに対して、アノテーションの属性情報を取得します。

    Args:
        simple_annotation: アノテーションJSONファイルの内容
        target_labels: 絞り込むラベルのcollection
        annotation_editor_type: アノテーションエディタの種類
    """
    details = simple_annotation["details"]

    result = []
    for detail in details:
        if target_labels is not None:  # noqa: SIM102
            if detail["label"] not in target_labels:
                continue

        result.append(
            AnnotationAttribute(
                project_id=simple_annotation["project_id"],
                task_id=simple_annotation["task_id"],
                task_status=simple_annotation["task_status"],
                task_phase=simple_annotation["task_phase"],
                task_phase_stage=simple_annotation["task_phase_stage"],
                input_data_id=simple_annotation["input_data_id"],
                input_data_name=simple_annotation["input_data_name"],
                label=detail["label"],
                annotation_id=detail["annotation_id"],
                annotation_editor_url=create_annotation_editor_url(simple_annotation, detail, annotation_editor_type),
                attributes=detail["attributes"],
                updated_datetime=simple_annotation["updated_datetime"],
            )
        )
    return result


def get_annotation_attribute_list_from_annotation_zipdir_path(
    annotation_zipdir_path: Path,
    *,
    target_task_ids: Collection[str] | None = None,
    task_query: TaskQuery | None = None,
    target_labels: Collection[str] | None = None,
    annotation_editor_type: AnnotationEditorType | None = None,
) -> list[AnnotationAttribute]:
    """
    アノテーションzipまたはそれを展開したディレクトリから、アノテーションの属性のlistを取得します。

    Args:
    """
    target_task_ids = set(target_task_ids) if target_task_ids is not None else None

    iter_parser = lazy_parse_simple_annotation_by_input_data(annotation_zipdir_path)

    result = []
    logger.debug("アノテーションzipまたはディレクトリを読み込み中")
    for index, parser in enumerate(iter_parser):
        if (index + 1) % 1000 == 0:
            logger.debug(f"{index + 1}  件目のJSONを読み込み中")

        if target_task_ids is not None and parser.task_id not in target_task_ids:
            continue

        simple_annotation_dict = parser.load_json()
        if task_query is not None:  # noqa: SIM102
            if not match_annotation_with_task_query(simple_annotation_dict, task_query):
                continue

        sub_result = get_annotation_attribute_list_from_annotation_json(
            simple_annotation_dict,
            target_labels=target_labels,
            annotation_editor_type=annotation_editor_type,
        )
        result.extend(sub_result)

    return result


def print_annotation_attribute_list_as_csv(annotation_attribute_list: list, output_file: Path | None) -> None:
    base_columns = [
        "project_id",
        "task_id",
        "task_status",
        "task_phase",
        "task_phase_stage",
        "input_data_id",
        "input_data_name",
        "updated_datetime",
        "annotation_id",
        "annotation_editor_url",
        "label",
    ]
    if len(annotation_attribute_list) == 0:
        print_csv(pandas.DataFrame(columns=base_columns), output_file)
        return

    df = pandas.json_normalize(annotation_attribute_list)

    attribute_columns = [col for col in df.columns if col.startswith("attributes.")]
    columns = base_columns + attribute_columns
    print_csv(df[columns], output_file)


def print_annotation_attribute_list(
    annotation_attribute_list: list[AnnotationAttribute],
    output_file: Path,
    output_format: Literal[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON],
) -> None:
    tmp_annotation_attribute_list = [e.model_dump() for e in annotation_attribute_list]
    if output_format == OutputFormat.CSV:
        print_annotation_attribute_list_as_csv(tmp_annotation_attribute_list, output_file)
    elif output_format == OutputFormat.JSON:
        print_json(tmp_annotation_attribute_list, output=output_file, is_pretty=False)
    elif output_format == OutputFormat.PRETTY_JSON:
        print_json(tmp_annotation_attribute_list, output=output_file, is_pretty=True)
    else:
        assert_never(output_format)


class ListAnnotationAttribute(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_zip list_annotation_attribute: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.project_id is None and args.annotation is None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --project_id: '--annotation'が未指定のときは、'--project_id' を指定してください。",
                file=sys.stderr,
            )
            return False
        if args.annotation_editor_type is not None and args.annotation is None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --annotation_editor_type: '--annotation'を指定したときのみ指定できます。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args

        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id: str | None = args.project_id
        if project_id is not None:
            super().validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        annotation_path = Path(args.annotation) if args.annotation is not None else None

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        label_name_list = annofabcli.common.cli.get_list_from_args(args.label_name) if args.label_name is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None
        annotation_editor_type: AnnotationEditorType | None = args.annotation_editor_type

        output_file: Path = args.output
        output_format = OutputFormat(args.format)

        downloading_obj = DownloadingFile(self.service)

        def download_and_print_annotation_attribute_list(project_id: str, temp_dir: Path, *, is_latest: bool, annotation_path: Path | None) -> None:
            if annotation_path is None:
                annotation_path = downloading_obj.download_annotation_zip_to_dir(
                    project_id,
                    temp_dir,
                    is_latest=is_latest,
                )

            annotation_attribute_list = get_annotation_attribute_list_from_annotation_zipdir_path(
                annotation_zipdir_path=annotation_path,
                target_task_ids=task_id_list,
                task_query=task_query,
                target_labels=label_name_list,
                annotation_editor_type=annotation_editor_type,
            )
            print_annotation_attribute_list(annotation_attribute_list, output_file, output_format)  # type: ignore[arg-type]

        if project_id is not None:
            if args.temp_dir is not None:
                download_and_print_annotation_attribute_list(project_id=project_id, temp_dir=args.temp_dir, is_latest=args.latest, annotation_path=annotation_path)
            else:
                # `NamedTemporaryFile`を使わない理由: Windowsで`PermissionError`が発生するため
                # https://qiita.com/yuji38kwmt/items/c6f50e1fc03dafdcdda0 参考
                with tempfile.TemporaryDirectory() as str_temp_dir:
                    download_and_print_annotation_attribute_list(project_id=project_id, temp_dir=Path(str_temp_dir), is_latest=args.latest, annotation_path=annotation_path)
        else:
            assert annotation_path is not None
            annotation_attribute_list = get_annotation_attribute_list_from_annotation_zipdir_path(
                annotation_zipdir_path=annotation_path,
                target_task_ids=task_id_list,
                task_query=task_query,
                target_labels=label_name_list,
                annotation_editor_type=annotation_editor_type,
            )
            print_annotation_attribute_list(annotation_attribute_list, output_file, output_format)  # type: ignore[arg-type]


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    annotation_group = parser.add_mutually_exclusive_group(required=True)
    annotation_group.add_argument(
        "--annotation",
        type=str,
        help="アノテーションzip、またはzipを展開したディレクトリを指定します。指定しない場合はAnnofabからダウンロードします。",
    )

    annotation_group.add_argument("-p", "--project_id", type=str, help="対象プロジェクトの project_id")

    parser.add_argument(
        "--annotation_editor_type",
        type=str,
        choices=ANNOTATION_EDITOR_TYPE_CHOICES,
        help="``--annotation`` で指定したアノテーションZIPに対応するアノテーションエディタの種類を指定します。"
        "未指定の場合は、Range型は ``video`` 、Unknown型は ``3dpc`` 、それ以外は ``image`` としてURLを生成します。",
    )

    argument_parser.add_format(
        choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON],
        default=OutputFormat.CSV,
    )

    argument_parser.add_output()

    parser.add_argument(
        "-tq",
        "--task_query",
        type=str,
        help="集計対象タスクを絞り込むためのクエリ条件をJSON形式で指定します。使用できるキーは task_id, status, phase, phase_stage です。"
        " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
    )
    argument_parser.add_task_id(required=False)

    parser.add_argument(
        "--label_name",
        type=str,
        nargs="+",
        required=False,
        help="出力対象のアノテーションのラベル名(英語)を指定します。指定しない場合はラベル名で絞り込みません。 ``file://`` を先頭に付けると、ラベル名の一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "--latest",
        action="store_true",
        help="``--annotation`` を指定しないとき、最新のアノテーションzipを参照します。このオプションを指定すると、アノテーションzipを更新するのに数分待ちます。",
    )

    parser.add_argument(
        "--temp_dir",
        type=Path,
        help="指定したディレクトリに、アノテーションZIPなどの一時ファイルをダウンロードします。",
    )

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAnnotationAttribute(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_annotation_attribute"
    subcommand_help = "アノテーションZIPを読み込み、アノテーションの属性値の一覧を出力します。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
