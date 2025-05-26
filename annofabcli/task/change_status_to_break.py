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
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery, match_task_with_query

logger = logging.getLogger(__name__)


class ChangeStatusToBreakMain(CommandLineWithConfirm):
    def __init__(self, service: annofabapi.Resource, all_yes: bool) -> None:  # noqa: FBT001
        super().__init__(all_yes)
        self.service = service
        self.facade = AnnofabApiFacade(service)

    def confirm_change_status_to_break(self, task: Task) -> bool:
        confirm_message = f"task_id = {task.task_id} のタスクのステータスを休憩中に変更しますか？"
        return self.confirm_processing(confirm_message)

    def change_status_to_break_for_task(
        self,
        project_id: str,
        task_id: str,
        task_index: Optional[int] = None,
        task_query: Optional[TaskQuery] = None,
    ) -> bool:
        logging_prefix = f"{task_index + 1} 件目" if task_index is not None else ""
        dict_task = self.service.wrapper.get_task_or_none(project_id, task_id)
        if dict_task is None:
            logger.warning(f"{logging_prefix}: task_id ='{task_id}' のタスクは存在しないので、スキップします。")
            return False

        task: Task = Task.from_dict(dict_task)

        if not match_task_with_query(task, task_query):
            logger.debug(f"{logging_prefix} : task_id = {task_id} : `--task_query` の条件にマッチしないため、スキップします。task_query={task_query}")
            return False

        if task.status not in (TaskStatus.WORKING, TaskStatus.ON_HOLD):
            logger.warning(f"{logging_prefix}: task_id = '{task_id}' のタスクは作業中でも保留中でもないので、スキップします。")
            return False

        if not self.confirm_change_status_to_break(task):
            return False

        try:
            # ステータスを変更する

            # 保留中なら一度作業中にする(APIの都合上)
            if task.status == TaskStatus.ON_HOLD:
                self.service.wrapper.change_task_status_to_working(project_id, task_id)

            self.service.wrapper.change_task_status_to_break(project_id, task_id)
            logger.debug(f"{logging_prefix} : task_id = {task_id}, タスクのステータスを休憩中に変更しました。")
            return True  # noqa: TRY300
        except requests.exceptions.HTTPError:
            logger.warning(f"{logging_prefix} : task_id = {task_id} のステータスの変更に失敗しました。", exc_info=True)
            return False

    def change_status_to_break_for_task_wrapper(
        self,
        tpl: tuple[int, str],
        project_id: str,
        task_query: Optional[TaskQuery] = None,
    ) -> bool:
        task_index, task_id = tpl
        try:
            return self.change_status_to_break_for_task(
                project_id=project_id,
                task_id=task_id,
                task_index=task_index,
                task_query=task_query,
            )
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"タスク'{task_id}'のステータスの変更に失敗しました。", exc_info=True)
            return False

    def change_status_to_break(  # noqa: ANN201
        self,
        project_id: str,
        task_id_list: list[str],
        task_query: Optional[TaskQuery] = None,
        parallelism: Optional[int] = None,
    ):
        """
        タスクのステータスを休憩中に変更する。
        Args:
            project_id:
            task_id_list:
            task_query:
            parallelism: 並列度

        """

        if task_query is not None:
            task_query = self.facade.set_account_id_of_task_query(project_id, task_query)

        logger.info(f"{len(task_id_list)} 件のタスクのステータスを、休憩中に変更します。")

        success_count = 0

        if parallelism is not None:
            partial_func = partial(
                self.change_status_to_break_for_task_wrapper,
                project_id=project_id,
                task_query=task_query,
            )
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(partial_func, enumerate(task_id_list))
                success_count = len([e for e in result_bool_list if e])

        else:
            # 逐次処理
            for task_index, task_id in enumerate(task_id_list):
                try:
                    result = self.change_status_to_break_for_task(
                        project_id,
                        task_id,
                        task_index=task_index,
                        task_query=task_query,
                    )
                    if result:
                        success_count += 1
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"タスク'{task_id}'のステータスの変更に失敗しました。", exc_info=True)
                    continue

        logger.info(f"{success_count} / {len(task_id_list)} 件 タスクのステータスを休憩中に変更しました。")


class ChangeStatusToBreak(CommandLine):
    """
    タスクのステータスを休憩中に変更する。
    """

    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli task change_status_to_break: error:"  # noqa: N806

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

        dict_task_query = annofabcli.common.cli.get_json_from_args(args.task_query)
        task_query: Optional[TaskQuery] = TaskQuery.from_dict(dict_task_query) if dict_task_query is not None else None

        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER, ProjectMemberRole.WORKER])

        main_obj = ChangeStatusToBreakMain(self.service, all_yes=self.all_yes)
        main_obj.change_status_to_break(
            project_id,
            task_id_list,
            task_query=task_query,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeStatusToBreak(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    argument_parser.add_task_query()

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "change_status_to_break"
    subcommand_help = "タスクのステータスを休憩中に変更します。"
    description = "タスクのステータスを休憩中に変更します。ただし、操作対象のタスクは作業中か保留中である必要があります。"
    epilog = "アノテータ、チェッカーまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
