"""
検査コメントを付与してタスクを差し戻します。
"""

import argparse
import logging
from typing import List, Optional

import requests
from annofabapi.dataclass.task import Task
from annofabapi.models import ProjectMemberRole, TaskStatus

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class ChangeOperator(AbstractCommandLineInterface):
    def confirm_change_operator(self, task: Task, user_id: Optional[str] = None) -> bool:
        if user_id is None:
            str_user_id = "未割り当て"
        else:
            str_user_id = user_id

        confirm_message = f"task_id = {task.task_id} のタスクの担当者を '{str_user_id}' にしますか？"
        return self.confirm_processing(confirm_message)

    def change_operator(self, project_id: str, task_id_list: List[str], user_id: Optional[str] = None):
        """
        検査コメントを付与して、タスクを差し戻す
        Args:
            project_id:
            task_id_list:
            user_id: タスクを担当するユーザのuser_id。Noneの場合タスクの担当者は未割り当て

        """

        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])

        if user_id is not None:
            account_id = self.facade.get_account_id_from_user_id(project_id, user_id)
            if account_id is None:
                logger.error(f"ユーザ '{user_id}' のaccount_idが見つかりませんでした。終了します。")
                return
        else:
            account_id = None

        logger.info(f"タスクの担当者を変更する件数: {len(task_id_list)}")
        success_count = 0

        for task_index, task_id in enumerate(task_id_list):
            str_progress = annofabcli.utils.progress_msg(task_index + 1, len(task_id_list))

            dict_task, _ = self.service.api.get_task(project_id, task_id)
            task: Task = Task.from_dict(dict_task)  # type: ignore

            if task.account_id is not None:
                user_id = self.facade.get_user_id_from_account_id(project_id, task.account_id)
            else:
                user_id = None

            logger.debug(
                f"{str_progress} : task_id = {task.task_id}, "
                f"status = {task.status.value}, "
                f"phase = {task.phase.value}, "
                f"user_id = {user_id}"
            )

            if task.status in [TaskStatus.COMPLETE, TaskStatus.WORKING]:
                logger.warning(
                    f"{str_progress} : task_id = {task_id} : タスクのstatusがworking or complete なので、担当者を変更できません。"
                )
                continue

            if not self.confirm_change_operator(task, user_id):
                continue

            try:
                # 担当者を変更する
                self.facade.change_operator_of_task(project_id, task_id, account_id)
                success_count += 1
                logger.debug(f"{str_progress} : task_id = {task_id}, phase={dict_task['phase']}, {user_id}に担当者を変更しました。")

            except requests.exceptions.HTTPError as e:
                logger.warning(e)
                logger.warning(f"{str_progress} : task_id = {task_id} の担当者を変更するのに失敗しました。")
                continue

        logger.info(f"{success_count} / {len(task_id_list)} 件 タスクの担当者を変更しました。")

    def main(self):
        args = self.args

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        if args.user_id is not None:
            user_id = args.user_id
        elif args.not_assign:
            user_id = None
        else:
            logger.error(f"タスクの担当者の指定方法が正しくありません。")
            return

        self.change_operator(args.project_id, task_id_list, user_id)


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    ChangeOperator(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    assign_group = parser.add_mutually_exclusive_group(required=True)

    assign_group.add_argument("-u", "--user_id", type=str, help="タスクを新しく担当するユーザのuser_idを指定してください。")

    assign_group.add_argument("--not_assign", action="store_true", help="指定した場合、タスクの担当者は未割り当てになります。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "change_operator"
    subcommand_help = "タスクの担当者を変更します。"
    description = "タスクの担当者を変更します。ただし、作業中のタスクに対しては変更しません。"
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
