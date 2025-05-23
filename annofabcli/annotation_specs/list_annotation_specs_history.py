import argparse
import logging
from typing import Any, Optional

import annofabapi

import annofabcli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


class AnnotationSpecsHistories(CommandLine):
    """
    アノテーション仕様の変更履歴を出力する。
    """

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace) -> None:
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)

    def get_annotation_specs_histories(self, project_id: str) -> list[dict[str, Any]]:
        annotation_specs_histories, _ = self.service.api.get_annotation_specs_histories(project_id)
        return [self.visualize.add_properties_to_annotation_specs_history(e) for e in annotation_specs_histories]

    def list_annotation_specs_histories(self, project_id: str) -> None:
        super().validate_project(project_id)

        annotation_specs_histories = self.get_annotation_specs_histories(project_id)
        self.print_according_to_format(annotation_specs_histories)

    def main(self) -> None:
        args = self.args
        self.list_annotation_specs_histories(args.project_id)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    AnnotationSpecsHistories(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    argument_parser.add_format(choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON], default=FormatArgument.CSV)
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_history"
    subcommand_help = "アノテーション仕様の変更履歴を表示する。"
    description = "アノテーション仕様の変更履歴を表示する。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
