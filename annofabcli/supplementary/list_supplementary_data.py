import argparse
import logging
from typing import List, Optional

from annofabapi.models import SupplementaryData

import annofabcli
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class ListSupplementaryData(AbstractCommandLineInterface):
    """
    補助情報一覧を表示する。
    """

    def get_input_data_id_from_task(self, project_id: str, task_id_list: List[str]) -> List[str]:
        all_input_data_id_list = []
        logger.info(f"{len(task_id_list)} 件のタスクを取得します。")
        for task_id in task_id_list:
            task = self.service.wrapper.get_task_or_none(project_id, task_id)
            if task is None:
                logger.warning(f"task_id='{task_id}'のタスクが見つかりませんでした。")
                continue
            all_input_data_id_list.extend(task["input_data_id_list"])
        return all_input_data_id_list

    def get_all_supplementary_data_list(
        self, project_id: str, input_data_id_list: List[str]
    ) -> List[SupplementaryData]:
        """
        補助情報一覧を取得する。
        """
        all_supplementary_data_list: List[SupplementaryData] = []
        logger.info(f"{len(input_data_id_list)} 件の入力データに紐づく補助情報を取得します。")
        for index, input_data_id in enumerate(input_data_id_list):
            if (index + 1) % 100 == 0:
                logger.debug(f"{index+1} 件目の入力データを取得します。")

            supplementary_data_list = self.service.wrapper.get_supplementary_data_list_or_none(
                project_id, input_data_id
            )
            if supplementary_data_list is not None:
                all_supplementary_data_list.extend(supplementary_data_list)
            else:
                logger.warning(f"入力データ '{input_data_id}' に紐づく補助情報が見つかりませんでした。")

        return all_supplementary_data_list

    def print_supplementary_data_list(
        self, project_id: str, input_data_id_list: Optional[List[str]], task_id_list: Optional[List[str]]
    ) -> None:
        """
        補助情報一覧を出力する

        """
        if task_id_list is not None:
            input_data_id_list = self.get_input_data_id_from_task(project_id, task_id_list)
        else:
            if input_data_id_list is None:
                logger.warning("input_data_id_listとtask_id_listの両方がNoneです。")
                return

        supplementary_data_list = self.get_all_supplementary_data_list(
            project_id, input_data_id_list=input_data_id_list
        )
        logger.info(f"補助情報一覧の件数: {len(supplementary_data_list)}")
        self.print_according_to_format(supplementary_data_list)

    def main(self):
        args = self.args
        input_data_id_list = (
            annofabcli.common.cli.get_list_from_args(args.input_data_id) if args.input_data_id is not None else None
        )
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None

        self.print_supplementary_data_list(
            project_id=args.project_id, input_data_id_list=input_data_id_list, task_id_list=task_id_list
        )


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListSupplementaryData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    query_group = parser.add_mutually_exclusive_group(required=True)
    query_group.add_argument(
        "-t",
        "--task_id",
        type=str,
        nargs="+",
        help="対象のタスクのtask_idを指定します。" + " ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )
    query_group.add_argument(
        "-i",
        "--input_data_id",
        type=str,
        nargs="+",
        help="対象の入力データのinput_data_idを指定します。" + " ``file://`` を先頭に付けると、input_data_idの一覧が記載されたファイルを指定できます。",
    )

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON], default=FormatArgument.CSV
    )
    argument_parser.add_output()
    argument_parser.add_csv_format()

    argument_parser.add_query()
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "list"
    subcommand_help = "補助情報一覧を出力します。"
    description = "補助情報一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
