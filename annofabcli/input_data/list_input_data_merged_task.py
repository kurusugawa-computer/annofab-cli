import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import annofabapi
import pandas
from annofabapi.models import ProjectMemberRole

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
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

logger = logging.getLogger(__name__)

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)


def millisecond_to_hour(millisecond: int):
    return millisecond / 1000 / 3600


class ListInputDataMergedTaskMain:
    def __init__(self, service: annofabapi.Resource):
        self.service = service
        self.facade = AnnofabApiFacade(service)

    @staticmethod
    def _to_task_list_based_input_data(task_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        new_all_task_list: List[Dict[str, Any]] = []
        for task in task_list:
            for input_data_id in task["input_data_id_list"]:
                new_task = {
                    "task_id": task["task_id"],
                    "status": task["status"],
                    "phase": task["phase"],
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
    ):
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
        input_data_id_list: Optional[List[str]] = None,
        input_data_name_list: Optional[List[str]] = None,
    ):
        new_task_list = self._to_task_list_based_input_data(task_list)

        df_input_data = pandas.DataFrame(input_data_list)
        df_input_data = self._filter_input_data(
            df_input_data, input_data_id_list=input_data_id_list, input_data_name_list=input_data_name_list
        )

        df_task = pandas.DataFrame(new_task_list)

        df_merged = pandas.merge(df_input_data, df_task, how="left", on="input_data_id")

        return df_merged


class ListInputDataMergedTask(AbstractCommandLineInterface):
    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)

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
                f"{COMMON_MESSAGE} '--task_json'と'--input_data_json'の両方を指定する必要があります。", file=sys.stderr,
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

    def main(self):
        args = self.args
        if not self.validate(args):
            return

        project_id = args.project_id
        if project_id is not None:
            super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
            wait_options = get_wait_options_from_args(get_json_from_args(args.wait_options), DEFAULT_WAIT_OPTIONS)
            cache_dir = annofabcli.utils.get_cache_dir()
            self.download_json_files(project_id, cache_dir, args.latest, wait_options)
            task_json_path = cache_dir / "task.json"
            input_data_json_path = cache_dir / "input_data.json"
        else:
            task_json_path = args.task_json
            input_data_json_path = args.input_data_json

        with open(task_json_path, encoding="utf-8") as f:
            task_list = json.load(f)

        with open(input_data_json_path, encoding="utf-8") as f:
            input_data_list = json.load(f)

        input_data_id_list = get_list_from_args(args.input_data_id) if args.input_data_id is not None else None
        input_data_name_list = get_list_from_args(args.input_data_name) if args.input_data_name is not None else None

        main_obj = ListInputDataMergedTaskMain(self.service)
        df_merged = main_obj.create_input_data_merged_task(
            input_data_list=input_data_list,
            task_list=task_list,
            input_data_id_list=input_data_id_list,
            input_data_name_list=input_data_name_list,
        )
        annofabcli.utils.print_according_to_format(
            df_merged, arg_format=FormatArgument(FormatArgument.CSV), output=self.output, csv_format=self.csv_format
        )


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListInputDataMergedTask(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    parser.add_argument(
        "-p", "--project_id", type=str, help="対象のプロジェクトのproject_idを指定してください。" "指定すると、入力データ一覧ファイル、タスク一覧ファイルをダウンロードします。"
    )

    parser.add_argument(
        "--input_data_json",
        type=str,
        help="入力データ情報が記載されたJSONファイルのパスを指定してください。JSONに記載された情報を元に出力します。"
        "JSONファイルは`$ annofabcli project download input_data`コマンドで取得できます。",
    )

    parser.add_argument(
        "--task_json",
        type=str,
        help="タスク情報が記載されたJSONファイルのパスを指定してください。JSONに記載された情報を元に出力します。"
        "JSONファイルは`$ annofabcli project download task`コマンドで取得できます。",
    )

    parser.add_argument(
        "--latest",
        action="store_true",
        help="入力データ一覧ファイル、タスク一覧ファイルの更新が完了するまで待って、最新のファイルをダウンロードします。" "'--project_id'を指定したときのみ有効です。",
    )

    parser.add_argument(
        "--wait_options",
        type=str,
        help="入力データ一覧ファイル、タスク一覧ファイルの更新が完了するまで待つ際のオプションを、JSON形式で指定してください。"
        "`file://`を先頭に付けるとjsonファイルを指定できます。"
        'デフォルは`{"interval":60, "max_tries":360}` です。'
        "`interval`:完了したかを問い合わせる間隔[秒], "
        "`max_tires`:完了したかの問い合わせを最大何回行うか。",
    )

    parser.add_argument("-i", "--input_data_id", type=str, nargs="+", help="指定したinput_data_idに完全一致する入力データを絞り込みます。")
    parser.add_argument(
        "--input_data_name", type=str, nargs="+", help="指定したinput_data_nameに部分一致(大文字小文字区別しない）する入力データを絞り込みます。"
    )

    argument_parser.add_output()
    argument_parser.add_csv_format()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_merged_task"
    subcommand_help = "タスク一覧と結合した入力データ一覧のCSVを出力します。"
    description = "タスク一覧と結合した入力データ一覧のCSVを出力します。"
    epilog = "アノテーションユーザまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
