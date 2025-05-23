from __future__ import annotations

import argparse
import logging
import sys
from typing import Any, Optional

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import print_according_to_format

logger = logging.getLogger(__name__)


class ExportAnnotationSpecs(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs export: error:"

    def get_history_id_from_before_index(self, project_id: str, before: int) -> Optional[str]:
        histories, _ = self.service.api.get_annotation_specs_histories(project_id)
        sorted_histories = sorted(histories, key=lambda x: x["updated_datetime"], reverse=True)

        if before + 1 > len(sorted_histories):
            logger.warning(f"アノテーション仕様の履歴は{len(sorted_histories)}個のため、最新より{before}個前のアノテーション仕様は見つかりませんでした。")
            return None

        history = sorted_histories[before]
        return history["history_id"]

    def get_exported_annotation_specs(self, project_id: str, history_id: Optional[str]) -> dict[str, Any]:
        query_params = {"v": "3"}
        if history_id is not None:
            query_params["history_id"] = history_id

        annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params=query_params)

        # アノテーション仕様画面のエクスポートが出力するJSONと同じ形式にするため、project_idを削除する
        annotation_specs.pop("project_id", None)
        return annotation_specs

    def main(self) -> None:
        args = self.args

        history_id = None
        if args.history_id is not None:
            history_id = args.history_id

        if args.before is not None:
            history_id = self.get_history_id_from_before_index(args.project_id, args.before)
            if history_id is None:
                print(  # noqa: T201
                    f"{self.COMMON_MESSAGE} argument --before: 最新より{args.before}個前のアノテーション仕様は見つかりませんでした。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        annotation_specs = self.get_exported_annotation_specs(args.project_id, history_id=history_id)

        print_according_to_format(annotation_specs, format=FormatArgument(args.format), output=args.output)


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    # 過去のアノテーション仕様を参照するためのオプション
    old_annotation_specs_group = parser.add_mutually_exclusive_group()
    old_annotation_specs_group.add_argument(
        "--history_id",
        type=str,
        help=(
            "出力したいアノテーション仕様のhistory_idを指定してください。 "
            "history_idは ``annotation_specs list_history`` コマンドで確認できます。 "
            "指定しない場合は、最新のアノテーション仕様が出力されます。 "
        ),
    )

    old_annotation_specs_group.add_argument(
        "--before",
        type=int,
        help=(
            "出力したい過去のアノテーション仕様が、最新よりいくつ前のアノテーション仕様であるかを指定してください。  "
            "たとえば ``1`` を指定した場合、最新より1個前のアノテーション仕様を出力します。 "
            "指定しない場合は、最新のアノテーション仕様が出力されます。 "
        ),
    )

    argument_parser.add_output()

    parser.add_argument(
        "-f",
        "--format",
        type=str,
        choices=[FormatArgument.JSON.value, FormatArgument.PRETTY_JSON.value],
        default=FormatArgument.JSON.value,
        help="出力フォーマット",
    )

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ExportAnnotationSpecs(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "export"

    subcommand_help = "アノテーション仕様の情報をエクスポートします。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
