import argparse
import logging
from typing import Any, Dict, List, Optional

import requests
from annofabapi.dataclass.task import Task
from annofabapi.models import ProjectMemberRole, TaskStatus

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.facade import TaskQuery, match_task_with_query

logger = logging.getLogger(__name__)


class DeleteTask(AbstractCommandLineInterface):
    """
    アノテーションが付与されていないタスクを削除する
    """

    @annofabcli.utils.allow_404_error
    def get_task(self, project_id: str, task_id: str) -> Dict[str, Any]:
        task, _ = self.service.api.get_task(project_id, task_id)
        return task

    def confirm_delete_task(self, task_id: str) -> bool:
        message_for_confirm = f"タスク'{task_id}' を削除しますか？"
        return self.confirm_processing(message_for_confirm)

    def get_annotation_list(self, project_id: str, task_id: str) -> List[Dict[str, Any]]:
        query_params = {"query": {"task_id": task_id, "exact_match_task_id": True}}
        annotation_list = self.service.wrapper.get_all_annotation_list(project_id, query_params=query_params)
        return annotation_list

    def delete_task(
        self,
        project_id: str,
        task_id: str,
        force: bool = False,
        task_query: Optional[TaskQuery] = None,
    ) -> bool:
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
        task = self.get_task(project_id, task_id)
        if task is None:
            logger.info(f"task_id={task_id} のタスクは存在しません。")
            return False

        logger.debug(
            f"task_id={task['task_id']}, status={task['status']}, "
            f"phase={task['phase']}, updated_datetime={task['updated_datetime']}"
        )

        task_status = TaskStatus(task["status"])
        if task_status in [TaskStatus.WORKING, TaskStatus.COMPLETE]:
            logger.info(f"タスクの状態が作業中/完了状態のため、タスクを削除できません。")
            return False

        annotation_list = self.get_annotation_list(project_id, task_id)
        logger.debug(f"task_id={task_id}: アノテーションが{len(annotation_list)}個付与されています。")
        if not force:
            if len(annotation_list) > 0:
                logger.info(
                    f"アノテーションが付与されているため（{len(annotation_list)}個）、タスク'{task_id}'の削除をスキップします。"
                    f"削除するには`--force`を指定してください。"
                )
                return False

        if not match_task_with_query(Task.from_dict(task), task_query):
            logger.debug(f"task_id={task_id}: `--task_query`の条件にマッチしないため、スキップします。task_query={task_query}")
            return False

        if not self.confirm_delete_task(task_id):
            return False

        self.service.api.delete_task(project_id, task_id)
        return True

    def delete_task_list(
        self, project_id: str, task_id_list: List[str], force: bool = False, task_query: Optional[TaskQuery] = None
    ):
        """
        複数のタスクを削除する。
        """
        if task_query is not None:
            task_query = self.facade.set_account_id_of_task_query(project_id, task_query)

        super().validate_project(project_id, [ProjectMemberRole.OWNER])
        project_title = self.facade.get_project_title(project_id)
        logger.info(f"プロジェクト'{project_title}'から 、{len(task_id_list)} 件のタスクを削除します。")

        count_delete_task = 0
        for task_index, task_id in enumerate(task_id_list):
            try:
                result = self.delete_task(project_id, task_id, force=force, task_query=task_query)
                if result:
                    count_delete_task += 1
                    logger.info(f"{task_index+1} / {len(task_id_list)} 件目: タスク'{task_id}'を削除しました。")

            except requests.exceptions.HTTPError as e:
                logger.warning(e)
                logger.warning(f"task_id='{task_id}'の削除に失敗しました。")
                continue

        logger.info(f"プロジェクト'{project_title}'から 、{count_delete_task} / {len(task_id_list)} 件のタスクを削除しました。")

    def main(self):
        args = self.args
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

        dict_task_query = annofabcli.common.cli.get_json_from_args(args.task_query)
        task_query: Optional[TaskQuery] = TaskQuery.from_dict(dict_task_query) if dict_task_query is not None else None

        self.delete_task_list(args.project_id, task_id_list=task_id_list, force=args.force, task_query=task_query)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteTask(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()
    parser.add_argument("--force", action="store_true", help="アノテーションが付与されているタスクも強制的に削除します。")
    argument_parser.add_task_query()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "delete"
    subcommand_help = "タスクを削除します。"
    description = "タスクを削除します。ただし、作業中/完了状態のタスクは削除できません。デフォルトは、アノテーションが付与されているタスクは削除できません。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
