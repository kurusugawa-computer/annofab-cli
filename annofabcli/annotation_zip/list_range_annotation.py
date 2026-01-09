from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas
from annofabapi.models import InputDataType, ProjectMemberRole
from dataclasses_json import DataClassJsonMixin

import annofabcli.common.cli
from annofabcli.common.annofab.annotation_zip import lazy_parse_simple_annotation_by_input_data
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, ArgumentParser, CommandLine, build_annofabapi_resource_and_login, get_list_from_args
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import (
    AnnofabApiFacade,
    TaskQuery,
    match_annotation_with_task_query,
)
from annofabcli.common.utils import print_csv, print_json

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RangeAnnotationInfo(DataClassJsonMixin):
    project_id: str
    task_id: str
    task_status: str
    task_phase: str
    task_phase_stage: int

    input_data_id: str
    input_data_name: str

    updated_datetime: str | None
    """アノテーションJSONに格納されているアノテーションの更新日時"""

    label: str
    annotation_id: str
    begin_second: float
    end_second: float
    duration_second: float
    attributes: dict[str, str | int | bool]


def get_range_annotation_info_list(simple_annotation: dict[str, Any], *, target_label_names: Collection[str] | None = None) -> list[RangeAnnotationInfo]:
    result = []
    target_label_names_set = set(target_label_names) if target_label_names is not None else None
    for detail in simple_annotation["details"]:
        if detail["data"]["_type"] == "Range":
            label = detail["label"]
            # ラベル名によるフィルタリング
            if target_label_names_set is not None and label not in target_label_names_set:
                continue

            begin_millisecond = detail["data"]["begin"]
            end_millisecond = detail["data"]["end"]
            begin_second = begin_millisecond / 1000
            end_second = end_millisecond / 1000
            duration_second = end_second - begin_second

            result.append(
                RangeAnnotationInfo(
                    project_id=simple_annotation["project_id"],
                    task_id=simple_annotation["task_id"],
                    task_phase=simple_annotation["task_phase"],
                    task_phase_stage=simple_annotation["task_phase_stage"],
                    task_status=simple_annotation["task_status"],
                    input_data_id=simple_annotation["input_data_id"],
                    input_data_name=simple_annotation["input_data_name"],
                    label=label,
                    annotation_id=detail["annotation_id"],
                    begin_second=begin_second,
                    end_second=end_second,
                    duration_second=duration_second,
                    updated_datetime=simple_annotation["updated_datetime"],
                    attributes=detail["attributes"],
                )
            )

    return result


def get_range_annotation_info_list_from_annotation_path(
    annotation_path: Path,
    *,
    target_task_ids: Collection[str] | None = None,
    task_query: TaskQuery | None = None,
    target_label_names: Collection[str] | None = None,
) -> list[RangeAnnotationInfo]:
    range_annotation_list = []
    target_task_ids = set(target_task_ids) if target_task_ids is not None else None
    iter_parser = lazy_parse_simple_annotation_by_input_data(annotation_path)
    logger.info(f"アノテーションZIPまたはディレクトリ'{annotation_path}'を読み込みます。")
    for index, parser in enumerate(iter_parser):
        if (index + 1) % 10000 == 0:
            logger.info(f"{index + 1}  件目のJSONを読み込み中")
        if target_task_ids is not None and parser.task_id not in target_task_ids:
            continue
        dict_simple_annotation = parser.load_json()
        if task_query is not None and not match_annotation_with_task_query(dict_simple_annotation, task_query):
            continue
        sub_range_annotation_list = get_range_annotation_info_list(dict_simple_annotation, target_label_names=target_label_names)
        range_annotation_list.extend(sub_range_annotation_list)
    return range_annotation_list


def create_df(
    range_annotation_list: list[RangeAnnotationInfo],
) -> pandas.DataFrame:
    base_columns = [
        "project_id",
        "task_id",
        "task_status",
        "task_phase",
        "task_phase_stage",
        "input_data_id",
        "input_data_name",
        "updated_datetime",
        "label",
        "annotation_id",
        "begin_second",
        "end_second",
        "duration_second",
    ]

    if not range_annotation_list:
        # 空のリストの場合は、base_columnsのみで空のDataFrameを返す
        return pandas.DataFrame(columns=base_columns)

    tmp_range_annotation_list = [e.to_dict(encode_json=True) for e in range_annotation_list]
    df = pandas.json_normalize(tmp_range_annotation_list)

    attribute_columns = sorted(col for col in df.columns if col.startswith("attributes."))
    columns = base_columns + attribute_columns

    return df[columns]


def print_range_annotation(
    annotation_path: Path,
    output_file: Path,
    output_format: FormatArgument,
    *,
    target_task_ids: Collection[str] | None = None,
    task_query: TaskQuery | None = None,
    target_label_names: Collection[str] | None = None,
) -> None:
    range_annotation_list = get_range_annotation_info_list_from_annotation_path(
        annotation_path,
        target_task_ids=target_task_ids,
        task_query=task_query,
        target_label_names=target_label_names,
    )

    logger.info(f"{len(range_annotation_list)} 件の区間アノテーションの情報を出力します。 :: output='{output_file}'")

    if output_format == FormatArgument.CSV:
        df = create_df(range_annotation_list)
        print_csv(df, output_file)

    elif output_format in [FormatArgument.PRETTY_JSON, FormatArgument.JSON]:
        json_is_pretty = output_format == FormatArgument.PRETTY_JSON
        # DataClassJsonMixinを使用したtoJSON処理
        print_json(
            [e.to_dict(encode_json=True) for e in range_annotation_list],
            is_pretty=json_is_pretty,
            output=output_file,
        )

    else:
        raise ValueError(f"出力形式 '{output_format}' はサポートされていません。")


class ListRangeAnnotation(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_zip list_range_annotation: error:"

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

        project_id: str | None = args.project_id
        if project_id is not None:
            super().validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
            project, _ = self.service.api.get_project(project_id)
            if project["input_data_type"] != InputDataType.MOVIE.value:
                print(f"project_id='{project_id}'であるプロジェクトは動画プロジェクトでないので、終了します", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        annotation_path = Path(args.annotation) if args.annotation is not None else None

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None
        label_name_list = get_list_from_args(args.label_name) if args.label_name is not None else None

        output_file: Path = args.output
        output_format = FormatArgument(args.format)

        downloading_obj = DownloadingFile(self.service)

        def download_and_print_range_annotation(project_id: str, temp_dir: Path, *, is_latest: bool) -> None:
            annotation_path = downloading_obj.download_annotation_zip_to_dir(
                project_id,
                temp_dir,
                is_latest=is_latest,
            )
            print_range_annotation(
                annotation_path,
                output_file,
                output_format,
                target_task_ids=task_id_list,
                task_query=task_query,
                target_label_names=label_name_list,
            )

        if project_id is not None:
            if args.temp_dir is not None:
                download_and_print_range_annotation(project_id=project_id, temp_dir=args.temp_dir, is_latest=args.latest)
            else:
                with tempfile.TemporaryDirectory() as str_temp_dir:
                    download_and_print_range_annotation(
                        project_id=project_id,
                        temp_dir=Path(str_temp_dir),
                        is_latest=args.latest,
                    )
        else:
            assert annotation_path is not None
            print_range_annotation(
                annotation_path,
                output_file,
                output_format,
                target_task_ids=task_id_list,
                task_query=task_query,
                target_label_names=label_name_list,
            )


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--annotation",
        type=str,
        help="アノテーションzip、またはzipを展開したディレクトリを指定します。",
    )

    group.add_argument("-p", "--project_id", type=str, help="project_id。アノテーションZIPをダウンロードします。")

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
        help="指定したラベル名の区間アノテーションのみを対象にします。複数指定できます。",
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
    ListRangeAnnotation(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_range_annotation"
    subcommand_help = "アノテーションZIPから動画プロジェクトの区間アノテーションの情報を出力します。"
    epilog = "アノテーションZIPをダウンロードする場合は、オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
