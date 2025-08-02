import argparse
import logging
import multiprocessing
import sys
from functools import partial
from typing import Optional

import annofabapi
import requests
from annofabapi.dataclass.task import Task
from annofabapi.models import ProjectMemberRole, TaskStatus

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
    prompt_yesnoall,
)
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery, match_task_with_query

logger = logging.getLogger(__name__)


class ChangeOperatorMain:
    def __init__(self, service: annofabapi.Resource, *, all_yes: bool, include_on_hold: bool = False) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.all_yes = all_yes
        self.include_on_hold = include_on_hold

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
        confirm_message = f"task_id='{task.task_id}' のタスクの担当者を変更しますか？"
        return self.confirm_processing(confirm_message)

    def change_operator_for_task(  # noqa: PLR0911
        self,
        project_id: str,
        task_id: str,
        new_account_id: Optional[str] = None,
        task_query: Optional[TaskQuery] = None,
        task_index: Optional[int] = None,
    ) -> bool:
        logging_prefix = f"{task_index + 1} 件目" if task_index is not None else ""
        dict_task = self.service.wrapper.get_task_or_none(project_id, task_id)
        if dict_task is None:
            logger.warning(f"{logging_prefix} :: task_id='{task_id}'のタスクは存在しないので、スキップします。")
            return False

        task: Task = Task.from_dict(dict_task)

        now_user_id = None
        if task.account_id is not None:
            now_user_id = self.facade.get_user_id_from_account_id(project_id, task.account_id)

        logger.debug(f"{logging_prefix} :: task_id='{task.task_id}', status='{task.status.value}', phase='{task.phase.value}', phase_stage='{task.phase_stage}', user_id='{now_user_id}'")
        if task.account_id == new_account_id:
            logger.info(f"{logging_prefix} :: task_id='{task_id}' :: タスクの担当者はすでにuser_id='{now_user_id}'のユーザーです。担当者を変更する必要がないのでスキップします。")
            return False

        if task.status in [TaskStatus.COMPLETE, TaskStatus.WORKING]:
            logger.warning(f"{logging_prefix} :: task_id='{task_id}' :: タスクが作業中状態または完了状態なので、担当者を変更できません。 :: status='{task.status.value}'")
            return False

        if task.status == TaskStatus.ON_HOLD and not self.include_on_hold:
            logger.warning(
                f"{logging_prefix} :: task_id='{task_id}' :: タスクが保留中状態なので、担当者を変更できません。保留中状態のタスクの担当者も変更する場合は、'--include_on_hold'を指定してください。"
            )
            return False

        if not match_task_with_query(task, task_query):
            logger.debug(f"{logging_prefix} :: task_id='{task_id}' :: `--task_query` の条件にマッチしないため、スキップします。task_query='{task_query}'")
            return False

        if not self.confirm_change_operator(task):
            return False

        try:
            # 担当者を変更する
            self.service.wrapper.change_task_operator(project_id, task_id, operator_account_id=new_account_id)
            logger.debug(f"{logging_prefix} :: task_id='{task_id}'であるタスクの担当者を変更しました。 :: phase='{dict_task['phase']}'")
            return True  # noqa: TRY300

        except requests.exceptions.HTTPError:
            logger.warning(f"{logging_prefix} :: task_id='{task_id}'である担当者を変更するのに失敗しました。", exc_info=True)
            return False

    def change_operator_for_task_wrapper(
        self,
        tpl: tuple[int, str],
        project_id: str,
        task_query: Optional[TaskQuery] = None,
        new_account_id: Optional[str] = None,
    ) -> bool:
        task_index, task_id = tpl
        try:
            return self.change_operator_for_task(
                project_id=project_id,
                task_id=task_id,
                task_index=task_index,
                task_query=task_query,
                new_account_id=new_account_id,
            )
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"task_id='{task_id}'であるタスク担当者の変更に失敗しました。", exc_info=True)
            return False

    def change_operator(
        self,
        project_id: str,
        task_id_list: list[str],
        *,
        new_user_id: Optional[str] = None,
        task_query: Optional[TaskQuery] = None,
        parallelism: Optional[int] = None,
    ) -> None:
        """
        指定した複数のタスクの担当者を変更します。

        Args:
            project_id:
            task_id_list:
            new_user_id: 新しく担当するユーザのuser_id。Noneの場合タスクの担当者は未割り当てにする。

        """
        if task_query is not None:
            task_query = self.facade.set_account_id_of_task_query(project_id, task_query)

        if new_user_id is not None:
            new_account_id = self.facade.get_account_id_from_user_id(project_id, new_user_id)
            if new_account_id is None:
                logger.error(f"user_id='{new_user_id}'であるユーザーは、project_id='{project_id}'のプロジェクトのメンバーではありません。終了します。")
                return
            else:
                logger.info(f"{len(task_id_list)} 件のタスクの担当者を、user_id='{new_user_id}'のユーザーに変更します。")
        else:
            new_account_id = None
            logger.info(f"{len(task_id_list)} 件のタスクの担当者を「未割り当て」に変更します。")

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
                try:
                    result = self.change_operator_for_task(project_id, task_id, task_index=task_index, task_query=task_query, new_account_id=new_account_id)
                    if result:
                        success_count += 1
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"task_id='{task_id}'であるタスクの担当者の変更に失敗しました。", exc_info=True)
                    continue

        logger.info(f"{success_count} / {len(task_id_list)} 件 タスクの担当者を変更しました。")


class ChangeOperator(CommandLine):
    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli task change_operator: error:"  # noqa: N806

        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず ``--yes`` を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        if args.user_id is not None:
            user_id = args.user_id
        elif args.not_assign:
            user_id = None
        else:
            logger.error("タスクの担当者の指定方法が正しくありません。")
            return

        dict_task_query = annofabcli.common.cli.get_json_from_args(args.task_query)
        task_query: Optional[TaskQuery] = TaskQuery.from_dict(dict_task_query) if dict_task_query is not None else None

        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])

        main_obj = ChangeOperatorMain(self.service, all_yes=self.all_yes, include_on_hold=args.include_on_hold)
        main_obj.change_operator(
            project_id,
            task_id_list=task_id_list,
            new_user_id=user_id,
            task_query=task_query,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeOperator(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    assign_group = parser.add_mutually_exclusive_group(required=True)

    assign_group.add_argument("-u", "--user_id", type=str, help="タスクを新しく担当するユーザのuser_idを指定してください。")

    assign_group.add_argument("--not_assign", action="store_true", help="指定した場合、タスクの担当者は未割り当てになります。")

    argument_parser.add_task_query()

    parser.add_argument(
        "--include_on_hold",
        action="store_true",
        help="指定した場合、保留中のタスクの担当者も変更します。指定しない場合、保留中のタスクはスキップされます。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "change_operator"
    subcommand_help = "タスクの担当者を変更します。"
    description = "タスクの担当者を変更します。作業中状態、完了状態のタスクは、担当者を変更できません。保留中状態のタスクは、デフォルトでは担当者を変更できません。"
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
