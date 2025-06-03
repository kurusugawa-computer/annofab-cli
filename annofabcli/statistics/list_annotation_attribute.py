# pylint: disable=too-many-lines
from __future__ import annotations

import argparse
import logging
import sys
import tempfile
import zipfile
from collections.abc import Collection, Iterator
from pathlib import Path
from typing import Any, Literal, Optional, Union

import pandas
import pydantic
from annofabapi.models import ProjectMemberRole
from annofabapi.parser import (
    SimpleAnnotationParser,
    lazy_parse_simple_annotation_dir,
    lazy_parse_simple_annotation_zip,
)

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import (
    AnnofabApiFacade,
    TaskQuery,
    match_annotation_with_task_query,
)
from annofabcli.common.type_util import assert_noreturn
from annofabcli.common.utils import print_csv, print_json

logger = logging.getLogger(__name__)


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
    annotation_id: str
    label: str
    attributes: dict[str, Union[str, int, bool]]


def get_annotation_attribute_list_from_annotation_json(simple_annotation: dict[str, Any], *, target_labels: Collection[str] | None = None) -> list[AnnotationAttribute]:
    """
    1個のアノテーションJSONに対して、アノテーションの属性情報を取得します。

    Args:
        simple_annotation: アノテーションJSONファイルの内容
        target_labels: 絞り込むラベルのcollection
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
                attributes=detail["attributes"],
            )
        )
    return result


def get_annotation_attribute_list_from_annotation_zipdir_path(
    annotation_zipdir_path: Path,
    *,
    target_task_ids: Optional[Collection[str]] = None,
    task_query: Optional[TaskQuery] = None,
    target_labels: Collection[str] | None = None,
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

        sub_result = get_annotation_attribute_list_from_annotation_json(simple_annotation_dict, target_labels=target_labels)
        result.extend(sub_result)

    return result


def print_annotation_attribute_list_as_csv(annotation_attribute_list: list, output_file: Optional[Path]) -> None:
    df = pandas.json_normalize(annotation_attribute_list)

    base_columns = [
        "project_id",
        "task_id",
        "task_status",
        "task_phase",
        "task_phase_stage",
        "input_data_id",
        "input_data_name",
        "annotation_id",
        "label",
    ]
    attribute_columns = [col for col in df.columns if col.startswith("attributes.")]
    columns = base_columns + attribute_columns
    print_csv(df[columns], output_file)


def print_annotation_attribute_list(
    annotation_attribute_list: list[AnnotationAttribute],
    output_file: Path,
    output_format: Literal[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON],
) -> None:
    tmp_annotation_attribute_list = [e.model_dump() for e in annotation_attribute_list]
    if output_format == FormatArgument.CSV:
        print_annotation_attribute_list_as_csv(tmp_annotation_attribute_list, output_file)
    elif output_format == FormatArgument.JSON:
        print_json(tmp_annotation_attribute_list, output=output_file, is_pretty=False)
    elif output_format == FormatArgument.PRETTY_JSON:
        print_json(tmp_annotation_attribute_list, output=output_file, is_pretty=True)
    else:
        raise assert_noreturn(output_format)


class ListAnnotationAttribute(CommandLine):
    COMMON_MESSAGE = "annofabcli statistics list_annotation_attribute: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.project_id is None and args.annotation is None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --project_id: '--annotation'が未指定のときは、'--project_id' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args

        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id: Optional[str] = args.project_id
        if project_id is not None:
            super().validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        annotation_path = Path(args.annotation) if args.annotation is not None else None

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        label_name_list = annofabcli.common.cli.get_list_from_args(args.label_name) if args.label_name is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None

        output_file: Path = args.output
        output_format = FormatArgument(args.format)

        downloading_obj = DownloadingFile(self.service)

        def download_and_print_annotation_attribute_list(project_id: str, temp_dir: Path, *, is_latest: bool, annotation_path: Optional[Path]) -> None:
            if annotation_path is None:
                annotation_path = temp_dir / f"{project_id}__annotation.zip"
                downloading_obj.download_annotation_zip(
                    project_id,
                    dest_path=annotation_path,
                    is_latest=is_latest,
                )

            annotation_attribute_list = get_annotation_attribute_list_from_annotation_zipdir_path(
                annotation_zipdir_path=annotation_path, target_task_ids=task_id_list, task_query=task_query, target_labels=label_name_list
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
                annotation_zipdir_path=annotation_path, target_task_ids=task_id_list, task_query=task_query, target_labels=label_name_list
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

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON],
        default=FormatArgument.CSV,
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


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_annotation_attribute"
    subcommand_help = "アノテーションZIPを読み込み、アノテーションの属性値の一覧を出力します。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
