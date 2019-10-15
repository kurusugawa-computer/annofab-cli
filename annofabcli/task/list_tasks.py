"""
プロジェクトのユーザを表示する。
"""
import argparse
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Union  # pylint: disable=unused-import

import annofabapi
from annofabapi.models import Task

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


class ListTasks(AbstractCommandLineInterface):
    """
    タスクの一覧を表示する
    """
    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)

    def _modify_task_query(self, project_id: str, task_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        タスク検索クエリを修正する。
        ``user_id`` から ``account_id`` に変換する。
        ``previous_user_id`` から ``previcous_account_id`` に変換する。
        ``page`` , ``limit``を削除」する

        Args:
            task_query: タスク検索クエリ（変更される）

        Returns:
            修正したタスク検索クエリ

        """
        def remove_key(arg_key: str):
            if arg_key in task_query:
                logger.info(f"タスク検索クエリから、`{arg_key}`　キーを削除しました。")
                task_query.pop(arg_key)

        remove_key('page')
        remove_key('limit')

        if 'user_id' in task_query:
            user_id = task_query['user_id']
            account_id = self.facade.get_account_id_from_user_id(project_id, user_id)
            if account_id is not None:
                task_query['account_id'] = account_id
            else:
                logger.warning(f"タスク検索クエリに含まれている user_id: {user_id} のユーザが見つかりませんでした。")

        if 'previous_user_id' in task_query:
            previous_user_id = task_query['previous_user_id']
            previous_account_id = self.facade.get_account_id_from_user_id(project_id, previous_user_id)
            if previous_account_id is not None:
                task_query['previous_account_id'] = previous_account_id
            else:
                logger.warning(f"タスク検索クエリに含まれている previous_user_id: {previous_user_id} のユーザが見つかりませんでした。")

        return task_query

    def get_tasks(self, project_id: str, task_query: Optional[Dict[str, Any]] = None) -> List[Task]:
        """
        タスク一覧を取得する。

        Args:
            project_id:
            task_id_list:

        Returns:
            対象の検査コメント一覧
        """
        if task_query is not None:
            task_query = self._modify_task_query(project_id, task_query)

        logger.debug(f"task_query: {task_query}")
        tasks = self.service.wrapper.get_all_tasks(project_id, query_params=task_query)
        return [self.visualize.add_properties_to_task(e) for e in tasks]

    def filter_task_list(self, task_list: List[Task], project_id: str, task_query: Dict[str, Any]) -> List[Task]:
        """
        指定されたタスク一覧に`username`などの情報を追加して、`task_query`で絞り込む。

        Args:
            task_list:
            project_id: プロジェクトID. `user_id`や`username`を取得するのに必要な情報
            task_id_list:

        Returns:
            対象の検査コメント一覧
        """

        # TODO あとで絞りこめるようにする
        # task_query = self._modify_task_query(project_id, task_query)
        # logger.debug(f"task_query: {task_query}")
        return [self.visualize.add_properties_to_task(e) for e in task_list]

    def print_tasks(self, project_id: str, task_query: Optional[Dict[str, Any]] = None,
                    task_list_from_json: Optional[List[Task]] = None):
        """
        タスク一覧を出力する

        Args:
            project_id: 対象のproject_id
            task_query: タスク検索クエリ

        """

        super().validate_project(project_id, project_member_roles=None)

        if task_list_from_json is None:
            tasks = self.get_tasks(project_id, task_query)
            logger.debug(f"タスク一覧の件数: {len(tasks)}")
            if len(tasks) == 10000:
                logger.warning("タスク一覧は10,000件で打ち切られている可能性があります。")

        else:
            tasks = self.filter_task_list(task_list_from_json, project_id, task_query)
            logger.debug(f"タスク一覧の件数: {len(tasks)}")

        self.print_according_to_format(tasks)

    def main(self):
        args = self.args
        task_query = annofabcli.common.cli.get_json_from_args(args.task_query)

        if args.task_json is not None:
            with open(args.task_json, encoding="utf-8") as f:
                task_list = json.load(f)
        else:
            task_list = None

        self.print_tasks(args.project_id, task_query=task_query, task_list_from_json=task_list)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    ListTasks(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    # タスク検索クエリ
    parser.add_argument(
        '-tq', '--task_query', type=str, help='タスクの検索クエリをJSON形式で指定します。指定しない場合は、すべてのタスクを取得します。'
        '`file://`を先頭に付けると、JSON形式のファイルを指定できます。'
        'クエリのフォーマットは、[getTasks API](https://annofab.com/docs/api/#operation/getTasks)のクエリパラメータと同じです。'
        'さらに追加で、`user_id`, `previous_user_id` キーも指定できます。'
        'ただし `page`, `limit`キーは指定できません。')

    parser.add_argument('--task_json', type=str,
        help='タスク情報が記載されたJSONファイルのパスを指定すると、JSONに記載された情報を元にタスク一覧を出力します。AnnoFabからタスク情報は取得しません。'
        'JSONには記載されていない、`user_id`や`username`などの情報も追加します。'
        'JSONファイルは`annofabcli project download task`コマンドで取得できます。')

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON, FormatArgument.TASK_ID_LIST],
        default=FormatArgument.CSV)
    argument_parser.add_output()
    argument_parser.add_csv_format()

    argument_parser.add_query()
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list"
    subcommand_help = "タスク一覧を出力します。"
    description = ("タスク一覧を出力します。")

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
