import argparse
import logging
import multiprocessing
import sys
from dataclasses import dataclass
from functools import partial
from typing import List, Optional, Tuple

import annofabapi
import requests
from annofabapi.dataclass.task import Task
from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstracCommandCinfirmInterface,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import TaskQuery, match_task_with_query

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class User:
    account_id: str
    user_id: str
    username: str


class CancelAcceptanceMain(AbstracCommandCinfirmInterface):
    def __init__(self, service: annofabapi.Resource, all_yes: bool = False):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        AbstracCommandCinfirmInterface.__init__(self, all_yes)

    def cancel_acceptance_for_task(
        self,
        project_id: str,
        task_id: str,
        acceptor: Optional[User] = None,
        assign_last_acceptor: bool = True,
        task_query: Optional[TaskQuery] = None,
        task_index: Optional[int] = None,
    ) -> bool:
        def get_user_id(user: Optional[User]) -> Optional[str]:
            return user.user_id if user is not None else None

        logging_prefix = f"{task_index + 1} 件目" if task_index is not None else ""

        try:
            task, _ = self.service.api.get_task(project_id, task_id)

            if task["status"] != "complete":
                logger.warning(
                    f"{logging_prefix}: task_id = {task_id} は受入完了でありません。"
                    f"status = {task['status']}, phase={task['phase']}"
                )
                return False

            actual_acceptor: Optional[User] = None
            if assign_last_acceptor:
                acceptor_account_id = task["account_id"]
                if acceptor_account_id is not None:
                    member = self.facade.get_project_member_from_account_id(project_id, acceptor_account_id)
                    if member is not None:
                        actual_acceptor = User(
                            account_id=member["account_id"], user_id=member["user_id"], username=member["username"]
                        )
                    else:
                        logger.warning(f"account_id='{acceptor_account_id}' であるユーザは見つかりませんでした。")
                        return False
            else:
                actual_acceptor = acceptor

            if not match_task_with_query(Task.from_dict(task), task_query):
                logger.debug(f"{logging_prefix} : task_id = {task_id} : TaskQueryの条件にマッチしないため、スキップします。")
                return False

            if not self.confirm_processing(
                f"{logging_prefix}: task_id = {task_id} のタスクの受入を取り消しますか？ "
                f"user_id = '{get_user_id(actual_acceptor)}' のユーザに割り当てます。"
            ):
                return False

            logger.debug(
                f"{logging_prefix}: task_id = {task_id} のタスクの受入を取り消し、"
                f"user_id = '{get_user_id(actual_acceptor)}' のユーザに割り当てます。"
            )
            request_body = {
                "status": "not_started",
                "account_id": actual_acceptor.account_id if actual_acceptor is not None else None,
                "last_updated_datetime": task["updated_datetime"],
            }
            self.service.api.operate_task(project_id, task_id, request_body=request_body)
            logger.info(f"{logging_prefix} : task_id = {task_id} の受け入れ取り消しが成功しました。")
            return True

        except requests.exceptions.HTTPError as e:
            logger.warning(f"{logging_prefix} : task_id = {task_id} の受け入れ取り消しに失敗しました。")
            logger.warning(e)
            return False

    def cancel_acceptance_for_wrapper(
        self,
        tpl: Tuple[int, str],
        project_id: str,
        acceptor: Optional[User] = None,
        assign_last_acceptor: bool = True,
        task_query: Optional[TaskQuery] = None,
    ) -> bool:
        task_index, task_id = tpl
        return self.cancel_acceptance_for_task(
            project_id=project_id,
            task_id=task_id,
            acceptor=acceptor,
            assign_last_acceptor=assign_last_acceptor,
            task_query=task_query,
            task_index=task_index,
        )

    def cancel_acceptance_for_task_list(
        self,
        project_id: str,
        task_id_list: List[str],
        acceptor_user_id: Optional[str] = None,
        assign_last_acceptor: bool = True,
        task_query: Optional[TaskQuery] = None,
        parallelism: Optional[int] = None,
    ):
        """
        タスクを受入取り消しする

        Args:
            project_id:
            task_id_list: 受け入れ取り消しするtask_id_list
            acceptor_user_id: 再度受入を担当させたいユーザのuser_id. Noneならば、未割り当てにする
            assign_last_acceptor: trueなら最後の受入担当者に割り当てる
        """
        logger.info(f"受け入れを取り消すタスク数: {len(task_id_list)}")

        if task_query is not None:
            task_query = self.facade.set_account_id_of_task_query(project_id, task_query)

        acceptor: Optional[User] = None
        if acceptor_user_id is not None:
            member = self.facade.get_project_member_from_user_id(project_id, acceptor_user_id)
            if member is not None:
                acceptor = User(account_id=member["account_id"], user_id=member["user_id"], username=member["username"])
            else:
                raise RuntimeError(f"user_id='{acceptor_user_id}' であるプロジェクトメンバは見つかりませんでした。")

        success_count = 0
        if parallelism is not None:
            partial_func = partial(
                self.cancel_acceptance_for_wrapper,
                project_id=project_id,
                acceptor=acceptor,
                assign_last_acceptor=assign_last_acceptor,
                task_query=task_query,
            )
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(partial_func, enumerate(task_id_list))
                success_count = len([e for e in result_bool_list if e])

        else:
            # 逐次処理
            success_count = 0
            for task_index, task_id in enumerate(task_id_list):
                result = self.cancel_acceptance_for_task(
                    project_id,
                    task_id,
                    task_index=task_index,
                    acceptor=acceptor,
                    assign_last_acceptor=assign_last_acceptor,
                    task_query=task_query,
                )
                if result:
                    success_count += 1

        logger.info(f"{success_count} / {len(task_id_list)} 件 受け入れ取り消しに成功しました。")


class CancelAcceptance(AbstractCommandLineInterface):
    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli task cancel_acceptance: error:"

        if args.parallelism is not None and not args.yes:
            print(
                f"{COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず'--yes'を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            return

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

        assign_last_acceptor = not args.not_assign and args.assigned_acceptor_user_id is None

        dict_task_query = annofabcli.common.cli.get_json_from_args(args.task_query)
        task_query: Optional[TaskQuery] = TaskQuery.from_dict(dict_task_query) if dict_task_query is not None else None

        super().validate_project(args.project_id, [ProjectMemberRole.OWNER])
        main_obj = CancelAcceptanceMain(self.service, all_yes=args.yes)
        main_obj.cancel_acceptance_for_task_list(
            args.project_id,
            task_id_list,
            acceptor_user_id=args.assigned_acceptor_user_id,
            assign_last_acceptor=assign_last_acceptor,
            task_query=task_query,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CancelAcceptance(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

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

    argument_parser.add_task_query()

    parser.add_argument(
        "--parallelism", type=int, help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず'--yes'を指定してください。指定しない場合は、逐次的に処理します。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "cancel_acceptance"
    subcommand_help = "受入が完了したタスクに対して、受入を取り消します。"
    description = "受入が完了したタスクに対して、受入を取り消します。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
