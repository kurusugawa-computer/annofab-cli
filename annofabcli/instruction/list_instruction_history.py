import argparse
import logging
from typing import Any, Dict, List

import annofabapi

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


class ListInstructionHistories(AbstractCommandLineInterface):
    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)

    def get_instruction_histories(self, project_id: str) -> List[Dict[str, Any]]:
        # limitを指定する理由：上限がわからないので大きい値を指定する
        histories, _ = self.service.api.get_instruction_history(project_id, query_params={"limit": 10000})
        visualize = AddProps(self.service, project_id)
        return [visualize.add_properties_to_instruction(e) for e in histories]

    def main(self):
        args = self.args
        project_id = args.project_id
        super().validate_project(project_id)

        histories = self.get_instruction_histories(project_id)
        self.print_according_to_format(histories)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListInstructionHistories(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):

    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    argument_parser.add_output()

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON], default=FormatArgument.CSV
    )
    argument_parser.add_csv_format()
    argument_parser.add_query()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_history"
    subcommand_help = "作業ガイドの変更履歴を出力します。"
    description = "作業ガイドの変更履歴を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
