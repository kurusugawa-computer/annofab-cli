import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import annofabapi
from annofabapi.models import TaskHistory

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)

TaskHistoryDict = Dict[str, List[TaskHistory]]
"""全タスクのタスク履歴一覧の集合体。keyはtask_id"""


class ListTaskHistoryWithJsonMain:
    def __init__(self, service: annofabapi.Resource):
        self.service = service
        self.facade = AnnofabApiFacade(service)

    @staticmethod
    def filter_task_history_dict(
        task_history_dict: TaskHistoryDict, task_id_list: Optional[List[str]] = None
    ) -> TaskHistoryDict:
        if task_id_list is None:
            return task_history_dict

        filtered_task_history_dict: TaskHistoryDict = {}
        for task_id in task_id_list:
            task_history_list = task_history_dict.get(task_id)
            if task_history_list is None:
                logger.warning(f"task_id='{task_id}'のタスク履歴は見つかりませんでした。")
            else:
                filtered_task_history_dict[task_id] = task_history_list
        return filtered_task_history_dict

    def get_task_history_dict(
        self, project_id: str, task_history_json: Optional[Path] = None, task_id_list: Optional[List[str]] = None
    ) -> TaskHistoryDict:
        """出力対象のタスク履歴情報を取得する"""
        if task_history_json is None:
            downloading_obj = DownloadingFile(self.service)
            cache_dir = annofabcli.utils.get_cache_dir()
            json_path = cache_dir / f"{project_id}-task_history.json"

            downloading_obj.download_task_history_json(project_id, str(json_path))
        else:
            json_path = task_history_json

        with json_path.open() as f:
            all_task_history_dict = json.load(f)

        task_history_dict = self.filter_task_history_dict(all_task_history_dict, task_id_list)

        visualize = AddProps(self.service, project_id)

        for task_history_list in task_history_dict.values():
            for task_history in task_history_list:
                visualize.add_properties_to_task_history(task_history)

        return task_history_dict

    @staticmethod
    def to_all_task_history_list_from_dict(task_history_dict: TaskHistoryDict) -> List[TaskHistory]:
        all_task_history_list = []
        for task_history_list in task_history_dict.values():
            all_task_history_list.extend(task_history_list)
        return all_task_history_list


class ListTaskHistoryWithJson(AbstractCommandLineInterface):
    def print_task_history_list(
        self,
        project_id: str,
        task_history_json: Optional[Path],
        task_id_list: Optional[List[str]],
        arg_format: FormatArgument,
    ):
        """
        タスク一覧を出力する

        Args:
            project_id: 対象のproject_id
            task_id_list: 対象のタスクのtask_id
            task_query: タスク検索クエリ
            task_list_from_json: JSONファイルから取得したタスク一覧

        """

        super().validate_project(project_id, project_member_roles=None)

        main_obj = ListTaskHistoryWithJsonMain(self.service)
        task_history_dict = main_obj.get_task_history_dict(
            project_id, task_history_json=task_history_json, task_id_list=task_id_list
        )
        if arg_format == FormatArgument.CSV:
            all_task_history_list = main_obj.to_all_task_history_list_from_dict(task_history_dict)
            self.print_according_to_format(all_task_history_list)
        else:
            self.print_according_to_format(task_history_dict)

    def main(self):
        args = self.args

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None

        self.print_task_history_list(
            args.project_id,
            task_history_json=args.task_history_json,
            task_id_list=task_id_list,
            arg_format=FormatArgument(args.format),
        )


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListTaskHistoryWithJson(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    parser.add_argument(
        "-t",
        "--task_id",
        type=str,
        nargs="+",
        help="対象のタスクのtask_idを指定します。" " ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "--task_history_json",
        type=Path,
        help="タスク履歴情報が記載されたJSONファイルのパスを指定すると、JSONに記載された情報を元にタスク履歴一覧を出力します。"
        "指定しない場合、JSONファイルをダウンロードします。"
        "JSONファイルは ``$ annofabcli project download task_history`` コマンドで取得できます。",
    )

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON],
        default=FormatArgument.CSV,
    )
    argument_parser.add_output()
    argument_parser.add_csv_format()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "list_with_json"
    subcommand_help = "タスク履歴全件ファイルからタスク履歴の一覧を出力します。"
    description = "タスク履歴全件ファイルからタスク履歴の一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
