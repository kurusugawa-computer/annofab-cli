from __future__ import annotations

import argparse
import logging
from typing import Any, Optional

import annofabapi
from annofabapi.dataclass.task import Task
from annofabapi.models import ProjectMemberRole, TaskStatus

import annofabcli
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery, match_task_with_query
from annofabcli.common.utils import add_dryrun_prefix

logger = logging.getLogger(__name__)


class DeleteTaskMain(CommandLineWithConfirm):
    def __init__(
        self,
        service: annofabapi.Resource,
        project_id: str,
        *,
        all_yes: bool = False,
        dryrun: bool = False,
        force: bool = False,
        should_delete_input_data: bool = False,
    ) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.project_id = project_id
        self.dryrun = dryrun
        self.force = force
        self.should_delete_input_data = should_delete_input_data

        CommandLineWithConfirm.__init__(self, all_yes)

    def delete_supplementary_data_list(self, task_id: str, input_data_id: str) -> int:
        supplementary_data_list, _ = self.service.api.get_supplementary_data_list(self.project_id, input_data_id)
        if len(supplementary_data_list) == 0:
            return 0

        logger.debug(f"task_id='{task_id}', input_data_id='{input_data_id}' :: 補助情報 {len(supplementary_data_list)} 件を削除します。")

        deleted_count = 0
        for supplementary_data in supplementary_data_list:
            supplementary_data_id = supplementary_data["supplementary_data_id"]
            try:
                if not self.dryrun:
                    self.service.api.delete_supplementary_data(self.project_id, input_data_id=input_data_id, supplementary_data_id=supplementary_data_id)
                logger.debug(
                    f"task_id='{task_id}', input_data_id='{input_data_id}' :: 補助情報を削除しました。 :: "
                    f"supplementary_data_id='{supplementary_data_id}', "
                    f"supplementary_data_name='{supplementary_data['supplementary_data_name']}'"
                )
                deleted_count += 1
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    f"task_id='{task_id}', input_data_id='{input_data_id}' :: 補助情報の削除に失敗しました。 :: "
                    f"supplementary_data_id='{supplementary_data_id}', "
                    f"supplementary_data_name='{supplementary_data['supplementary_data_name']}'",
                    exc_info=True,
                )
                continue

        logger.debug(f"task_id='{task_id}', input_data_id='{input_data_id}' :: 補助情報 {deleted_count} / {len(supplementary_data_list)} 件を削除しました。")

        return deleted_count

    def confirm_deleting_input_data(self, task_id: str, input_data_id: str, input_data_name: str) -> bool:
        message_for_confirm = f"task_id='{task_id}'のタスクから参照されている入力データと補助情報を削除しますか？  :: input_data_id='{input_data_id}', input_data_name='{input_data_name}'"
        return self.confirm_processing(message_for_confirm)

    def delete_input_data_and_supplementary_data(self, task_id: str, input_data_id: str) -> bool:
        """タスクから使われている入力データと、それに紐づく補助情報データを削除します。

        Args:
            project_id (str): _description_
            task_id (str): _description_
        """
        # 削除対象の入力データを使っているタスクを取得する
        task_list = self.service.wrapper.get_all_tasks(self.project_id, query_params={"input_data_ids": input_data_id})
        # input_data_id も判定している理由： get_all_tasksの`input_data_ids` は大文字小文字を区別しないので、ちゃんと区別する
        other_task_list = [e for e in task_list if e["task_id"] != task_id and input_data_id in e["input_data_id_list"]]
        if len(other_task_list) > 0:
            other_task_id_list = [e["task_id"] for e in other_task_list]
            logger.info(f"task_id='{task_id}' :: input_data_id='{input_data_id}'の入力データは、他のタスクから参照されているため、削除しません。 :: 参照しているタスク = {other_task_id_list}")
            return False

        input_data, _ = self.service.api.get_input_data(self.project_id, input_data_id)
        if not self.confirm_deleting_input_data(task_id, input_data_id, input_data_name=input_data["input_data_name"]):
            return False

        # 入力データに紐づく補助情報を削除
        self.delete_supplementary_data_list(task_id, input_data_id)

        # 入力データに紐づく補助情報を削除
        if not self.dryrun:
            self.service.api.delete_input_data(self.project_id, input_data_id)
        logger.debug(f"task_id='{task_id}' :: 入力データを削除しました。 :: input_data_id='{input_data_id}', input_data_name='{input_data['input_data_name']}'")
        return True

    def _should_delete_task(
        self,
        task: dict[str, Any],
        log_prefix: str,
        task_query: Optional[TaskQuery] = None,
    ) -> bool:
        """タスクを削除するかどうかを判定する"""

        task_id = task["task_id"]

        task_status = TaskStatus(task["status"])
        if task_status in [TaskStatus.WORKING, TaskStatus.COMPLETE]:
            logger.info(f"{log_prefix} :: タスクの状態が作業中/完了状態のため、タスクを削除できません。")
            return False

        annotation_list = self.get_annotation_list(task_id)
        logger.debug(f"{log_prefix} :: アノテーションが{len(annotation_list)}個付与されています。")
        if not self.force:  # noqa: SIM102
            if len(annotation_list) > 0:
                logger.info(f"{log_prefix} :: アノテーションが付与されているため（{len(annotation_list)}個）、タスクの削除をスキップします。削除するには`--force`を指定してください。")
                return False

        if not match_task_with_query(Task.from_dict(task), task_query):
            logger.debug(f"{log_prefix} :: `--task_query`の条件にマッチしないため、スキップします。task_query={task_query}")
            return False

        if not self.confirm_delete_task(task_id):  # noqa: SIM103
            return False

        return True

    def delete_task(self, task_id: str, task_query: Optional[TaskQuery] = None, task_index: Optional[int] = None) -> bool:
        """
        タスクを削除します。

        以下の条件を満たすタスクは削除しない
        * アノテーションが付与されている
        * タスクの状態が作業中 or 完了

        Args:
            project_id:
            task_id:
            force: アノテーションが付与されていても削除します。

        Returns:
            True: タスクを削除した。False: タスクを削除しなかった。

        """
        if task_index is not None:
            log_prefix = f"{task_index + 1} 件目, task_id='{task_id}'"
        else:
            log_prefix = f"task_id='{task_id}'"

        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"{log_prefix} :: タスクは存在しません。")
            return False

        logger.debug(f"{log_prefix} :: status={task['status']}, phase={task['phase']}, updated_datetime={task['updated_datetime']}")

        if not self._should_delete_task(task, log_prefix, task_query=task_query):
            return False

        if not self.dryrun:
            self.service.api.delete_task(self.project_id, task_id)
            logger.debug(f"{log_prefix} :: タスクを削除しました。")

        if self.should_delete_input_data:
            deleted_input_data_count = 0
            for input_data_id in task["input_data_id_list"]:
                try:
                    result = self.delete_input_data_and_supplementary_data(task_id, input_data_id)
                    if result:
                        deleted_input_data_count += 1
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"{log_prefix} :: 入力データの削除に失敗しました。 :: input_data_id='{input_data_id}'", exc_info=True)
                continue
            if deleted_input_data_count > 0:
                logger.debug(f"{log_prefix} :: {deleted_input_data_count} 件の入力データを削除しました。")

        return True

    def confirm_delete_task(self, task_id: str) -> bool:
        message_for_confirm = f"タスク'{task_id}' を削除しますか？"
        return self.confirm_processing(message_for_confirm)

    def get_annotation_list(self, task_id: str) -> list[dict[str, Any]]:
        query_params = {"query": {"task_id": task_id, "exact_match_task_id": True}}
        annotation_list = self.service.wrapper.get_all_annotation_list(self.project_id, query_params=query_params)
        return annotation_list

    def delete_task_list(  # noqa: ANN201
        self,
        task_id_list: list[str],
        task_query: Optional[TaskQuery] = None,
    ):
        """
        複数のタスクを削除する。
        """
        if task_query is not None:
            task_query = self.facade.set_account_id_of_task_query(self.project_id, task_query)

        logger.info(f"{len(task_id_list)} 件のタスクを削除します。")

        count_delete_task = 0
        for task_index, task_id in enumerate(task_id_list):
            try:
                result = self.delete_task(task_id, task_query=task_query, task_index=task_index)
                if result:
                    count_delete_task += 1

            except Exception:  # pylint: disable=broad-except
                logger.warning(f"task_id='{task_id}'の削除に失敗しました。", exc_info=True)
                continue

        logger.info(f"{count_delete_task} / {len(task_id_list)} 件のタスクを削除しました。")


class DeleteTask(CommandLine):
    """
    タスクを削除する
    """

    def main(self) -> None:
        args = self.args

        if args.dryrun:
            add_dryrun_prefix(logger)

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

        dict_task_query = annofabcli.common.cli.get_json_from_args(args.task_query)
        task_query: Optional[TaskQuery] = TaskQuery.from_dict(dict_task_query) if dict_task_query is not None else None

        super().validate_project(args.project_id, [ProjectMemberRole.OWNER])

        main_obj = DeleteTaskMain(
            self.service,
            project_id=args.project_id,
            all_yes=args.yes,
            dryrun=args.dryrun,
            force=args.force,
            should_delete_input_data=args.delete_input_data,
        )
        main_obj.delete_task_list(task_id_list=task_id_list, task_query=task_query)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteTask(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()
    parser.add_argument("--force", action="store_true", help="アノテーションが付与されているタスクも強制的に削除します。")
    parser.add_argument(
        "--delete_input_data",
        action="store_true",
        help="指定した場合、タスクから参照されている入力データと、その入力データに紐づく補助情報を削除します。ただし、他のタスクから参照されている入力データは削除しません。",
    )
    parser.add_argument("--dryrun", action="store_true", help="削除が行われた時の結果を表示しますが、実際はタスクを削除しません。")
    argument_parser.add_task_query()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "delete"
    subcommand_help = "タスクを削除します。"
    description = "タスクを削除します。ただし、作業中/完了状態のタスクは削除できません。デフォルトは、アノテーションが付与されているタスクは削除できません。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
