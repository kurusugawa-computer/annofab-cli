import argparse
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Union  # pylint: disable=unused-import

import annofabapi
from annofabapi.models import InputData, Task, TaskId

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


class ListInputData(AbstractCommandLineInterface):
    """
    入力データの一覧を表示する
    """
    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)

    @staticmethod
    def _find_task_id_list(task_list: List[Task], input_data_id: str) -> List[TaskId]:
        """
        タスク一覧から、該当のinput_data_idを持つtask_id_listを返す。
        """
        task_id_list = []
        for task in task_list:
            if input_data_id in task['input_data_id_list']:
                task_id_list.append(task['task_id'])
        return task_id_list

    def get_input_data(self, project_id: str, input_data_query: Dict[str, Any],
                       add_details: bool = False) -> List[InputData]:
        """
        入力データ一覧を取得する。
        """

        logger.debug(f"input_data_query: {input_data_query}")
        input_data_list = self.service.wrapper.get_all_input_data_list(project_id, query_params=input_data_query)
        print(f"len(input_data_list) = {len(input_data_list)}")
        # 詳細な情報を追加する
        if add_details:
            logger.info(f"{len(input_data_list)} 件、タスク一覧取得APIを実行する。")
            for input_data_index, input_data in enumerate(input_data_list):
                input_data_id = input_data['input_data_id']

                logger.debug(f"{input_data_index} 件目: input_data_id = {input_data_id} を使用しているタスクを取得する。")
                task_list = self.service.wrapper.get_all_tasks(project_id,
                                                               query_params={'input_data_ids': input_data_id})

                # input_data_idで絞り込んでいるが、大文字小文字を区別しない。
                # したがって、確認のため `_find_task_id_list`を実行する
                task_id_list = self._find_task_id_list(task_list, input_data_id)
                self.visualize.add_properties_to_input_data(input_data, task_id_list)

        return input_data_list

    def print_input_data(self, project_id: str, input_data_query: Dict[str, Any], add_details: bool = False):
        """
        入力データ一覧を出力する

        Args:
            project_id: 対象のproject_id
            input_data_query: 入力データの検索クエリ
            add_details: 詳細情報を表示する

        """

        super().validate_project(project_id, roles=None)

        input_data_list = self.get_input_data(project_id, input_data_query, add_details)
        input_data_list = self.search_with_jmespath_expression(input_data_list)

        logger.debug(f"入力データ一覧の件数: {len(input_data_list)}")
        if len(input_data_list) == 10000:
            logger.warning("入力データ一覧は10,000件で打ち切られている可能性があります。")

        self.print_according_to_format(input_data_list)

    def main(self):
        args = self.args
        input_data_query = annofabcli.common.cli.get_json_from_args(args.input_data_query)

        self.print_input_data(args.project_id, input_data_query=input_data_query, add_details=args.add_details)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    ListInputData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    # タスク検索クエリ
    parser.add_argument(
        '-iq', '--input_data_query', type=str, required=True, help='入力データの検索クエリをJSON形式で指定します。'
        '`file://`を先頭に付けると、JSON形式のファイルを指定できます。'
        'クエリのフォーマットは、[getInputDataList API](https://annofab.com/docs/api/#operation/getInputDataList)のクエリパラメータと同じです。'
        'ただし `page`, `limit`キーは指定できません。')

    parser.add_argument('--add_details', action='store_true', help='入力データの詳細情報を表示します（`parent_task_id_list`）')

    argument_parser.add_format(
        choices=[
            FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON, FormatArgument.INPUT_DATA_ID_LIST
        ], default=FormatArgument.CSV)
    argument_parser.add_output()
    argument_parser.add_csv_format()

    argument_parser.add_query()
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list"
    subcommand_help = "入力データ一覧を出力します。"
    description = ("入力データ一覧を出力します。AnnoFabの制約上、10,000件までしか出力されません。")

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
