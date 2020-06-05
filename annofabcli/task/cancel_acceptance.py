"""
受け入れ完了タスクを、受け入れ取り消しする。
"""

import argparse
import logging
from typing import List, Optional

import requests
from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class CancelAcceptance(AbstractCommandLineInterface):
    def cancel_acceptance(
        self,
        project_id: str,
        task_id_list: List[str],
        acceptor_user_id: Optional[str] = None,
        assign_last_acceptor: bool = True,
    ):
        """
        タスクを受け入れ取り消しする

        Args:
            project_id:
            task_id_list: 受け入れ取り消しするtask_id_list
            acceptor_user_id: 再度受入を担当させたいユーザのuser_id. Noneならば、未割り当てにする
            assign_last_acceptor: trueなら最後の受入担当者に割り当てる
        """

        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        if not assign_last_acceptor:
            acceptor_account_id = (
                self.facade.get_account_id_from_user_id(project_id, acceptor_user_id)
                if acceptor_user_id is not None
                else None
            )
        else:
            acceptor_account_id = None

        logger.info(f"受け入れを取り消すタスク数: {len(task_id_list)}")

        success_count = 0
        for task_index, task_id in enumerate(task_id_list):
            str_progress = annofabcli.utils.progress_msg(task_index + 1, len(task_id_list))

            try:
                task, _ = self.service.api.get_task(project_id, task_id)
                if task["status"] != "complete":
                    logger.warning(f"task_id = {task_id} は受入完了でありません。status = {task['status']}, phase={task['phase']}")
                    continue

                if assign_last_acceptor:
                    acceptor_account_id = task["account_id"]
                    if acceptor_account_id is not None:
                        user_info = self.facade.get_organization_member_from_account_id(project_id, acceptor_account_id)
                        if user_info is not None:
                            acceptor_user_id = user_info["user_id"]

                if not super().confirm_processing_task(
                    task_id, f"task_id = {task_id} のタスクの受入を取り消しますか？ user_id = '{acceptor_user_id}' に割り当てます。"
                ):
                    continue

                request_body = {
                    "status": "not_started",
                    "account_id": acceptor_account_id,
                    "last_updated_datetime": task["updated_datetime"],
                }
                self.service.api.operate_task(project_id, task_id, request_body=request_body)
                logger.info(
                    f"{str_progress} : task_id = {task_id} の受け入れ取り消しが成功しました。 user_id = '{acceptor_user_id}' に割り当てます。"
                )
                success_count += 1

            except requests.exceptions.HTTPError as e:
                logger.warning(e)
                logger.warning(f"{str_progress} : task_id = {task_id} の受け入れ取り消しに失敗しました。")

        logger.info(f"{success_count} / {len(task_id_list)} 件 受け入れ取り消しに成功した")

    def main(self):
        args = self.args

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

        assign_last_acceptor = not args.not_assign and args.assigned_acceptor_user_id is None

        self.cancel_acceptance(
            args.project_id,
            task_id_list,
            acceptor_user_id=args.assigned_acceptor_user_id,
            assign_last_acceptor=assign_last_acceptor,
        )


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CancelAcceptance(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):

    parser.add_argument("-p", "--project_id", type=str, required=True, help="対象のプロジェクトのproject_idを指定します。")

    parser.add_argument(
        "-t",
        "--task_id",
        type=str,
        required=True,
        nargs="+",
        help="対象のタスクのtask_idを指定します。`file://`を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )

    # 受入取消後のタスクの担当者の割当に関して
    assign_group = parser.add_mutually_exclusive_group()

    assign_group.add_argument(
        "--not_assign", action="store_true", help="受入を取り消した後のタスクの担当者を未割り当てにします。" "指定しない場合は、最後の受入phaseの担当者が割り当てます。"
    )

    assign_group.add_argument(
        "--assigned_acceptor_user_id",
        type=str,
        help="受入を取り消した後に割り当てる受入作業者のuser_idを指定します。" "指定しない場合は、最後の受入phaseの担当者が割り当てます。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "cancel_acceptance"
    subcommand_help = "受入が完了したタスクに対して、受入を取り消します。"
    description = "受入が完了したタスクに対して、受入を取り消します。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
