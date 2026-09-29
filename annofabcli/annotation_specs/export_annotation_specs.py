from __future__ import annotations

import argparse
from typing import Any

import annofabcli.common.cli
from annofabcli.annotation_specs.history import add_history_arguments, resolve_history_id_or_exit
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import print_according_to_format


class ExportAnnotationSpecs(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs export: error:"

    def get_exported_annotation_specs(self, project_id: str, history_id: str | None) -> dict[str, Any]:
        query_params = {"v": "3"}
        if history_id is not None:
            query_params["history_id"] = history_id

        annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params=query_params)

        # アノテーション仕様画面のエクスポートが出力するJSONと同じ形式にするため、project_idを削除する
        annotation_specs.pop("project_id", None)
        return annotation_specs

    def main(self) -> None:
        args = self.args

        history_id = resolve_history_id_or_exit(
            self.service,
            args.project_id,
            history_id=args.history_id,
            before=args.before,
            updated_datetime=args.updated_datetime,
            common_message=self.COMMON_MESSAGE,
        )

        annotation_specs = self.get_exported_annotation_specs(args.project_id, history_id=history_id)

        print_according_to_format(annotation_specs, format=OutputFormat(args.format), output=args.output)


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    add_history_arguments(parser)

    argument_parser.add_output()

    parser.add_argument(
        "-f",
        "--format",
        type=str,
        choices=[OutputFormat.JSON.value, OutputFormat.PRETTY_JSON.value],
        default=OutputFormat.JSON.value,
        help="出力フォーマット",
    )

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ExportAnnotationSpecs(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "export"

    subcommand_help = "アノテーション仕様の情報をエクスポートします。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
