import argparse
import logging
from typing import List

from annofabapi.models import SupplementaryData

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument

logger = logging.getLogger(__name__)


class ListSupplementaryData(AbstractCommandLineInterface):
    """
    補助情報一覧を表示する。
    """

    @annofabcli.utils.allow_404_error
    def get_supplementary_data_list(self, project_id: str, input_data_id: str) -> SupplementaryData:
        supplementary_data_list, _ = self.service.api.get_supplementary_data_list(project_id, input_data_id)
        return supplementary_data_list

    def get_all_supplementary_data_list(
        self, project_id: str, input_data_id_list: List[str]
    ) -> List[SupplementaryData]:
        """
        補助情報一覧を取得する。
        """
        all_supplementary_data_list: List[SupplementaryData] = []

        logger.debug(f"{len(input_data_id_list)}件の入力データに紐づく補助情報を取得します。")
        for index, input_data_id in enumerate(input_data_id_list):
            if (index + 1) % 100 == 0:
                logger.debug(f"{index+1} 件目の入力データを取得します。")

            supplementary_data_list = self.get_supplementary_data_list(project_id, input_data_id)
            if supplementary_data_list is not None:
                all_supplementary_data_list.extend(supplementary_data_list)
            else:
                logger.warning(f"入力データ '{input_data_id}' に紐づく補助情報が見つかりませんでした。")

        return all_supplementary_data_list

    def print_supplementary_data_list(self, project_id: str, input_data_id_list: List[str]) -> None:
        """
        補助情報一覧を出力する

        """

        supplementary_data_list = self.get_all_supplementary_data_list(project_id, input_data_id_list)
        logger.info(f"補助情報一覧の件数: {len(supplementary_data_list)}")
        self.print_according_to_format(supplementary_data_list)

    def main(self):
        args = self.args
        input_data_id_list = annofabcli.common.cli.get_list_from_args(args.input_data_id)
        self.print_supplementary_data_list(project_id=args.project_id, input_data_id_list=input_data_id_list)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    ListSupplementaryData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    argument_parser.add_input_data_id()

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON], default=FormatArgument.CSV
    )
    argument_parser.add_output()
    argument_parser.add_csv_format()

    argument_parser.add_query()
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list"
    subcommand_help = "補助情報一覧を出力します。"
    description = "補助情報一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
