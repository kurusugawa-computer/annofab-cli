"""
すべてのルートコメントに返信コメント一覧を付与して出力する。
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from annofabapi.models import CommentType

import annofabcli.common.cli
from annofabcli.comment.list_all_comment import ListAllCommentMain
from annofabcli.comment.utils import create_comment_list_with_replies
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import print_according_to_format

logger = logging.getLogger(__name__)


class ListAllCommentWithReplies(CommandLine):
    def main(self) -> None:
        args = self.args
        project_id = args.project_id
        super().validate_project(project_id, project_member_roles=None)

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        comment_type = CommentType(args.comment_type) if args.comment_type is not None else None
        temp_dir = Path(args.temp_dir) if args.temp_dir is not None else None

        main_obj = ListAllCommentMain(self.service)
        comment_list = main_obj.get_all_comment(
            project_id=project_id,
            comment_json=args.comment_json,
            task_ids=task_id_list,
            comment_type=comment_type,
            exclude_reply=False,
            temp_dir=temp_dir,
        )
        comment_list_with_replies = create_comment_list_with_replies(comment_list)

        logger.info(f"ルートコメントの件数: {len(comment_list_with_replies)}")

        print_according_to_format(comment_list_with_replies, OutputFormat(args.format), output=args.output)


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id(
        required=False,
        help_message=("対象のタスクのtask_idを指定します。 \n``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。"),
    )

    parser.add_argument(
        "--comment_type",
        choices=[CommentType.INSPECTION.value, CommentType.ONHOLD.value],
        help=(f"コメントの種類で絞り込みます。\n\n * {CommentType.INSPECTION.value}: 検査コメント\n * {CommentType.ONHOLD.value}: 保留コメント\n"),
    )

    parser.add_argument(
        "--comment_json",
        type=Path,
        help="コメント情報が記載されたJSONファイルのパスを指定すると、JSONに記載された情報を元にコメント一覧を出力します。\nJSONファイルは ``$ annofabcli comment download`` コマンドで取得できます。",
    )

    parser.add_argument(
        "--temp_dir",
        type=str,
        help="``--comment_json`` を指定しなかった場合、ダウンロードしたJSONファイルの保存先ディレクトリを指定できます。指定しない場合は、一時ディレクトリに保存されます。",
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


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAllCommentWithReplies(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_all_with_replies"
    subcommand_help = "すべてのルートコメントに返信コメント一覧を付与して出力します。"
    description = (
        "すべてのルートコメントに返信コメント一覧を付与して出力します。\n"
        "コメント一覧は、コマンドを実行した日の02:00(JST)頃の状態です。最新のコメント情報を取得したい場合は、 ``annofabcli comment list_with_replies`` コマンドを実行してください。"
    )

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
