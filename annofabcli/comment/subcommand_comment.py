import argparse
from typing import Optional

import annofabcli
import annofabcli.comment.download_comment_json
import annofabcli.comment.list_comment
import annofabcli.common.cli


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.comment.download_comment_json.add_parser(subparsers)
    annofabcli.comment.list_comment.add_parser(subparsers)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "comment"
    subcommand_help = "コメント関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description=subcommand_help, is_subcommand=False
    )
    parse_args(parser)
    return parser
