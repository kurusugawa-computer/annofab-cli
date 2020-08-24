import argparse
import logging
import multiprocessing
from dataclasses import dataclass
from functools import partial
from typing import List, Optional, Tuple

import annofabapi
import requests
from annofabapi.dataclass.task import Task
from annofabapi.models import ProjectMemberRole, TaskPhase, TaskStatus
from dataclasses_json import dataclass_json

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    prompt_yesnoall,
)

logger = logging.getLogger(__name__)


@dataclass_json
@dataclass(frozen=True)
class TaskQuery:
    phase: Optional[TaskPhase] = None
    status: Optional[TaskStatus] = None


class ChangeOperatorMain:
    def __init__(self, service: annofabapi.Resource, all_yes: bool):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.all_yes = all_yes

    def confirm_processing(self, confirm_message: str) -> bool:
        """
        `all_yes`属性を見て、処理するかどうかユーザに問い合わせる。
        "ALL"が入力されたら、`all_yes`属性をTrueにする

        Args:
            task_id: 処理するtask_id
            confirm_message: 確認メッセージ

        Returns:
            True: Yes, False: No

        """
        if self.all_yes:
            return True

        yes, all_yes = prompt_yesnoall(confirm_message)

        if all_yes:
            self.all_yes = True

        return yes

    def confirm_change_operator(self, task: Task) -> bool:
        confirm_message = f"task_id = {task.task_id} のタスクの担当者を変更しますか？"
        return self.confirm_processing(confirm_message)

    def change_operator_for_task(
        self,
        project_id: str,
        task_id: str,
        task_index: int,
        task_query: TaskQuery,
        new_account_id: Optional[str] = None,
    ) -> bool:
        logging_prefix = f"{task_index} 件目"
        dict_task, _ = self.service.api.get_task(project_id, task_id)
        task: Task = Task.from_dict(dict_task)  # type: ignore

        if task.account_id is not None:
            now_user_id = self.facade.get_user_id_from_account_id(project_id, task.account_id)
        else:
            now_user_id = None

        logger.debug(
            f"{logging_prefix} : task_id = {task.task_id}, "
            f"status = {task.status.value}, "
            f"phase = {task.phase.value}, "
            f"user_id = {now_user_id}"
        )

        if task_query.status is not None:
            if task.status != task_query.status:
                logger.debug(
                    f"{logging_prefix} : task_id = {task_id} : タスクのstatusが {task_query.status.value} でないので、スキップします。"
                )
                return False

        if task_query.phase is not None:
            if task.phase != task_query.phase:
                logger.debug(
                    f"{logging_prefix} : task_id = {task_id} : タスクのphaseが {task_query.phase.value} でないので、スキップします。"
                )
                return False

        if task.status in [TaskStatus.COMPLETE, TaskStatus.WORKING]:
            logger.warning(f"{logging_prefix} : task_id = {task_id} : タスクのstatusがworking or complete なので、担当者を変更できません。")
            return False

        if not self.confirm_change_operator(task):
            return False

        try:
            # 担当者を変更する
            self.facade.change_operator_of_task(project_id, task_id, new_account_id)
            logger.debug(f"{logging_prefix} : task_id = {task_id}, phase={dict_task['phase']} のタスクの担当者を変更しました。")
            return True

        except requests.exceptions.HTTPError as e:
            logger.warning(e)
            logger.warning(f"{logging_prefix} : task_id = {task_id} の担当者を変更するのに失敗しました。")
            return False

    def change_operator_for_task_wrapper(
        self, tpl: Tuple[int, str], project_id: str, task_query: TaskQuery, new_account_id: Optional[str] = None,
    ) -> bool:
        task_index, task_id = tpl
        return self.change_operator_for_task(
            project_id=project_id,
            task_id=task_id,
            task_index=task_index,
            task_query=task_query,
            new_account_id=new_account_id,
        )

    def change_operator(
        self,
        project_id: str,
        task_id_list: List[str],
        new_user_id: Optional[str] = None,
        task_query: Optional[TaskQuery] = None,
        parallelism: Optional[int] = None,
    ):
        """
        検査コメントを付与して、タスクを差し戻す
        Args:
            project_id:
            task_id_list:
            new_user_id: 新しく担当するユーザのuser_id。Noneの場合タスクの担当者は未割り当てにする。

        """
        if task_query is None:
            task_query = TaskQuery()

        if new_user_id is not None:
            new_account_id = self.facade.get_account_id_from_user_id(project_id, new_user_id)
            if new_account_id is None:
                logger.error(f"ユーザ '{new_user_id}' のaccount_idが見つかりませんでした。終了します。")
                return
            else:
                logger.info(f" {len(task_id_list)}のタスクの担当者を、{new_user_id}に変更します。")
        else:
            new_account_id = None
            logger.info(f" {len(task_id_list)}のタスクの担当者を未割り当てに変更します。")

        success_count = 0

        if parallelism is not None:
            partial_func = partial(
                self.change_operator_for_task_wrapper,
                project_id=project_id,
                task_query=task_query,
                new_account_id=new_account_id,
            )
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(partial_func, enumerate(task_id_list))
                success_count = len([e for e in result_bool_list if e])

        else:
            # 逐次処理
            for task_index, task_id in enumerate(task_id_list):
                result = self.change_operator_for_task(
                    project_id, task_id, task_index=task_index, task_query=task_query, new_account_id=new_account_id
                )
                if result:
                    success_count += 1

        logger.info(f"{success_count} / {len(task_id_list)} 件 タスクの担当者を変更しました。")


class ChangeOperator(AbstractCommandLineInterface):
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

        dict_task_query = annofabcli.common.cli.get_json_from_args(args.task_query)
        task_query: Optional[TaskQuery] = TaskQuery.from_dict(dict_task_query) if dict_task_query is not None else None

        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])

        main_obj = ChangeOperatorMain(self.service, all_yes=self.all_yes)
        main_obj.change_operator(project_id, task_id_list=task_id_list, new_user_id=user_id, task_query=task_query, parallelism=args.parallelism)


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeOperator(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    assign_group = parser.add_mutually_exclusive_group(required=True)

    assign_group.add_argument("-u", "--user_id", type=str, help="タスクを新しく担当するユーザのuser_idを指定してください。")

    assign_group.add_argument("--not_assign", action="store_true", help="指定した場合、タスクの担当者は未割り当てになります。")

    parser.add_argument(
        "-tq",
        "--task_query",
        type=str,
        help="タスクの検索クエリをJSON形式で指定します。指定しない場合はすべてのタスクを取得します。"
        "`file://`を先頭に付けると、JSON形式のファイルを指定できます。"
        "使用できるキーは、phase, status のみです。",
    )

    parser.add_argument("--parallelism", type=int, help="並列度。指定する場合は必ず'--yes'を指定してください。指定しない場合は、逐次的に処理します。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "change_operator"
    subcommand_help = "タスクの担当者を変更します。"
    description = "タスクの担当者を変更します。ただし、作業中/受入完了状態のタスクに対しては変更できません。"
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
