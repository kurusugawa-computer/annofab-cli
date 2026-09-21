from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

import annofabapi
from annofabapi.models import CommentType, ProjectMemberRole

import annofabcli.common.cli
from annofabcli.comment.put_comment import AddedComments, PutCommentMain, convert_cli_inspection_comment_list
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, PARALLELISM_CHOICES, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.task.reject_tasks import RejectTasks, RejectTasksMain

logger = logging.getLogger(__name__)


class RejectTasksWithInspectionCommentsMain(RejectTasksMain):
    """検査コメントを付与してからタスクを差し戻す処理。"""

    def __init__(self, service: annofabapi.Resource, *, project_id: str, comments_for_task_list: AddedComments, all_yes: bool = False) -> None:
        super().__init__(service, comment_data=None, all_yes=all_yes)
        self.comments_for_task_list = comments_for_task_list
        """タスクごとの作成対象検査コメント"""
        self.comment_main = PutCommentMain(service, project_id=project_id, comment_type=CommentType.INSPECTION, all_yes=all_yes)

    def add_inspection_comment(self, project_id: str, task: dict[str, Any], inspection_comment: str) -> None:
        """指定したタスクに紐付く検査コメントを付与する。"""
        del project_id, inspection_comment
        comments_for_task = self.comments_for_task_list[task["task_id"]]
        added_comment_count = self.comment_main.add_comments_to_working_task(task, comments_for_task, put_mode="create")
        logger.debug(f"task_id='{task['task_id']}'のタスクに{added_comment_count}件の検査コメントを付与しました。")


class RejectTasksWithInspectionComments(RejectTasks):
    """検査コメントを付与してタスクを差し戻すコマンド。"""

    COMMON_MESSAGE = "annofabcli task reject_with_inspection_comments: error:"

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        comment_list: Any = annofabcli.common.cli.get_json_from_args(args.json)
        if not isinstance(comment_list, list):
            print(f"{self.COMMON_MESSAGE} argument --json: JSON形式が不正です。配列を指定してください。", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
        if len(comment_list) == 0:
            print(f"{self.COMMON_MESSAGE} argument --json: 少なくとも1件の検査コメントを指定してください。", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        comments_for_task_list = convert_cli_inspection_comment_list(comment_list)
        assigned_annotator = self.get_assigned_annotator(args.project_id, args.assigned_annotator_user_id)
        if args.assigned_annotator_user_id is not None and assigned_annotator is None:
            return
        assign_last_annotator = not args.not_assign and assigned_annotator is None

        required_project_member_roles = [ProjectMemberRole.OWNER] if args.cancel_acceptance else [ProjectMemberRole.ACCEPTER, ProjectMemberRole.OWNER]
        super().validate_project(args.project_id, required_project_member_roles)

        main_obj = RejectTasksWithInspectionCommentsMain(self.service, project_id=args.project_id, comments_for_task_list=comments_for_task_list, all_yes=self.all_yes)
        main_obj.reject_task_list(
            args.project_id,
            list(comments_for_task_list),
            inspection_comment="",
            assign_last_annotator=assign_last_annotator,
            assigned_annotator=assigned_annotator,
            cancel_acceptance=args.cancel_acceptance,
            include_break_task=args.include_break_task,
            include_on_hold_task=args.include_on_hold_task,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    RejectTasksWithInspectionComments(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    parser.add_argument(
        "--json",
        type=str,
        required=True,
        help="作成する検査コメントの内容をJSON形式で指定してください。``file://`` を先頭に付けると、JSON形式のファイルを指定できます。形式は ``comment create_inspection --json`` と同じです。",
    )

    assign_group = parser.add_mutually_exclusive_group()
    assign_group.add_argument(
        "--not_assign",
        action="store_true",
        help="差し戻したタスクに担当者を割り当てません。指定しない場合は、最後の教師付フェーズの担当者が割り当てられます。",
    )
    assign_group.add_argument(
        "--assigned_annotator_user_id",
        type=str,
        help="差し戻したタスクに割り当てるユーザのuser_idを指定します。指定しない場合は、最後の教師付フェーズの担当者が割り当てられます。",
    )

    parser.add_argument("--cancel_acceptance", action="store_true", help="受入完了状態を取り消して、タスクを差し戻します。")
    parser.add_argument("--include_break_task", action="store_true", help="指定した場合、休憩中状態のタスクも処理します。指定しない場合、休憩中状態のタスクはスキップします。")
    parser.add_argument("--include_on_hold_task", action="store_true", help="指定した場合、保留中状態のタスクも処理します。指定しない場合、保留中状態のタスクはスキップします。")
    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "reject_with_inspection_comments"
    subcommand_help = "検査コメントを付与してタスクを差し戻します。"
    description = "検査コメントを付与してから、そのコメントに紐付くタスクを差し戻します。作業中状態のタスクに対しては差し戻せません。"
    epilog = "オーナロールを持つユーザで実行してください。``--cancel_acceptance`` を指定していない場合は、チェッカーロールを持つユーザーも実行できます。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
