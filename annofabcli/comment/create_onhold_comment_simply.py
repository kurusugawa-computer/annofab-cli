import argparse
import logging
import sys

from annofabapi.models import CommentType, ProjectMemberRole

import annofabcli.common.cli
from annofabcli.comment.put_comment_simply import AddedSimpleComment, PutCommentSimplyMain
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class CreateOnholdCommentSimply(CommandLine):
    COMMON_MESSAGE = "annofabcli comment create_onhold_simply: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、'--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        required_project_member_roles = (
            [ProjectMemberRole.ACCEPTER, ProjectMemberRole.OWNER] if args.change_operator_to_me else [ProjectMemberRole.ACCEPTER, ProjectMemberRole.OWNER, ProjectMemberRole.WORKER]
        )
        super().validate_project(args.project_id, required_project_member_roles)

        task_id_list = get_list_from_args(args.task_id)
        main_obj = PutCommentSimplyMain(self.service, project_id=args.project_id, comment_type=CommentType.ONHOLD, all_yes=self.all_yes)
        main_obj.put_comment_for_task_list(
            task_ids=task_id_list,
            comment_info=AddedSimpleComment(comment=args.comment, data=None, phrases=None),
            parallelism=args.parallelism,
            change_operator_to_me=args.change_operator_to_me,
            include_break_task=args.include_break_task,
            include_on_hold_task=args.include_on_hold_task,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CreateOnholdCommentSimply(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "-t",
        "--task_id",
        type=str,
        nargs="+",
        required=True,
        help=("保留コメントを作成するタスクのtask_idを指定してください。\n``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。"),
    )

    parser.add_argument(
        "--comment",
        type=str,
        required=True,
        help="作成する保留コメントのメッセージを指定します。",
    )

    parser.add_argument(
        "--change_operator_to_me",
        action="store_true",
        help="オーナーまたはチェッカーロールで、自身が担当者ではないタスクに保留コメントを作成する場合に指定してください。タスクの担当者を一時的に自分自身に変更し、保留コメントの作成完了後に元へ戻します。",
    )

    parser.add_argument(
        "--include_break_task",
        action="store_true",
        help="休憩中状態のタスクに対しても保留コメントを作成します。未指定の場合は、休憩中状態のタスクはスキップされます。",
    )

    parser.add_argument(
        "--include_on_hold_task",
        action="store_true",
        help="保留中状態のタスクに対しても保留コメントを作成します。ただし、保留コメントの作成後は休憩中状態になります。未指定の場合は、保留中状態のタスクはスキップされます。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "create_onhold_simply"
    subcommand_help = "``comment create_onhold`` コマンドよりも、簡単に保留コメントを作成します。"
    epilog = (
        "ワーカーロールで実行する場合は、自身が担当するタスクだけに保留コメントを作成できます。"
        "``--change_operator_to_me`` を指定する場合は、オーナーロールまたはチェッカーロールを持つユーザで実行してください。"
    )

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
