"""
検査コメントを付与してタスクを差し戻します。
"""

import argparse
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import annofabapi
import annofabapi.utils
import requests
from annofabapi.models import ProjectMemberRole, TaskPhase

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class RejectTasks(AbstractCommandLineInterface):
    def add_inspection_comment(
        self, project_id: str, task: Dict[str, Any], inspection_comment: str, commenter_account_id: str
    ):
        """
        先頭画像の左上に検査コメントを付与する
        Args:
            project_id:
            task:
            inspection_comment:
            commenter_account_id:

        Returns:
            更新した検査コメントの一覧

        """
        first_input_data_id = task["input_data_id_list"][0]
        req_inspection = [
            {
                "data": {
                    "project_id": project_id,
                    "comment": inspection_comment,
                    "task_id": task["task_id"],
                    "input_data_id": first_input_data_id,
                    "inspection_id": str(uuid.uuid4()),
                    "phase": task["phase"],
                    "commenter_account_id": commenter_account_id,
                    "data": {"x": 0, "y": 0, "_type": "Point"},
                    "status": "annotator_action_required",
                    "created_datetime": annofabapi.utils.str_now(),
                },
                "_type": "Put",
            }
        ]

        return self.service.api.batch_update_inspections(
            project_id, task["task_id"], first_input_data_id, request_body=req_inspection
        )[0]

    def confirm_reject_task(
        self, task_id, assign_last_annotator: bool, assigned_annotator_user_id: Optional[str]
    ) -> bool:
        confirm_message = f"task_id = {task_id} のタスクを差し戻しますか？"
        if assign_last_annotator:
            confirm_message += "最後のannotation phaseの担当者を割り当てます。"
        elif assigned_annotator_user_id is not None:
            confirm_message += f"ユーザ '{assigned_annotator_user_id}' を担当者に割り当てます。"
        else:
            confirm_message += f"担当者は割り当てません。"

        return self.confirm_processing_task(task_id, confirm_message)

    def reject_tasks_with_adding_comment(
        self,
        project_id: str,
        task_id_list: List[str],
        inspection_comment: str,
        commenter_user_id: str,
        assign_last_annotator: bool = True,
        assigned_annotator_user_id: Optional[str] = None,
    ):
        """
        検査コメントを付与して、タスクを差し戻す
        Args:
            project_id:
            task_id_list:
            inspection_comment: 検査コメントの中身
            commenter_user_id: 検査コメントを付与して、タスクを差し戻すユーザのuser_id
            assign_last_annotator: Trueなら差し戻したタスクに対して、最後のannotation phaseを担当者を割り当てる
            assigned_annotator_user_id: 差し戻したタスクに割り当てるユーザのuser_id. assign_last_annotatorがTrueの場合、この引数は無視される。

        """

        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])

        commenter_account_id = self.facade.get_account_id_from_user_id(project_id, commenter_user_id)
        if commenter_account_id is None:
            logger.error(f"検査コメントを付与するユーザ( {commenter_user_id} の account_idが見つかりませんでした。終了します。")
            return

        assigned_annotator_account_id = (
            self.facade.get_account_id_from_user_id(project_id, assigned_annotator_user_id)
            if assigned_annotator_user_id is not None
            else None
        )

        logger.info(f"差し戻すタスク数: {len(task_id_list)}")
        success_count = 0

        for task_index, task_id in enumerate(task_id_list):
            str_progress = annofabcli.utils.progress_msg(task_index + 1, len(task_id_list))

            task, _ = self.service.api.get_task(project_id, task_id)

            logger.debug(
                f"{str_progress} : task_id = {task_id} の現状: status = {task['status']}, phase = {task['phase']}"
            )

            if task["phase"] == TaskPhase.ANNOTATION.value:
                logger.warning(f"{str_progress} : task_id = {task_id} はannofation phaseのため、差し戻しできません。")
                continue

            if not self.confirm_reject_task(task_id, assign_last_annotator, assigned_annotator_user_id):
                continue

            try:
                # 担当者を変更して、作業中にする
                self.facade.change_operator_of_task(project_id, task_id, commenter_account_id)
                logger.debug(
                    f"{str_progress} : task_id = {task_id}, phase={task['phase']}, {commenter_user_id}に担当者変更 完了"
                )

                self.facade.change_to_working_phase(project_id, task_id, commenter_account_id)
                logger.debug(f"{str_progress} : task_id = {task_id}, phase={task['phase']}, working statusに変更 完了")

            except requests.exceptions.HTTPError as e:
                logger.warning(e)
                logger.warning(f"{str_progress} : task_id = {task_id}, phase={task['phase']} の担当者変更 or 作業phaseへの変更に失敗")
                continue

            # 少し待たないと検査コメントが登録できない場合があるため
            time.sleep(3)
            try:
                # 検査コメントを付与する
                self.add_inspection_comment(project_id, task, inspection_comment, commenter_account_id)
                logger.debug(f"{str_progress} : task_id = {task_id}, 検査コメントの付与 完了")

            except requests.exceptions.HTTPError as e:
                logger.warning(e)
                logger.warning(f"{str_progress} : task_id = {task_id} 検査コメントの付与に失敗")
                continue

            try:
                # タスクを差し戻す
                if assign_last_annotator:
                    # 最後のannotation phaseに担当を割り当てる
                    _, last_annotator_account_id = self.facade.reject_task_assign_last_annotator(
                        project_id, task_id, commenter_account_id
                    )
                    last_annotator_user_id = self.facade.get_user_id_from_account_id(
                        project_id, last_annotator_account_id
                    )
                    str_annotator_user = f"タスクの担当者: {last_annotator_user_id}"

                else:
                    # 指定したユーザに担当を割り当てる
                    self.facade.reject_task(
                        project_id,
                        task_id,
                        account_id=commenter_account_id,
                        annotator_account_id=assigned_annotator_account_id,
                    )
                    str_annotator_user = f"タスクの担当者: {assigned_annotator_user_id}"

                logger.info(f"{str_progress} : task_id = {task_id} の差し戻し完了. {str_annotator_user}")
                success_count += 1

            except requests.exceptions.HTTPError as e:
                logger.warning(e)
                logger.warning(f"{str_progress} : task_id = {task_id} タスクの差し戻しに失敗")
                continue

        logger.info(f"{success_count} / {len(task_id_list)} 件 タスクの差し戻しに成功した")

    def main(self):
        args = self.args

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        user_id = self.service.api.login_user_id
        assign_last_annotator = not args.not_assign and args.assigned_annotator_user_id is None
        self.reject_tasks_with_adding_comment(
            args.project_id,
            task_id_list,
            args.comment,
            commenter_user_id=user_id,
            assign_last_annotator=assign_last_annotator,
            assigned_annotator_user_id=args.assigned_annotator_user_id,
        )


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    RejectTasks(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    parser.add_argument("-c", "--comment", type=str, required=True, help="差し戻すときに付与する検査コメントを指定します。")

    # 差し戻したタスクの担当者の割当に関して
    assign_group = parser.add_mutually_exclusive_group()

    assign_group.add_argument(
        "--not_assign", action="store_true", help="差し戻したタスクに担当者を割り当てません。" "指定しない場合は、最後のannotation phaseの担当者が割り当てられます。"
    )

    assign_group.add_argument(
        "--assigned_annotator_user_id",
        type=str,
        help="差し戻したタスクに割り当てるユーザのuser_idを指定します。" "指定しない場合は、最後のannotation phaseの担当者が割り当てられます。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "reject"
    subcommand_help = "検査コメントを付与してタスクを差し戻します。"
    description = "検査コメントを付与してタスクを差し戻します。" "検査コメントは、タスク内の先頭の画像の左上(x=0,y=0)に付与します。" "アノテーションルールを途中で変更したときなどに、利用します。"
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
