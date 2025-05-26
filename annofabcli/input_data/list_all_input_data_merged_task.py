from __future__ import annotations

import argparse
import copy
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import pandas
from annofabapi.dataclass.input import InputData

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade, InputDataQuery, match_input_data_with_query
from annofabcli.common.utils import print_csv
from annofabcli.input_data.utils import remove_unnecessary_keys_from_input_data

logger = logging.getLogger(__name__)


def _create_dict_tasks_by_input_data_id(task_list: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """
    task_listから、keyがinput_data_id, valueがsub_task_listであるdictを生成します。
    """
    result = defaultdict(list)
    for task in task_list:
        for input_data_index, input_data_id in enumerate(task["input_data_id_list"]):
            new_task = {
                "task_id": task["task_id"],
                "task_status": task["status"],
                "task_phase": task["phase"],
                "task_phase_stage": task["phase_stage"],
                "frame_no": input_data_index + 1,
            }
            result[input_data_id].append(new_task)

    return result


def create_input_data_list_with_merged_task(input_data_list: list[dict[str, Any]], task_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    入力データのlistに、`parent_task_list`という参照されているタスクの情報が格納されたlistを返します。

    Args:
        input_data_list: 入力データのlist
        task_list: タスクのlist
    """
    dict_tasks_by_input_data_id = _create_dict_tasks_by_input_data_id(task_list)
    for input_data in input_data_list:
        input_data["parent_task_list"] = dict_tasks_by_input_data_id.get(input_data["input_data_id"], [])
        # 不要なキーを削除する
        remove_unnecessary_keys_from_input_data(input_data)
    return input_data_list


def create_df_input_data_with_merged_task(input_data_list: list[dict[str, Any]]) -> pandas.DataFrame:
    """
    参照されているタスクlist情報が格納されている入力データのlistを、pandas.DataFrameに変換します。
    """

    def get_columns(columns: pandas.Index) -> list[str]:
        task_columns = ["task_id", "task_status", "task_phase", "task_phase_stage", "frame_no"]
        new_columns = columns.drop(task_columns)
        return list(new_columns) + task_columns

    new_input_data_list = []
    for input_data in input_data_list:
        parent_task_list = input_data["parent_task_list"]

        if len(parent_task_list) > 0:
            for task in parent_task_list:
                new_input_data = copy.deepcopy(input_data)
                new_input_data.pop("parent_task_list")
                new_input_data.update(task)
                new_input_data_list.append(new_input_data)
        else:
            new_input_data = copy.deepcopy(input_data)
            new_input_data.pop("parent_task_list")
            new_input_data_list.append(new_input_data)

    # pandas.DataFrameでなくpandas.json_normalizeを使う理由:
    # ネストしたオブジェクトを`system_metadata.input_duration`のような列名でアクセスできるようにするため
    df_input_data = pandas.json_normalize(new_input_data_list)

    for column in ["task_id", "task_status", "task_phase", "task_phase_stage", "frame_no"]:
        if column not in df_input_data.columns:
            df_input_data[column] = pandas.NA

    # int型がfloat型になるのを防ぐためにnullableなInt64型を指定する
    df_input_data = df_input_data.astype({"task_phase_stage": "Int64", "frame_no": "Int64"})
    columns = get_columns(df_input_data.columns)
    return df_input_data[columns]


def match_input_data(
    input_data: dict[str, Any],
    input_data_id_set: Optional[set[str]] = None,
    input_data_query: Optional[InputDataQuery] = None,
) -> bool:
    result = True

    dc_input_data = InputData.from_dict(input_data)
    result = result and match_input_data_with_query(dc_input_data, input_data_query)
    if input_data_id_set is not None:
        result = result and (dc_input_data.input_data_id in input_data_id_set)
    return result


def match_parent_task_list_of_input_data_with(input_data: dict[str, Any], *, is_not_used_by_task: bool, is_used_by_multiple_task: bool) -> bool:
    parent_task_list = input_data["parent_task_list"]
    if is_not_used_by_task:
        return len(parent_task_list) == 0
    if is_used_by_multiple_task:
        return len(parent_task_list) > 1
    return True


class ListInputDataMergedTask(CommandLine):
    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli input_data list_all_merged_task: error:"  # noqa: N806
        if args.project_id is None and (args.input_data_json is None or args.task_json is None):
            print(  # noqa: T201
                f"{COMMON_MESSAGE} '--project_id' か、'--task_json'/'--input_data_json'ペアのいずれかを指定する必要があります。",
                file=sys.stderr,
            )
            return False

        if (args.input_data_json is None and args.task_json is not None) or (args.input_data_json is not None and args.task_json is None):
            print(  # noqa: T201
                f"{COMMON_MESSAGE} '--task_json'と'--input_data_json'の両方を指定する必要があります。",
                file=sys.stderr,
            )
            return False

        return True

    def download_json_files(self, project_id: str, output_dir: Path, *, is_latest: bool) -> None:
        downloading_obj = DownloadingFile(self.service)
        downloading_obj.download_input_data_json(
            project_id,
            dest_path=str(output_dir / "input_data.json"),
            is_latest=is_latest,
        )
        downloading_obj.download_task_json(project_id, dest_path=str(output_dir / "task.json"), is_latest=is_latest)

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id
        if project_id is not None:
            super().validate_project(project_id, None)
            cache_dir = annofabcli.common.utils.get_cache_dir()
            self.download_json_files(project_id, cache_dir, is_latest=args.latest)
            task_json_path = cache_dir / "task.json"
            input_data_json_path = cache_dir / "input_data.json"
        else:
            task_json_path = args.task_json
            input_data_json_path = args.input_data_json

        logger.debug(f"{task_json_path} を読み込み中")
        with open(task_json_path, encoding="utf-8") as f:  # noqa: PTH123
            task_list = json.load(f)

        logger.debug(f"{input_data_json_path} を読み込み中")
        with open(input_data_json_path, encoding="utf-8") as f:  # noqa: PTH123
            input_data_list = json.load(f)

        input_data_id_set = set(get_list_from_args(args.input_data_id)) if args.input_data_id is not None else None
        input_data_query = InputDataQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.input_data_query)) if args.input_data_query is not None else None
        filtered_input_data_list = [e for e in input_data_list if match_input_data(e, input_data_query=input_data_query, input_data_id_set=input_data_id_set)]

        input_data_list_with_merged_task = create_input_data_list_with_merged_task(input_data_list=filtered_input_data_list, task_list=task_list)

        filtered_input_data_list_with_merged_task = [
            e for e in input_data_list_with_merged_task if match_parent_task_list_of_input_data_with(e, is_not_used_by_task=args.not_used_by_task, is_used_by_multiple_task=args.used_by_multiple_task)
        ]

        logger.debug(f"入力データ {len(filtered_input_data_list_with_merged_task)} 件を出力します。")

        if self.str_format == FormatArgument.CSV.value:
            df_input_data = create_df_input_data_with_merged_task(filtered_input_data_list_with_merged_task)
            print_csv(df_input_data, output=args.output)

        elif self.str_format in [FormatArgument.JSON.value, FormatArgument.PRETTY_JSON.value]:
            self.print_according_to_format(filtered_input_data_list_with_merged_task)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListInputDataMergedTask(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    parser.add_argument(
        "-p",
        "--project_id",
        type=str,
        help="対象のプロジェクトのproject_idを指定してください。指定すると、入力データ一覧ファイル、タスク一覧ファイルをダウンロードします。",
    )

    parser.add_argument("-i", "--input_data_id", type=str, nargs="+", help="指定したinput_data_idに完全一致する入力データを絞り込みます。")
    parser.add_argument("--input_data_name", type=str, nargs="+", help="指定したinput_data_nameに部分一致(大文字小文字区別しない）する入力データを絞り込みます。")

    parser.add_argument(
        "-iq",
        "--input_data_query",
        type=str,
        help="入力データの検索クエリをJSON形式で指定します。"
        " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        "指定できるキーは、``input_data_id`` , ``input_data_name`` , ``input_data_path`` です。",
    )

    used_by_task_group = parser.add_mutually_exclusive_group()

    used_by_task_group.add_argument(
        "--not_used_by_task",
        action="store_true",
        help="タスクから使われていない入力データのみ出力します。\n「入力データは登録したがタスクは登録していなかった」などのデータ登録のミスを探すときに利用できます。",
    )

    used_by_task_group.add_argument(
        "--used_by_multiple_task",
        action="store_true",
        help="複数のタスクから使われている入力データのみ出力します。\n"
        "基本的な運用では、1個の入力データは複数のタスクから参照されることはありません。複数のタスクから参照されている場合は、データ登録のミスの可能性があります。このようなミスを探すときに利用できます。",
    )

    parser.add_argument(
        "--input_data_json",
        type=str,
        help="入力データ情報が記載されたJSONファイルのパスを指定してください。JSONに記載された情報を元に出力します。JSONファイルは ``$ annofabcli input_data download`` コマンドで取得できます。",
    )

    parser.add_argument(
        "--task_json",
        type=str,
        help="タスク情報が記載されたJSONファイルのパスを指定してください。JSONに記載された情報を元に出力します。JSONファイルは ``$ annofabcli task download`` コマンドで取得できます。",
    )

    parser.add_argument(
        "--latest",
        action="store_true",
        help="入力データ一覧ファイル、タスク一覧ファイルの更新が完了するまで待って、最新のファイルをダウンロードします。 ``--project_id`` を指定したときのみ有効です。",
    )

    argument_parser.add_format(
        choices=[
            FormatArgument.CSV,
            FormatArgument.JSON,
            FormatArgument.PRETTY_JSON,
        ],
        default=FormatArgument.CSV,
    )
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_all_merged_task"
    subcommand_help = "タスク一覧と結合したすべての入力データ一覧の情報を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
