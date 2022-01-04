import argparse
import logging
from typing import Any, Dict, List, Optional

import annofabapi
import pandas
from annofabapi.models import Task

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument
from annofabcli.common.utils import get_columns_with_priority
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


class ListTasksMain:
    def __init__(self, service: annofabapi.Resource, project_id: str):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.project_id = project_id
        self.visualize = AddProps(self.service, project_id)

    def get_task_list_from_task_id(self, project_id: str, task_id_list: List[str]) -> List[Task]:
        task_list = []
        logger.debug(f"{len(task_id_list)}件のタスクを取得します。")
        for index, task_id in enumerate(task_id_list):
            if (index + 1) % 100 == 0:
                logger.debug(f"{index+1} 件のタスクを取得します。")

            task = self.service.wrapper.get_task_or_none(project_id, task_id)
            if task is not None:
                task_list.append(self.visualize.add_properties_to_task(task))
            else:
                logger.warning(f"タスク '{task_id}' は見つかりませんでした。")

        return task_list

    def _modify_task_query(self, project_id: str, task_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        タスク検索クエリを修正する。
        ``user_id`` から ``account_id`` に変換する。
        ``previous_user_id`` から ``previous_account_id`` に変換する。
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

        remove_key("page")
        remove_key("limit")

        if "user_id" in task_query:
            user_id = task_query["user_id"]
            account_id = self.facade.get_account_id_from_user_id(project_id, user_id)
            if account_id is not None:
                task_query["account_id"] = account_id
            else:
                logger.warning(f"タスク検索クエリに含まれている user_id: {user_id} のユーザが見つかりませんでした。")

        if "previous_user_id" in task_query:
            previous_user_id = task_query["previous_user_id"]
            previous_account_id = self.facade.get_account_id_from_user_id(project_id, previous_user_id)
            if previous_account_id is not None:
                task_query["previous_account_id"] = previous_account_id
            else:
                logger.warning(f"タスク検索クエリに含まれている previous_user_id: {previous_user_id} のユーザが見つかりませんでした。")

        return task_query

    def get_task_list_with_api(
        self, project_id: str, task_query: Optional[Dict[str, Any]] = None, user_id_list: Optional[List[str]] = None
    ) -> List[Task]:
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
        else:
            task_query = {}

        if user_id_list is None:
            logger.debug(f"task_query: {task_query}")
            tasks = self.service.wrapper.get_all_tasks(project_id, query_params=task_query)
            if len(tasks) == 10000:
                logger.warning("タスク一覧は10,000件で打ち切られている可能性があります。")

        else:
            tasks = []
            for user_id in user_id_list:
                task_query["user_id"] = user_id
                task_query = self._modify_task_query(project_id, task_query)
                logger.debug(f"task_query: {task_query}")
                sub_tasks = self.service.wrapper.get_all_tasks(project_id, query_params=task_query)
                if len(sub_tasks) == 10000:
                    logger.warning(f"user_id={user_id}で絞り込んだタスク一覧は10,000件で打ち切られている可能性があります。")
                tasks.extend(sub_tasks)

        return [self.visualize.add_properties_to_task(e) for e in tasks]

    def get_task_list(
        self,
        project_id: str,
        task_id_list: Optional[List[str]] = None,
        task_query: Optional[Dict[str, Any]] = None,
        user_id_list: Optional[List[str]] = None,
    ) -> List[Task]:
        """


        Args:
            project_id: 対象のproject_id
            task_id_list: 対象のタスクのtask_id
            task_query: タスク検索クエリ
            user_id_list:

        Returns:

        """
        if task_id_list is not None:
            task_list = self.get_task_list_from_task_id(project_id, task_id_list=task_id_list)
        else:
            task_list = self.get_task_list_with_api(project_id, task_query=task_query, user_id_list=user_id_list)

        return task_list


class ListTasks(AbstractCommandLineInterface):
    """
    タスクの一覧を表示する
    """

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)

    PRIOR_COLUMNS = [
        "project_id",
        "task_id",
        "phase",
        "phase_stage",
        "status",
        "started_datetime",
        "updated_datetime",
        "user_id",
        "username",
        "worktime_hour",
        "metadata",
        "number_of_rejections_by_inspection",
        "number_of_rejections_by_acceptance",
    ]

    def main(self):
        args = self.args

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        user_id_list = annofabcli.common.cli.get_list_from_args(args.user_id) if args.user_id is not None else None
        task_query = annofabcli.common.cli.get_json_from_args(args.task_query)

        project_id = args.project_id
        super().validate_project(project_id, project_member_roles=None)

        main_obj = ListTasksMain(self.service, project_id=project_id)
        task_list = main_obj.get_task_list(
            project_id=project_id,
            task_id_list=task_id_list,
            task_query=task_query,
            user_id_list=user_id_list,
        )

        logger.debug(f"タスク一覧の件数: {len(task_list)}")

        if len(task_list) > 0:
            if self.str_format == FormatArgument.CSV.value:
                task_list = self.search_with_jmespath_expression(task_list)
                df = pandas.DataFrame(task_list)
                columns = get_columns_with_priority(df, prior_columns=self.PRIOR_COLUMNS)
                self.print_csv(df[columns])
            else:
                self.print_according_to_format(task_list)
        else:
            logger.info(f"タスク一覧の件数が0件のため、出力しません。")


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListTasks(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    query_group = parser.add_mutually_exclusive_group()

    # タスク検索クエリ
    query_group.add_argument(
        "-tq",
        "--task_query",
        type=str,
        help="タスクの検索クエリをJSON形式で指定します。指定しない場合は、すべてのタスクを取得します。"
        " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        "クエリのフォーマットは、`getTasks <https://annofab.com/docs/api/#operation/getTasks>`_ APIのクエリパラメータと同じです。"
        "さらに追加で、``user_id`` , ``previous_user_id`` キーも指定できます。"
        "ただし ``page`` , ``limit`` キーは指定できません。",
    )

    query_group.add_argument(
        "-t",
        "--task_id",
        type=str,
        nargs="+",
        help="対象のタスクのtask_idを指定します。 ``--task_query`` 引数とは同時に指定できません。"
        " ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "-u",
        "--user_id",
        type=str,
        nargs="+",
        help="絞り込み対象である担当者のuser_idを指定します。" " ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON, FormatArgument.TASK_ID_LIST],
        default=FormatArgument.CSV,
    )
    argument_parser.add_output()
    argument_parser.add_csv_format()

    argument_parser.add_query()
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "list"
    subcommand_help = "タスク一覧を出力します。"
    description = "タスク一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
