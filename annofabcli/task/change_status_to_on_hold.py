from __future__ import annotations

import argparse
import logging
import multiprocessing
import sys
import uuid
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


class ChangingStatusToOnHoldMain(CommandLineWithConfirm):
    def __init__(self, service: annofabapi.Resource, project_id: str, *, all_yes: bool) -> None:
        super().__init__(all_yes)
        self.service = service
        self.project_id = project_id
        self.facade = AnnofabApiFacade(service)

    def confirm_change_status_to_on_hold(self, task: Task) -> bool:
        user_id = None
        if task.account_id is not None:
            user_id = self.facade.get_user_id_from_account_id(self.project_id, task.account_id)

        confirm_message = f"task_id='{task.task_id}' のタスクのステータスを保留中に変更しますか？(status='{task.status.value}, phase='{task.phase.value}', user_id='{user_id}')"
        return self.confirm_processing(confirm_message)

    def add_comment(self, task: Task, comment: str) -> None:
        """
        先頭の入力データに対して、保留コメントを付与します。

        タスクは作業中状態である必要があります。
        """
        request_body = [
            {
                "comment": comment,
                "comment_id": str(uuid.uuid4()),
                "phase": task.phase.value,
                "phase_stage": task.phase_stage,
                "comment_type": "onhold",
                "account_id": self.service.api.account_id,
                "comment_node": {"status": "open", "_type": "Root"},
                "_type": "Put",
            }
        ]
        input_data_id = task.input_data_id_list[0]
        self.service.api.batch_update_comments(self.project_id, task.task_id, input_data_id, request_body=request_body)

    def change_status_to_on_hold_for_task(
        self,
        task_id: str,
        *,
        comment: Optional[str] = None,
        task_index: Optional[int] = None,
        task_query: Optional[TaskQuery] = None,
    ) -> bool:
        """
        Args:
            comment: 保留用のコメント

        """

        def preprocess() -> bool:
            if not match_task_with_query(task, task_query):
                logger.debug(f"{logging_prefix} : task_id = {task_id} : `--task_query` の条件にマッチしないため、スキップします。 :: task_query={task_query}")
                return False

            if task.status not in [TaskStatus.NOT_STARTED, TaskStatus.BREAK]:
                logger.warning(f"{logging_prefix}: task_id = '{task_id}' のタスクのステータスが未着手または休憩中でないので、スキップします。 :: status='{task.status.value}'")
                return False

            if not self.confirm_change_status_to_on_hold(task):  # noqa: SIM103
                return False

            return True

        logging_prefix = f"{task_index + 1} 件目" if task_index is not None else ""
        dict_task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if dict_task is None:
            logger.warning(f"{logging_prefix}: task_id ='{task_id}' のタスクは存在しないので、スキップします。")
            return False

        task: Task = Task.from_dict(dict_task)

        if not preprocess():
            return False

        task_user_id = None
        if task.account_id is not None:
            task_user_id = self.facade.get_user_id_from_account_id(self.project_id, task.account_id)

        logger.debug(f"{logging_prefix}: task_id='{task_id}'のステータスを保留中に変更します。 :: status='{task.status.value}, phase='{task.phase.value}', user_id='{task_user_id}'")

        task_last_updated_datetime = None

        try:
            # 休憩中または未着手状態から保留中状態にするには、一旦作業中状態に変更する必要がある
            # 作業中状態にするには、担当者が自分でないといけないので、担当者も自分自身に変更する
            if task.account_id != self.service.api.account_id:
                updated_task = self.service.wrapper.change_task_operator(self.project_id, task.task_id, self.service.api.account_id)
                task_last_updated_datetime = updated_task["updated_datetime"]
                logger.debug(f"{logging_prefix}: task_id='{task_id}' のタスクの担当者を'{task_user_id}'から自分自身に変更しました。")

            updated_task = self.service.wrapper.change_task_status_to_working(self.project_id, task_id, last_updated_datetime=task_last_updated_datetime)
            task_last_updated_datetime = updated_task["updated_datetime"]
            logger.debug(f"{logging_prefix}: task_id='{task_id}'のタスクのステータスを作業中に変更しました。")

        except requests.exceptions.HTTPError:
            logger.warning(f"{logging_prefix} : task_id='{task_id}' のステータスを作業中に変更するのに失敗しました。", exc_info=True)
            return False

        # 保留コメントを付与する
        if comment is not None:
            try:
                self.add_comment(task, comment)
            except requests.exceptions.HTTPError:
                logger.warning(f"{logging_prefix} : task_id='{task_id}' に保留コメントを付与するのに失敗しました。", exc_info=True)
                # 作業中状態のまま放置すると、作業時間が増え続けるので、作業中状態ならば休憩中状態に変更する
                self.service.wrapper.change_task_status_to_break(self.project_id, task_id)
                logger.warning(f"{logging_prefix} : task_id='{task_id}' のステータスを休憩中に変更しました。")
                return False

        try:
            # ステータスを保留中状態に変更する
            self.service.wrapper.change_task_status_to_on_hold(self.project_id, task_id, last_updated_datetime=task_last_updated_datetime)
            logger.debug(f"{logging_prefix} : task_id='{task_id}' のタスクのステータスを保留中に変更しました。")
            return True  # noqa: TRY300

        except requests.exceptions.HTTPError:
            logger.warning(f"{logging_prefix} : task_id = {task_id} のステータスの保留中に変更するのに失敗しました。", exc_info=True)
            # 作業中状態のまま放置すると、作業時間が増え続けるので、作業中状態ならば休憩中状態に変更する
            self.service.wrapper.change_task_status_to_break(self.project_id, task_id)
            logger.warning(f"{logging_prefix} : task_id='{task_id}' のステータスを休憩中に変更しました。")
            return False

    def change_status_to_on_hold_for_task_wrapper(
        self,
        tpl: tuple[int, str],
        *,
        comment: Optional[str] = None,
        task_query: Optional[TaskQuery] = None,
    ) -> bool:
        task_index, task_id = tpl
        try:
            return self.change_status_to_on_hold_for_task(
                task_id=task_id,
                comment=comment,
                task_index=task_index,
                task_query=task_query,
            )
        except Exception:
            logger.warning(f"タスク'{task_id}'のステータスの変更に失敗しました。", exc_info=True)
            return False

    def change_status_to_on_hold(  # noqa: ANN201
        self,
        task_id_list: list[str],
        *,
        comment: Optional[str] = None,
        task_query: Optional[TaskQuery] = None,
        parallelism: Optional[int] = None,
    ):
        """
        タスクのステータスを保留中に変更する。

        Args:
            task_id_list:
            task_query:
            parallelism: 並列度

        """

        if task_query is not None:
            task_query = self.facade.set_account_id_of_task_query(self.project_id, task_query)

        logger.info(f"{len(task_id_list)} 件のタスクのステータスを、保留中に変更します。")

        success_count = 0

        if parallelism is not None:
            partial_func = partial(
                self.change_status_to_on_hold_for_task_wrapper,
                comment=comment,
                task_query=task_query,
            )
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(partial_func, enumerate(task_id_list))
                success_count = len([e for e in result_bool_list if e])

        else:
            # 逐次処理
            for task_index, task_id in enumerate(task_id_list):
                try:
                    result = self.change_status_to_on_hold_for_task(
                        task_id,
                        comment=comment,
                        task_index=task_index,
                        task_query=task_query,
                    )
                    if result:
                        success_count += 1
                except Exception:
                    logger.warning(f"タスク'{task_id}'のステータスの変更に失敗しました。", exc_info=True)
                    continue

        logger.info(f"{success_count} / {len(task_id_list)} 件 タスクのステータスを保留中に変更しました。")


class ChangingStatusToOnHold(CommandLine):
    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli task change_status_to_on_hold: error:"  # noqa: N806

        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、``--yes`` を指定してください。",
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

        main_obj = ChangingStatusToOnHoldMain(self.service, project_id=project_id, all_yes=self.all_yes)
        main_obj.change_status_to_on_hold(
            task_id_list,
            comment=args.comment,
            task_query=task_query,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangingStatusToOnHold(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    argument_parser.add_task_query()

    parser.add_argument("--comment", type=str, help="保留コメントを指定してください。保留コメントは先頭の入力データに付与します。")

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "change_status_to_on_hold"
    subcommand_help = "タスクのステータスを保留に変更します。"
    description = "タスクのステータスを保留に変更します。ただし、操作対象のタスクのステータスは休憩中か未着手である必要があります。"
    epilog = "アノテータ、チェッカーまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
