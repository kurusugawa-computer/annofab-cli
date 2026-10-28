import argparse

import annofabcli.comment.create_inspection_comment
import annofabcli.comment.create_inspection_comment_simply
import annofabcli.comment.create_onhold_comment
import annofabcli.comment.create_onhold_comment_simply
import annofabcli.comment.delete_comment
import annofabcli.comment.download_comment_json
import annofabcli.comment.list_all_comment
import annofabcli.comment.list_all_comment_with_replies
import annofabcli.comment.list_comment
import annofabcli.comment.list_comment_with_replies
import annofabcli.comment.put_inspection_comment
import annofabcli.comment.put_inspection_comment_simply
import annofabcli.comment.put_onhold_comment
import annofabcli.comment.put_onhold_comment_simply
import annofabcli.comment.update_inspection_comment
import annofabcli.comment.update_onhold_comment
import annofabcli.common.cli


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="subcommand_name", required=True)

    # サブコマンドの定義
    annofabcli.comment.create_inspection_comment.create_parser(subparsers)
    annofabcli.comment.create_inspection_comment_simply.create_parser(subparsers)
    annofabcli.comment.create_onhold_comment.create_parser(subparsers)
    annofabcli.comment.create_onhold_comment_simply.create_parser(subparsers)
    annofabcli.comment.delete_comment.create_parser(subparsers)
    annofabcli.comment.download_comment_json.create_parser(subparsers)
    annofabcli.comment.list_comment.create_parser(subparsers)
    annofabcli.comment.list_all_comment.create_parser(subparsers)
    annofabcli.comment.list_all_comment_with_replies.create_parser(subparsers)
    annofabcli.comment.list_comment_with_replies.create_parser(subparsers)
    annofabcli.comment.put_inspection_comment.create_parser(subparsers)
    annofabcli.comment.put_inspection_comment_simply.create_parser(subparsers)
    annofabcli.comment.put_onhold_comment.create_parser(subparsers)
    annofabcli.comment.put_onhold_comment_simply.create_parser(subparsers)
    annofabcli.comment.update_inspection_comment.create_parser(subparsers)
    annofabcli.comment.update_onhold_comment.create_parser(subparsers)


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "comment"
    subcommand_help = "コメント関係のサブコマンド"

    parser = annofabcli.common.cli.create_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help, is_subcommand=False)
    parse_args(parser)
    return parser
