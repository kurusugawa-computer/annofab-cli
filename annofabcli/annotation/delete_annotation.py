import argparse
import logging
from pathlib import Path
from typing import List, Optional

import annofabapi
import requests
from annofabapi.dataclass.task import Task
from annofabapi.models import ProjectMemberRole, TaskStatus
from annofabapi.utils import can_put_annotation

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.annotation.dump_annotation import DumpAnnotation
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class DeleteAnnotation(AbstractCommandLineInterface):
    """
    アノテーションを削除する
    """

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.dump_annotation_obj = DumpAnnotation(service, facade, args)

    def delete_annotation_for_input_data(self, project_id: str, task_id: str, input_data_id: str) -> int:
        """
        入力データに対してアノテーションを削除する

        Args:
            project_id:
            task_id:
            input_data_id:

        Returns:
            削除したアノテーション数

        """
        old_annotation, _ = self.service.api.get_editor_annotation(project_id, task_id, input_data_id)
        old_details = old_annotation["details"]
        logger.debug(f"task_id={task_id}, input_data_id={input_data_id}: アノテーション数={len(old_details)}")
        if len(old_details) == 0:
            return len(old_details)

        updated_datetime = old_annotation["updated_datetime"] if old_annotation is not None else None
        request_body = {
            "project_id": project_id,
            "task_id": task_id,
            "input_data_id": input_data_id,
            "details": [],
            "updated_datetime": updated_datetime,
        }
        self.service.api.put_annotation(project_id, task_id, input_data_id, request_body=request_body)
        logger.debug(f"task_id={task_id}, input_data_id={input_data_id}: アノテーションを削除しました。")
        return len(old_details)

    def delete_annotation_for_task(
        self, project_id: str, task_id: str, my_account_id: str, backup_dir: Optional[Path] = None
    ) -> bool:
        """
        タスクに対してアノテーションを削除する

        Args:
            project_id:
            task_id:
            my_account_id: 自分自身のaccount_id
            backup_dir: 削除対象のアノテーションをバックアップとして保存するディレクトリ。指定しない場合は、バックアップを取得しない。

        Returns:
            アノテーション削除を実施したかどうか。スキップしたらFalse

        """
        dict_task = self.service.wrapper.get_task_or_none(project_id, task_id)
        if dict_task is None:
            logger.warning(f"task_id = '{task_id}' は存在しません。")
            return False

        task: Task = Task.from_dict(dict_task)  # type: ignore
        logger.info(
            f"task_id={task.task_id}, phase={task.phase.value}, status={task.status.value}, "
            f"updated_datetime={task.updated_datetime}"
        )
        if task.status in [TaskStatus.WORKING, TaskStatus.COMPLETE]:
            logger.warning(f"task_id={task_id}: タスクが作業中/完了状態のため、スキップします。")
            return False

        if not can_put_annotation(dict_task, my_account_id):
            logger.debug(f"タスク'{task_id}'は、過去に誰かに割り当てられたタスクで、現在の担当者が自分自身でないため、アノテーションの削除をスキップします。")
            return False

        if not self.confirm_processing(f"task_id={task_id} のアノテーションを削除しますか？"):
            return False

        if backup_dir is not None:
            self.dump_annotation_obj.dump_annotation_for_task(project_id, task_id, output_dir=backup_dir)

        deleted_annotation_count = 0
        for input_data_id in task.input_data_id_list:
            try:
                deleted_annotation_count += self.delete_annotation_for_input_data(project_id, task_id, input_data_id)
            except requests.HTTPError as e:
                logger.warning(e)
                logger.warning(f"task_id={task_id}, input_data_id={input_data_id}: アノテーションの削除に失敗しました。")

        logger.info(f"task_id={task_id}: アノテーション {deleted_annotation_count} 個を削除しました。")
        return True

    def delete_annotation_for_task_list(self, project_id: str, task_id_list: List[str], backup_dir: Path):
        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        project_title = self.facade.get_project_title(project_id)
        logger.info(f"プロジェクト'{project_title}'に対して、タスク{len(task_id_list)} 件のアノテーションを削除します。")

        my_account_id = self.facade.get_my_account_id()
        backup_dir.mkdir(exist_ok=True, parents=True)

        for task_index, task_id in enumerate(task_id_list):
            logger.info(f"{task_index+1} / {len(task_id_list)} 件目: タスク '{task_id}' を削除します。")
            self.delete_annotation_for_task(project_id, task_id, my_account_id=my_account_id, backup_dir=backup_dir)

    def main(self):
        args = self.args
        project_id = args.project_id
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        backup_dir = Path(args.backup)
        self.delete_annotation_for_task_list(project_id, task_id_list, backup_dir)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    parser.add_argument(
        "--backup",
        type=str,
        required=False,
        help="アノテーションのバックアップを保存するディレクトリを指定してください。アノテーションの復元は'annotation restore'コマンドで実現できます。",
    )
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "delete"
    subcommand_help = "アノテーションを削除します。"
    description = "タスク配下のアノテーションを削除します。" "ただし、作業中/完了状態のタスク、または「過去に割り当てられていて現在の担当者が自分自身でない」タスクのアノテーションは削除できません。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
