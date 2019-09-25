import argparse
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Union  # pylint: disable=unused-import

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument

logger = logging.getLogger(__name__)


class AnnotationSpecsHistories(AbstractCommandLineInterface):
    """
    アノテーション仕様の変更履歴を出力する。
    """
    def list_annotation_specs_histories(self, project_id: str) -> None:
        annotation_specs_histories, _ = self.service.api.get_annotation_specs_histories(project_id)
        self.print_according_to_format(annotation_specs_histories)

    def main(self):
        args = self.args
        self.list_annotation_specs_histories(args.project_id)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    AnnotationSpecsHistories(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    argument_parser.add_format(choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON],
                               default=FormatArgument.CSV)
    argument_parser.add_output()
    argument_parser.add_csv_format()
    argument_parser.add_query()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "history"
    subcommand_help = "アノテーション仕様の変更履歴を表示する。"
    description = ("アノテーション仕様の変更履歴を表示する。")

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
