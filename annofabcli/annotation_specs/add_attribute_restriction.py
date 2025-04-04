from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

import annofabcli
import annofabcli.common.cli
from annofabcli.annotation_specs.attribute_restriction import AttributeRestrictionMessage, OutputFormat
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)




def parse_args(parser: argparse.ArgumentParser) -> None:
    required_group = parser.add_mutually_exclusive_group(required=True)
    required_group.add_argument(
        "-p", "--project_id", help="対象のプロジェクトのproject_idを指定します。", required=True
    )

    parser.add_argument("--json", type=str, help="追加する属性の制約情報のJSONを指定します。"
                        "JSON形式は ... を参照してください。\n"
                        "``file://`` を先頭に付けるとjsonファイルを指定できます。")
    
    parser.add_argument(
        "--comment",
        type=str,
        help="アノテーション仕様の変更時に指定できるコメント。未指定の場合、自動でコメントが生成されます。"
    )


    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAttributeRestriction(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "add_attribute_restriction"

    subcommand_help = "アノテーション仕様に属性の制約を追加します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
