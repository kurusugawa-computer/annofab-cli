import argparse
import logging
import urllib.parse
from typing import Any, Dict, List, Optional

import annofabapi
from annofabapi.models import InputData, Task

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

    #: 入力データIDの平均長さ
    average_input_data_id_length: int = 36

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)
        self.average_input_data_id_length = args.average_input_data_id_length

    @staticmethod
    def _find_task_id_list(task_list: List[Task], input_data_id: str) -> List[str]:
        """
        タスク一覧から、該当のinput_data_idを持つtask_id_listを返す。
        """
        task_id_list = []
        for task in task_list:
            if input_data_id in task["input_data_id_list"]:
                task_id_list.append(task["task_id"])
        return task_id_list

    @annofabcli.utils.allow_404_error
    def get_input_data(self, project_id: str, input_data_id: str) -> InputData:
        input_data, _ = self.service.api.get_input_data(project_id, input_data_id)
        return input_data

    def get_input_data_from_input_data_id(self, project_id: str, input_data_id_list: List[str]) -> List[InputData]:
        input_data_list = []
        logger.debug(f"{len(input_data_id_list)}件の入力データを取得します。")
        for index, input_data_id in enumerate(input_data_id_list):
            if (index + 1) % 100 == 0:
                logger.debug(f"{index+1} 件目の入力データを取得します。")

            input_data = self.get_input_data(project_id, input_data_id)
            if input_data is not None:
                input_data_list.append(input_data)
            else:
                logger.warning(f"入力データ '{input_data_id}' は見つかりませんでした。")

        return input_data_list

    def add_details_to_input_data_list(self, project_id: str, input_data_list: List[InputData]) -> List[InputData]:
        """
        `input_data_list`に詳細情報（どのタスクに使われているか）を付与する。

        Args:
            project_id:
            input_data_list: 入力データList(In/Out)

        Returns:

        """
        if len(input_data_list) == 0:
            return input_data_list

        logger.debug(f"入力データ一覧の件数: {len(input_data_list)}")

        # AWS CloudFrontのURLの上限が8,192byte
        # https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cloudfront-limits.html
        MAX_URL_QUERY_LENGTH = 8000  # input_dat_ids部分のURLクエリの最大値
        average_input_data_id_length = self.average_input_data_id_length + 1  # カンマの分だけ長さを増やす
        chunk_size = MAX_URL_QUERY_LENGTH // average_input_data_id_length
        initial_index = 0
        while True:
            sub_input_data_list = input_data_list[initial_index : initial_index + chunk_size]
            sub_input_data_id_list = [e["input_data_id"] for e in sub_input_data_list]
            str_input_data_id_list = ",".join(sub_input_data_id_list)
            encoded_input_data_id_list = urllib.parse.quote(str_input_data_id_list)
            if len(encoded_input_data_id_list) > MAX_URL_QUERY_LENGTH:
                differential_length = len(encoded_input_data_id_list) - MAX_URL_QUERY_LENGTH
                decreasing_size = (differential_length // average_input_data_id_length) + 1
                logger.debug(
                    f"chunk_sizeを {chunk_size} から、{chunk_size - decreasing_size} に減らした. "
                    f"len(encoded_input_data_id_list) = {len(encoded_input_data_id_list)}"
                )
                chunk_size = chunk_size - decreasing_size
                if chunk_size <= 0:
                    chunk_size = 1

                continue

            logger.debug(f"input_data_list[{initial_index}:{initial_index+chunk_size}] を使用しているタスクを取得する。")
            task_list = self.service.wrapper.get_all_tasks(
                project_id, query_params={"input_data_ids": str_input_data_id_list}
            )

            for input_data in sub_input_data_list:
                # input_data_idで絞り込んでいるが、大文字小文字を区別しない。
                # したがって、確認のため `_find_task_id_list`を実行する
                task_id_list = self._find_task_id_list(task_list, input_data["input_data_id"])
                self.visualize.add_properties_to_input_data(input_data, task_id_list)

            initial_index = initial_index + chunk_size
            if initial_index >= len(input_data_list):
                break

        return input_data_list

    def get_input_data_list(
        self,
        project_id: str,
        input_data_id_list: Optional[List[str]] = None,
        input_data_query: Optional[Dict[str, Any]] = None,
        add_details: bool = False,
    ) -> List[InputData]:
        """
        入力データ一覧を取得する。
        """
        if input_data_id_list is not None:
            input_data_list = self.get_input_data_from_input_data_id(project_id, input_data_id_list)
        else:
            logger.debug(f"input_data_query: {input_data_query}")
            input_data_list = self.service.wrapper.get_all_input_data_list(project_id, query_params=input_data_query)

        # 詳細な情報を追加する
        if add_details:
            self.add_details_to_input_data_list(project_id, input_data_list)

        return input_data_list

    def print_input_data(
        self,
        project_id: str,
        input_data_query: Optional[Dict[str, Any]] = None,
        input_data_id_list: Optional[List[str]] = None,
        add_details: bool = False,
    ):
        """
        入力データ一覧を出力する

        Args:
            project_id: 対象のproject_id
            input_data_query: 入力データの検索クエリ
            input_data_id: 入力データID
            add_details: 詳細情報を表示する

        """

        super().validate_project(project_id, project_member_roles=None)

        input_data_list = self.get_input_data_list(
            project_id,
            input_data_query=input_data_query,
            input_data_id_list=input_data_id_list,
            add_details=add_details,
        )
        logger.info(f"入力データ一覧の件数: {len(input_data_list)}")
        if len(input_data_list) == 10000:
            logger.warning("入力データ一覧は10,000件で打ち切られている可能性があります。")

        if len(input_data_list) > 0:
            self.print_according_to_format(input_data_list)
        else:
            logger.info(f"入力データの件数が0件のため、出力しません。")

    def main(self):
        args = self.args
        input_data_id_list = annofabcli.common.cli.get_list_from_args(args.input_data_id)
        if len(input_data_id_list) == 0:
            input_data_id_list = None

        input_data_query = annofabcli.common.cli.get_json_from_args(args.input_data_query)
        self.print_input_data(
            args.project_id,
            input_data_id_list=input_data_id_list,
            input_data_query=input_data_query,
            add_details=args.add_details,
        )


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListInputData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    query_group = parser.add_mutually_exclusive_group()

    query_group.add_argument(
        "-iq",
        "--input_data_query",
        type=str,
        help="入力データの検索クエリをJSON形式で指定します。"
        "`file://`を先頭に付けると、JSON形式のファイルを指定できます。"
        "クエリのフォーマットは、[getInputDataList API](https://annofab.com/docs/api/#operation/getInputDataList)のクエリパラメータと同じです。"
        "ただし `page`, `limit`キーは指定できません。",
    )

    query_group.add_argument(
        "-i",
        "--input_data_id",
        type=str,
        nargs="+",
        help="対象のinput_data_idを指定します。`--input_data_query`引数とは同時に指定できません。"
        "`file://`を先頭に付けると、input_data_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument("--add_details", action="store_true", help="入力データの詳細情報を表示します（`parent_task_id_list`）")

    parser.add_argument(
        "--average_input_data_id_length",
        type=int,
        default=36,
        help=("入力データIDの平均長さを指定します。`add_details`がTrueのときのみ有効です。" "デフォルトはUUIDv4の長さです。" "この値を元にして、タスク一括取得APIの実行回数を決めます。"),
    )

    argument_parser.add_format(
        choices=[
            FormatArgument.CSV,
            FormatArgument.JSON,
            FormatArgument.PRETTY_JSON,
            FormatArgument.INPUT_DATA_ID_LIST,
        ],
        default=FormatArgument.CSV,
    )
    argument_parser.add_output()
    argument_parser.add_csv_format()

    argument_parser.add_query()
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list"
    subcommand_help = "入力データ一覧を出力します。"
    description = "入力データ一覧を出力します。AnnoFabの制約上、10,000件までしか出力されません。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
