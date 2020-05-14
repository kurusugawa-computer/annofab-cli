import argparse
import json
import logging
from typing import Any, Dict, List

import annofabapi
import pandas

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


class ListInputDataMergedTask(AbstractCommandLineInterface):
    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)

    def _to_task_list_based_input_data(self, task_list: List[Dict[str, Any]]):
        new_all_task_list = []
        for task in task_list:
            for input_data_id in task["input_data_id"]:
                new_task = {}
                new_task["input_data_id"] = input_data_id
                new_task.update(task)
                new_all_task_list.extend(new_task)

    def print_input_data_merged_task(self, input_data_list: List[Dict[str, Any]], task_list: List[Dict[str, Any]]):

        for task in task_list:
            self.visualize.add_properties_to_task(task)

        new_task_list = self._to_task_list_based_input_data(task_list)

        df_input_data = pandas.DataFrame(input_data_list)
        df_task = pandas.DataFrame(new_task_list)
        df_merged = pandas.merge(df_input_data, df_task, how="left", on="input_data_id")

        annofabcli.utils.print_according_to_format(
            df_merged, arg_format=FormatArgument(self.str_format), output=self.output, csv_format=self.csv_format
        )

    @staticmethod
    def validate(args: argparse.Namespace):
        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            return

        with open(args.task_json, encoding="utf-8") as f:
            task_list = json.load(f)

        with open(args.input_data_json, encoding="utf-8") as f:
            input_data_list = json.load(f)

        self.print_input_data_merged_task(input_data_list=input_data_list, task_list=task_list)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListInputDataMergedTask(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)
    # argument_parser.add_project_id()
    parser.add_argument(
        "--task_json",
        type=str,
        help="タスク情報が記載されたJSONファイルのパスを指定してください。JSONに記載された情報を元にタスク一覧を出力します。"
        "JSONファイルは`$ annofabcli project download task`コマンドで取得できます。",
    )

    parser.add_argument(
        "--input_data_json",
        type=str,
        help="入力データ情報が記載されたJSONファイルのパスを指定してください。JSONに記載された情報を元にタスク一覧を出力します。"
        "JSONファイルは`$ annofabcli project download input_data`コマンドで取得できます。",
    )

    argument_parser.add_output()
    argument_parser.add_csv_format()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_merged_task"
    subcommand_help = "タスク一覧と結合した入力データ一覧を出力します。"
    description = "タスク一覧と結合した入力データ一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
