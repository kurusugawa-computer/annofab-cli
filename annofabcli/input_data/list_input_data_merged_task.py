import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import annofabapi
import pandas
from annofabapi.dataclass.input import InputData

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    get_list_from_args,
    get_wait_options_from_args,
)
from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade, InputDataQuery, match_input_data_with_query

logger = logging.getLogger(__name__)

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)


def millisecond_to_hour(millisecond: int):
    return millisecond / 1000 / 3600


class ListInputDataMergedTaskMain:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)

    @staticmethod
    def _to_task_list_based_input_data(task_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        new_all_task_list: List[Dict[str, Any]] = []
        for task in task_list:
            for input_data_id in task["input_data_id_list"]:
                new_task = {
                    "task_id": task["task_id"],
                    "task_status": task["status"],
                    "task_phase": task["phase"],
                    "worktime_hour": millisecond_to_hour(task["work_time_span"]),
                    "input_data_id": input_data_id,
                }
                new_all_task_list.append(new_task)
        return new_all_task_list

    @staticmethod
    def _filter_input_data(
        df_input_data: pandas.DataFrame,
        input_data_id_list: Optional[List[str]] = None,
        input_data_name_list: Optional[List[str]] = None,
    ) -> pandas.DataFrame:
        df = df_input_data
        if input_data_id_list is not None:
            df = df[df["input_data_id"].isin(input_data_id_list)]

        if input_data_name_list is not None:
            df = pandas.concat(
                [
                    df[df["input_data_name"].str.lower().str.contains(input_data_name.lower())]
                    for input_data_name in input_data_name_list
                ]
            )
        return df

    def create_input_data_merged_task(
        self,
        input_data_list: List[Dict[str, Any]],
        task_list: List[Dict[str, Any]],
        is_not_used_by_task: bool = False,
        is_used_by_multiple_task: bool = False,
    ):
        new_task_list = self._to_task_list_based_input_data(task_list)

        df_input_data = pandas.DataFrame(input_data_list)

        df_task = pandas.DataFrame(new_task_list)

        df_merged = pandas.merge(df_input_data, df_task, how="left", on="input_data_id")

        assert not (is_not_used_by_task and is_used_by_multiple_task)
        if is_not_used_by_task:
            df_merged = df_merged[df_merged["task_id"].isna()]

        if is_used_by_multiple_task:
            tmp = df_merged["input_data_id"].value_counts()
            input_data_ids = {input_data_id for (input_data_id, count) in tmp.items() if count >= 2}
            df_merged = df_merged[df_merged["input_data_id"].isin(input_data_ids)]

        return df_merged


def match_input_data(
    input_data: Dict[str, Any],
    input_data_id_set: Optional[Set[str]] = None,
    input_data_query: Optional[InputDataQuery] = None,
) -> bool:
    result = True

    dc_input_data = InputData.from_dict(input_data)
    result = result and match_input_data_with_query(dc_input_data, input_data_query)
    if input_data_id_set is not None:
        result = result and (dc_input_data.input_data_id in input_data_id_set)
    return result


class ListInputDataMergedTask(AbstractCommandLineInterface):
    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli input_data list_merged_task: error:"
        if args.project_id is None and (args.input_data_json is None or args.task_json is None):
            print(
                f"{COMMON_MESSAGE} '--project_id' か、'--task_json'/'--input_data_json'ペアのいずれかを指定する必要があります。",
                file=sys.stderr,
            )
            return False

        if (args.input_data_json is None and args.task_json is not None) or (
            args.input_data_json is not None and args.task_json is None
        ):
            print(
                f"{COMMON_MESSAGE} '--task_json'と'--input_data_json'の両方を指定する必要があります。",
                file=sys.stderr,
            )
            return False

        return True

    def download_json_files(self, project_id: str, output_dir: Path, is_latest: bool, wait_options: WaitOptions):
        loop = asyncio.get_event_loop()
        downloading_obj = DownloadingFile(self.service)
        gather = asyncio.gather(
            downloading_obj.download_input_data_json_with_async(
                project_id,
                dest_path=str(output_dir / "input_data.json"),
                is_latest=is_latest,
                wait_options=wait_options,
            ),
            downloading_obj.download_task_json_with_async(
                project_id, dest_path=str(output_dir / "task.json"), is_latest=is_latest, wait_options=wait_options
            ),
        )
        loop.run_until_complete(gather)

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id
        if project_id is not None:
            super().validate_project(project_id, None)
            wait_options = get_wait_options_from_args(get_json_from_args(args.wait_options), DEFAULT_WAIT_OPTIONS)
            cache_dir = annofabcli.common.utils.get_cache_dir()
            self.download_json_files(project_id, cache_dir, args.latest, wait_options)
            task_json_path = cache_dir / "task.json"
            input_data_json_path = cache_dir / "input_data.json"
        else:
            task_json_path = args.task_json
            input_data_json_path = args.input_data_json

        logger.debug(f"{task_json_path} を読み込み中")
        with open(task_json_path, encoding="utf-8") as f:
            task_list = json.load(f)

        logger.debug(f"{input_data_json_path} を読み込み中")
        with open(input_data_json_path, encoding="utf-8") as f:
            input_data_list = json.load(f)

        input_data_id_set = set(get_list_from_args(args.input_data_id)) if args.input_data_id is not None else None
        input_data_query = (
            InputDataQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.input_data_query))
            if args.input_data_query is not None
            else None
        )
        filtered_input_data_list = [
            e
            for e in input_data_list
            if match_input_data(e, input_data_query=input_data_query, input_data_id_set=input_data_id_set)
        ]

        main_obj = ListInputDataMergedTaskMain(self.service)
        df_merged = main_obj.create_input_data_merged_task(
            input_data_list=filtered_input_data_list,
            task_list=task_list,
            is_not_used_by_task=args.not_used_by_task,
            is_used_by_multiple_task=args.used_by_multiple_task,
        )

        logger.debug(f"一覧の件数: {len(df_merged)}")

        if self.str_format == FormatArgument.CSV.value:
            self.print_according_to_format(df_merged)
        elif self.str_format in [FormatArgument.JSON.value, FormatArgument.PRETTY_JSON.value]:
            result = df_merged.to_dict("records")
            self.print_according_to_format(result)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListInputDataMergedTask(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    parser.add_argument(
        "-p", "--project_id", type=str, help="対象のプロジェクトのproject_idを指定してください。" "指定すると、入力データ一覧ファイル、タスク一覧ファイルをダウンロードします。"
    )

    parser.add_argument("-i", "--input_data_id", type=str, nargs="+", help="指定したinput_data_idに完全一致する入力データを絞り込みます。")
    parser.add_argument(
        "--input_data_name", type=str, nargs="+", help="指定したinput_data_nameに部分一致(大文字小文字区別しない）する入力データを絞り込みます。"
    )

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
        help="タスクから使われていない入力データのみ出力します。",
    )

    used_by_task_group.add_argument(
        "--used_by_multiple_task",
        action="store_true",
        help="複数のタスクから使われている入力データのみ出力します。",
    )

    parser.add_argument(
        "--input_data_json",
        type=str,
        help="入力データ情報が記載されたJSONファイルのパスを指定してください。JSONに記載された情報を元に出力します。"
        "JSONファイルは ``$ annofabcli input_data download`` コマンドで取得できます。",
    )

    parser.add_argument(
        "--task_json",
        type=str,
        help="タスク情報が記載されたJSONファイルのパスを指定してください。JSONに記載された情報を元に出力します。"
        "JSONファイルは ``$ annofabcli task download`` コマンドで取得できます。",
    )

    parser.add_argument(
        "--latest",
        action="store_true",
        help="入力データ一覧ファイル、タスク一覧ファイルの更新が完了するまで待って、最新のファイルをダウンロードします。" " ``--project_id`` を指定したときのみ有効です。",
    )

    parser.add_argument(
        "--wait_options",
        type=str,
        help="入力データ一覧ファイル、タスク一覧ファイルの更新が完了するまで待つ際のオプションを、JSON形式で指定してください。"
        " ``file://`` を先頭に付けるとjsonファイルを指定できます。"
        'デフォルトは ``{"interval":60, "max_tries":360}`` です。'
        "``interval`` :完了したかを問い合わせる間隔[秒], "
        "``max_tires`` :完了したかの問い合わせを最大何回行うか。",
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
    argument_parser.add_csv_format()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_merged_task"
    subcommand_help = "タスク一覧と結合した入力データ一覧の情報を出力します。"
    description = "タスク一覧と結合した入力データ一覧の情報を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
