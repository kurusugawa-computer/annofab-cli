import argparse
from typing import Optional

import annofabcli
import annofabcli.common.cli
import annofabcli.inspection_comment.delete_inspection_comments
import annofabcli.inspection_comment.download_inspection_comment_json
import annofabcli.inspection_comment.list_all_inspection_comment
import annofabcli.inspection_comment.put_inspection_comments
import annofabcli.inspection_comment.put_inspection_comments_simply


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.inspection_comment.delete_inspection_comments.add_parser(subparsers)
    annofabcli.inspection_comment.download_inspection_comment_json.add_parser(subparsers)
    annofabcli.inspection_comment.list_inspections.add_parser(subparsers)
    annofabcli.inspection_comment.list_all_inspection_comment.add_parser(subparsers)
    annofabcli.inspection_comment.put_inspection_comments.add_parser(subparsers)
    annofabcli.inspection_comment.put_inspection_comments_simply.add_parser(subparsers)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "inspection_comment"
    subcommand_help = "検査コメント関係のサブコマンド"
    description = "検査コメント関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description, is_subcommand=False
    )
    parse_args(parser)
    return parser
