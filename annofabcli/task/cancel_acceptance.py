from __future__ import annotations

import argparse
import logging
import multiprocessing
import sys
from dataclasses import dataclass
from functools import partial
from typing import Any, List, Optional, Tuple

import annofabapi
import more_itertools
import requests
from annofabapi.dataclass.task import Task
from annofabapi.models import ProjectMemberRole, TaskPhase, TaskStatus

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    AbstractCommandLineWithConfirmInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery, match_task_with_query
from annofabcli.common.utils import add_dryrun_prefix

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class User:
    account_id: str
    user_id: str
    username: str


class CancelAcceptanceMain(AbstractCommandLineWithConfirmInterface):
    def __init__(self, service: annofabapi.Resource, project_id: str, all_yes: bool = False):
        self.service = service
        self.project_id = project_id
        self.facade = AnnofabApiFacade(service)

        self._project_members_dict: Optional[dict[str, dict[str, Any]]] = None
        """プロジェクトメンバー情報を保持する変数"""

        AbstractCommandLineWithConfirmInterface.__init__(self, all_yes)

    def get_project_member_from_account_id(self, account_id: str) -> Optional[dict[str, Any]]:
        """account_idからプロジェクトメンバを取得します。"""
        if self._project_members_dict is None:
            project_member_list = self.service.wrapper.get_all_project_members(self.project_id)
            self._project_members_dict = {e["account_id"]: e for e in project_member_list}

        return self._project_members_dict.get(account_id)

    def cancel_acceptance_for_task(
        self,
        task_id: str,
        acceptor: Optional[User] = None,
        assign_last_acceptor: bool = True,
        task_query: Optional[TaskQuery] = None,
        task_index: Optional[int] = None,
        dryrun: bool = False,
    ) -> bool:
        logging_prefix = f"{task_index + 1} 件目" if task_index is not None else ""

        try:
            task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
            if task is None:
                logger.warning(f"{logging_prefix}: task_id='{task_id}'のタスクは存在しないので、スキップします。")
                return False

            if task["phase"] != TaskPhase.ACCEPTANCE.value or task["status"] != TaskStatus.COMPLETE.value:
                logger.warning(
                    f"{logging_prefix}: task_id = {task_id} は受入完了でありません。"
                    f"status = {task['status']}, phase={task['phase']}"
                )
                return False

            actual_acceptor: Optional[User] = None
            if assign_last_acceptor:
                # 最後の受入フェーズの担当者の情報を取得する
                acceptor_account_id = task["account_id"]
                if acceptor_account_id is not None:
                    member = self.get_project_member_from_account_id(acceptor_account_id)
                    if member is not None:
                        actual_acceptor = User(
                            account_id=member["account_id"], user_id=member["user_id"], username=member["username"]
                        )
                    else:
                        logger.warning(
                            f"{logging_prefix}: task_id = {task_id} の最後の受入フェーズを担当したユーザ"
                            f"（account_id='{acceptor_account_id}'）は、プロジェクトメンバーでないので、担当者を割り当てません。"
                        )
            else:
                actual_acceptor = acceptor

            if not match_task_with_query(Task.from_dict(task), task_query):
                logger.debug(f"{logging_prefix} : task_id = {task_id} : TaskQueryの条件にマッチしないため、スキップします。")
                return False

            if not self.confirm_processing(f"{logging_prefix}: task_id = {task_id} のタスクの受入完了状態を取り消しますか？ "):
                return False

            logger.debug(
                f"{logging_prefix}: task_id = {task_id} のタスクの受入完了状態を取り消します。"
                + (
                    f"タスクの担当者は {actual_acceptor.username}({actual_acceptor.user_id}) です。"
                    if actual_acceptor is not None
                    else "タスクの担当者は未割り当てです。"
                )  # noqa: E501
            )
            operator_account_id = actual_acceptor.account_id if actual_acceptor is not None else None
            if not dryrun:
                self.service.wrapper.cancel_completed_task(
                    self.project_id, task_id, operator_account_id=operator_account_id
                )
            logger.info(f"{logging_prefix} : task_id = {task_id} の受け入れ取り消しが成功しました。")
            return True

        except requests.exceptions.HTTPError:
            logger.warning(f"{logging_prefix} : task_id = {task_id} の受け入れ取り消しに失敗しました。", exc_info=True)
            return False

    def cancel_acceptance_for_wrapper(
        self,
        tpl: Tuple[int, str],
        acceptor: Optional[User] = None,
        assign_last_acceptor: bool = True,
        task_query: Optional[TaskQuery] = None,
        dryrun: bool = False,
    ) -> bool:
        task_index, task_id = tpl
        try:
            return self.cancel_acceptance_for_task(
                task_id=task_id,
                acceptor=acceptor,
                assign_last_acceptor=assign_last_acceptor,
                task_query=task_query,
                task_index=task_index,
                dryrun=dryrun,
            )
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"タスク'{task_id}'の受け入れ取り消しに失敗しました。", exc_info=True)
            return False

    def cancel_acceptance_for_task_list(
        self,
        task_id_list: List[str],
        acceptor: Optional[User] = None,
        assign_last_acceptor: bool = True,
        task_query: Optional[TaskQuery] = None,
        parallelism: Optional[int] = None,
        dryrun: bool = False,
    ):
        """
        タスクを受入取り消しする

        Args:
            project_id:
            task_id_list: 受け入れ取り消しするtask_id_list
            acceptor_user_id: 再度受入を担当させたいユーザのuser_id. Noneならば、未割り当てにする
            assign_last_acceptor: trueなら最後の受入担当者に割り当てる
        """
        assert not (assign_last_acceptor and acceptor is not None)
        logger.info(f"受け入れを取り消すタスク数: {len(task_id_list)}")

        if task_query is not None:
            task_query = self.facade.set_account_id_of_task_query(self.project_id, task_query)

        success_count = 0
        if parallelism is not None:
            partial_func = partial(
                self.cancel_acceptance_for_wrapper,
                acceptor=acceptor,
                assign_last_acceptor=assign_last_acceptor,
                task_query=task_query,
                dryrun=dryrun,
            )
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(partial_func, enumerate(task_id_list))
                success_count = len([e for e in result_bool_list if e])

        else:
            # 逐次処理
            success_count = 0
            for task_index, task_id in enumerate(task_id_list):
                try:
                    result = self.cancel_acceptance_for_task(
                        task_id,
                        task_index=task_index,
                        acceptor=acceptor,
                        assign_last_acceptor=assign_last_acceptor,
                        task_query=task_query,
                        dryrun=dryrun,
                    )
                    if result:
                        success_count += 1
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"タスク'{task_id}'の受け入れ取り消しに失敗しました。", exc_info=True)
                    continue

        logger.info(f"{success_count} / {len(task_id_list)} 件 受け入れ取り消しに成功しました。")


class CancelAcceptance(AbstractCommandLineInterface):
    COMMON_MESSAGE = "annofabcli task cancel_acceptance: error:"

    @classmethod
    def validate(cls, args: argparse.Namespace) -> bool:

        if args.parallelism is not None and not args.yes:
            print(
                f"{cls.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、'--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        if args.dryrun:
            add_dryrun_prefix(logger)

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

        assigned_acceptor_user_id: Optional[str] = args.assigned_acceptor_user_id

        # 最後の受入フェーズの担当者に割り当てるか否か
        assign_last_acceptor = not args.not_assign and assigned_acceptor_user_id is None

        # 受入担当者の情報を取得する
        acceptor: Optional[User] = None  # 受入担当者
        if assigned_acceptor_user_id is not None:
            project_member_list = self.service.wrapper.get_all_project_members(args.project_id)
            member = more_itertools.first_true(
                project_member_list, pred=lambda e: e["user_id"] == assigned_acceptor_user_id
            )
            if member is None:
                print(
                    f"{self.COMMON_MESSAGE} argument --assigned_acceptor_user_id: プロジェクトメンバーに user_id='{assigned_acceptor_user_id}'メンバーは存在しません",  # noqa: E501
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            else:
                acceptor = User(account_id=member["account_id"], user_id=member["user_id"], username=member["username"])

        dict_task_query = annofabcli.common.cli.get_json_from_args(args.task_query)
        task_query: Optional[TaskQuery] = TaskQuery.from_dict(dict_task_query) if dict_task_query is not None else None

        super().validate_project(args.project_id, [ProjectMemberRole.OWNER])
        main_obj = CancelAcceptanceMain(self.service, project_id=args.project_id, all_yes=args.yes)
        main_obj.cancel_acceptance_for_task_list(
            task_id_list,
            assign_last_acceptor=assign_last_acceptor,
            acceptor=acceptor,
            task_query=task_query,
            parallelism=args.parallelism,
            dryrun=args.dryrun,
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
        help="対象のタスクのtask_idを指定します。 ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
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
        "--parallelism", type=int, help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。"
    )

    parser.add_argument("--dryrun", action="store_true", help="取り消しが行われた時の結果を表示しますが、実際は受け入れを取り消しません。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "cancel_acceptance"
    subcommand_help = "受入が完了したタスクに対して、受入を取り消します。"
    description = "受入が完了したタスクに対して、受入を取り消します。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
