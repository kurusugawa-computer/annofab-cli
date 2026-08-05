"""
指定したタスクのルートコメントに返信コメント一覧を付与して出力する。
"""

from __future__ import annotations

import argparse
import logging

from annofabapi.models import CommentType

import annofabcli.common.cli
from annofabcli.comment.list_comment import ListingComments
from annofabcli.comment.utils import create_comment_list_with_replies
from annofabcli.common.cli import ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import print_according_to_format

logger = logging.getLogger(__name__)


class ListingCommentsWithReplies(ListingComments):
    def main(self) -> None:
        args = self.args
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        comment_type = CommentType(args.comment_type) if args.comment_type is not None else None

        comment_list = self.get_comment_list(args.project_id, task_id_list, comment_type=comment_type, exclude_reply=False)
        comment_list_with_replies = create_comment_list_with_replies(comment_list)

        logger.info(f"ルートコメントの件数: {len(comment_list_with_replies)}")

        print_according_to_format(comment_list_with_replies, OutputFormat(args.format), output=args.output)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListingCommentsWithReplies(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id(
        required=True,
        help_message="対象のタスクのtask_idを指定します。 ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "--comment_type",
        choices=[CommentType.INSPECTION.value, CommentType.ONHOLD.value],
        help=(f"コメントの種類で絞り込みます。\n\n * {CommentType.INSPECTION.value}: 検査コメント\n * {CommentType.ONHOLD.value}: 保留コメント\n"),
    )

    argument_parser.add_format(
        choices=[
            OutputFormat.JSON,
            OutputFormat.PRETTY_JSON,
        ],
        default=OutputFormat.JSON,
    )
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_with_replies"
    subcommand_help = "指定したタスクのルートコメントに返信コメント一覧を付与して出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help)
    parse_args(parser)
    return parser
