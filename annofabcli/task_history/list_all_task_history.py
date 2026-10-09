import argparse
import json
import logging
import tempfile
from pathlib import Path

import annofabapi
from annofabapi.models import TaskHistory

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.visualize import AddProps
from annofabcli.task_history.list_task_history import CSV_COLUMNS

logger = logging.getLogger(__name__)

TaskHistoryDict = dict[str, list[TaskHistory]]
"""全タスクのタスク履歴一覧の集合体。keyはtask_id"""


class ListTaskHistoryWithJsonMain:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)

    @staticmethod
    def filter_task_history_dict(task_history_dict: TaskHistoryDict, task_id_list: list[str] | None = None) -> TaskHistoryDict:
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

    def get_task_history_dict(self, project_id: str, task_id_list: list[str] | None = None, temp_dir: Path | None = None) -> TaskHistoryDict:
        """出力対象のタスク履歴情報を取得する"""
        downloading_obj = DownloadingFile(self.service)

        def download_and_load(dir_path: Path) -> TaskHistoryDict:
            json_path = downloading_obj.download_task_history_json_to_dir(project_id, dir_path)
            with json_path.open(encoding="utf-8") as f:
                return json.load(f)

        if temp_dir is not None:
            all_task_history_dict = download_and_load(temp_dir)
        else:
            with tempfile.TemporaryDirectory() as str_temp_dir:
                all_task_history_dict = download_and_load(Path(str_temp_dir))

        task_history_dict = self.filter_task_history_dict(all_task_history_dict, task_id_list)

        visualize = AddProps(self.service, project_id)

        for task_history_list in task_history_dict.values():
            for task_history in task_history_list:
                visualize.add_properties_to_task_history(task_history)

        return task_history_dict

    @staticmethod
    def to_all_task_history_list_from_dict(task_history_dict: TaskHistoryDict) -> list[TaskHistory]:
        all_task_history_list = []
        for task_history_list in task_history_dict.values():
            all_task_history_list.extend(task_history_list)
        return all_task_history_list


class ListTaskHistoryWithJson(CommandLine):
    def print_task_history_list(
        self,
        project_id: str,
        task_id_list: list[str] | None,
        arg_format: OutputFormat,
        temp_dir: Path | None,
    ) -> None:
        """
        タスク履歴一覧を出力する

        Args:
            project_id: 対象のproject_id
            task_id_list: 対象のタスクのtask_id
            arg_format: 出力形式
            temp_dir: 全件ファイルの保存先ディレクトリ

        Returns:
            なし。

        """

        super().require_project_access(project_id, project_member_roles=None)

        main_obj = ListTaskHistoryWithJsonMain(self.service)
        task_history_dict = main_obj.get_task_history_dict(project_id, task_id_list=task_id_list, temp_dir=temp_dir)
        logger.debug(f"{len(task_history_dict)} 件のタスクの履歴情報を出力します。")
        if arg_format == OutputFormat.CSV:
            all_task_history_list = main_obj.to_all_task_history_list_from_dict(task_history_dict)
            self.print_according_to_format(all_task_history_list, csv_columns=CSV_COLUMNS)
        else:
            self.print_according_to_format(task_history_dict)

    def main(self) -> None:
        args = self.args

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        temp_dir = Path(args.temp_dir) if args.temp_dir is not None else None

        self.print_task_history_list(
            args.project_id,
            task_id_list=task_id_list,
            arg_format=OutputFormat(args.format),
            temp_dir=temp_dir,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListTaskHistoryWithJson(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    parser.add_argument(
        "-t",
        "--task_id",
        type=str,
        nargs="+",
        help="対象のタスクのtask_idを指定します。 ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "--temp_dir",
        type=str,
        help="ダウンロードしたJSONファイルの保存先ディレクトリを指定できます。指定しない場合は、一時ディレクトリに保存されます。",
    )

    argument_parser.add_format(
        choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON],
        default=OutputFormat.CSV,
    )
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_all"
    subcommand_help = "すべてのタスク履歴の一覧を出力します。"
    description = (
        "すべてのタスク履歴の一覧を出力します。\n"
        "出力されるタスク履歴は、コマンドを実行した日の02:00(JST)頃の状態です。最新の情報を出力したい場合は、 ``annofabcli task_history list`` コマンドを実行してください。"
    )

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
