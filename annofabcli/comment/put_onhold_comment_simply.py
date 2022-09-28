import argparse
import logging
import sys
from typing import Optional

from annofabapi.models import CommentType

import annofabcli
import annofabcli.common.cli
from annofabcli.comment.put_comment_simply import AddedSimpleComment, PutCommentSimplyMain
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class PutOnholdCommentSimply(AbstractCommandLineInterface):

    COMMON_MESSAGE = "annofabcli comment put_onhold_simply: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず '--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        super().validate_project(args.project_id)

        task_id_list = get_list_from_args(args.task_id)
        main_obj = PutCommentSimplyMain(
            self.service, project_id=args.project_id, comment_type=CommentType.ONHOLD, all_yes=self.all_yes
        )
        main_obj.put_comment_for_task_list(
            task_ids=task_id_list,
            comment_info=AddedSimpleComment(comment=args.comment, data=None, phrases=None),
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PutOnholdCommentSimply(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "-t",
        "--task_id",
        type=str,
        nargs="+",
        required=True,
        help=("コメントを付与するタスクのtask_idを指定してください。\n" "``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。"),
    )

    parser.add_argument(
        "--comment",
        type=str,
        required=True,
        help="コメントのメッセージを指定します。",
    )

    parser.add_argument(
        "--parallelism", type=int, help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "put_onhold_simply"
    subcommand_help = "``comment put_onhold`` コマンドよりも、簡単に保留コメントを付与します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
