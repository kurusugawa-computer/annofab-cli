import argparse
import asyncio
import json
import logging
import sys
from functools import partial
from pathlib import Path
from typing import Any, Dict, List

import annofabapi
import pandas
import requests
from annofabapi.models import JobType, ProjectMemberRole

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    get_wait_options_from_args,
)
from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.enums import FormatArgument

logger = logging.getLogger(__name__)


DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)


class DownloadingLatestFile:
    """
    `AbstractCommandLineInterface`を継承したクラスだと、`multiprocessing.Pool`を実行したときに
    `AttributeError: Can't pickle local object 'ArgumentParser.__init__.<locals>.identity'`というエラーが発生したので、
    `ArgumentParser`を除いたクラスを作成した。
    """

    def __init__(self, service: annofabapi.Resource):
        self.service = service

    async def wait_until_updated_input_data(self, project_id: str, wait_options: WaitOptions):
        try:
            self.service.api.post_project_inputs_update(project_id)
        except requests.HTTPError as e:
            if e.response.status_code != requests.codes.conflict:
                raise e

        loop = asyncio.get_event_loop()
        partial_func = partial(
            self.service.wrapper.wait_for_completion,
            project_id,
            JobType.GEN_INPUTS_LIST,
            wait_options.interval,
            wait_options.max_tries,
        )
        result = await loop.run_in_executor(None, partial_func)
        return result

    async def wait_until_updated_task(self, project_id: str, wait_options: WaitOptions):
        try:
            self.service.api.post_project_tasks_update(project_id)
        except requests.HTTPError as e:
            if e.response.status_code != requests.codes.conflict:
                raise e

        loop = asyncio.get_event_loop()
        partial_func = partial(
            self.service.wrapper.wait_for_completion,
            project_id,
            JobType.GEN_TASKS_LIST,
            wait_options.interval,
            wait_options.max_tries,
        )
        result = await loop.run_in_executor(None, partial_func)
        return result


class ListInputDataMergedTask(AbstractCommandLineInterface):
    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)

    @staticmethod
    def millisecond_to_hour(millisecond: int):
        return millisecond / 1000 / 3600

    def _to_task_list_based_input_data(self, task_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        new_all_task_list: List[Dict[str, Any]] = []
        for task in task_list:
            for input_data_id in task["input_data_id_list"]:
                new_task = {
                    "task_id": task["task_id"],
                    "status": task["status"],
                    "phase": task["phase"],
                    "worktime_hour": self.millisecond_to_hour(task["work_time_span"]),
                    "input_data_id": input_data_id,
                }
                new_all_task_list.append(new_task)
        return new_all_task_list

    def print_input_data_merged_task(self, input_data_list: List[Dict[str, Any]], task_list: List[Dict[str, Any]]):
        new_task_list = self._to_task_list_based_input_data(task_list)

        df_input_data = pandas.DataFrame(input_data_list)
        df_task = pandas.DataFrame(new_task_list)
        df_merged = pandas.merge(df_input_data, df_task, how="left", on="input_data_id")

        annofabcli.utils.print_according_to_format(
            df_merged, arg_format=FormatArgument(FormatArgument.CSV), output=self.output, csv_format=self.csv_format
        )

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

    def download_latest_files(self, project_id: str, output_dir: Path, is_latest: bool, wait_options: WaitOptions):
        if is_latest:
            downloading_obj = DownloadingLatestFile(self.service)
            loop = asyncio.get_event_loop()

            gather = asyncio.gather(
                downloading_obj.wait_until_updated_input_data(project_id, wait_options),
                downloading_obj.wait_until_updated_task(project_id, wait_options),
            )
            result = loop.run_until_complete(gather)
            if len([e for e in result if not e]) > 0:
                raise RuntimeError("タスク全件ファイル、入力データ全件ファイルの更新に失敗しました。")

        self.service.wrapper.download_project_inputs_url(project_id, str(output_dir / "input_data.json"))
        self.service.wrapper.download_project_tasks_url(project_id, str(output_dir / "task.json"))

    def main(self):
        args = self.args
        if not self.validate(args):
            return

        project_id = args.project_id
        if project_id is not None:
            super().validate_project(project_id, [ProjectMemberRole.OWNER])
            wait_options = get_wait_options_from_args(get_json_from_args(args.wait_options), DEFAULT_WAIT_OPTIONS)
            cache_dir = annofabcli.utils.get_cache_dir()
            self.download_latest_files(project_id, cache_dir, args.latest, wait_options)
            task_json_path = cache_dir / "task.json"
            input_data_json_path = cache_dir / "input_data.json"
        else:
            task_json_path = args.task_json
            input_data_json_path = args.input_data_json

        with open(task_json_path, encoding="utf-8") as f:
            task_list = json.load(f)

        with open(input_data_json_path, encoding="utf-8") as f:
            input_data_list = json.load(f)

        self.print_input_data_merged_task(input_data_list=input_data_list, task_list=task_list)


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
        help="入力データ情報が記載されたJSONファイルのパスを指定してください。JSONに記載された情報を元にタスク一覧を出力します。"
        "JSONファイルは`$ annofabcli project download input_data`コマンドで取得できます。",
    )

    parser.add_argument(
        "--task_json",
        type=str,
        help="タスク情報が記載されたJSONファイルのパスを指定してください。JSONに記載された情報を元にタスク一覧を出力します。"
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

    argument_parser.add_output()
    argument_parser.add_csv_format()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_merged_task"
    subcommand_help = "タスク一覧と結合した入力データ一覧のCSVを出力します。"
    description = "タスク一覧と結合した入力データ一覧のCSVを出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
