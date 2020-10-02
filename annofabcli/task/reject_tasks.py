import argparse
import logging
import multiprocessing
import sys
import uuid
from functools import partial
from typing import Any, Dict, List, Optional, Tuple

import annofabapi
import annofabapi.utils
import requests
from annofabapi.dataclass.task import Task
from annofabapi.models import InputDataType, ProjectMemberRole, TaskPhase, TaskStatus

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


class RejectTasksMain(AbstracCommandCinfirmInterface):
    def __init__(self, service: annofabapi.Resource, all_yes: bool = False):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        AbstracCommandCinfirmInterface.__init__(self, all_yes)

    def add_inspection_comment(
        self,
        project_id: str,
        project_input_data_type: InputDataType,
        task: Dict[str, Any],
        inspection_comment: str,
    ):
        """
        検査コメントを付与する。
        画像プロジェクトなら先頭画像の左上に付与する。
        動画プロジェクトなら最初の区間に付与する。

        Args:
            project_id:
            project_input_data_type: プロジェクトの入力データの種類
            task:
            inspection_comment:

        Returns:
            更新した検査コメントの一覧

        """
        first_input_data_id = task["input_data_id_list"][0]
        if project_input_data_type == InputDataType.MOVIE:
            inspection_data = {"start": 0, "end": 100, "_type": "Time"}
        else:
            inspection_data = {"x": 0, "y": 0, "_type": "Point"}

        req_inspection = [
            {
                "data": {
                    "project_id": project_id,
                    "comment": inspection_comment,
                    "task_id": task["task_id"],
                    "input_data_id": first_input_data_id,
                    "inspection_id": str(uuid.uuid4()),
                    "phase": task["phase"],
                    "commenter_account_id": self.service.api.account_id,
                    "data": inspection_data,
                    "status": "annotator_action_required",
                    "created_datetime": task["updated_datetime"],
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

        return self.confirm_processing(confirm_message)

    def change_to_working_status(self, project_id: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        作業中状態に遷移する。必要ならば担当者を自分自身に変更する。

        Args:
            project_id:
            task:

        Returns:
            作業中状態遷移後のタスク
        """

        task_id = task["task_id"]
        try:
            if task["account_id"] != self.service.api.account_id:
                self.facade.change_operator_of_task(project_id, task_id, self.service.api.account_id)
                logger.debug(f"{task_id}: 担当者を自分自身に変更しました。")

            changed_task = self.facade.change_to_working_status(project_id, task_id, self.service.api.account_id)
            return changed_task

        except requests.HTTPError as e:
            logger.warning(e)
            logger.warning(f"{task_id}: 担当者の変更、または作業中状態への変更に失敗しました。")
            raise

    def _can_reject_task(
        self,
        task: Dict[str, Any],
        assign_last_annotator: bool,
        assigned_annotator_user_id: Optional[str],
        cancel_acceptance: bool = False,
        task_query: Optional[TaskQuery] = None,
    ):
        task_id = task["task_id"]
        if task["phase"] == TaskPhase.ANNOTATION.value:
            logger.warning(f"task_id = {task_id}: annofation phaseのため、差し戻しできません。")
            return False

        if task["status"] == TaskStatus.WORKING.value:
            logger.warning(f"task_id = {task_id} : タスクのstatusが'作業中'なので、差し戻しできません。")
            return False

        if task["status"] == TaskStatus.COMPLETE.value and not cancel_acceptance:
            logger.warning(
                f"task_id = {task_id} : タスクのstatusが'完了'なので、差し戻しできません。"
                f"受入完了を取消す場合は、コマンドライン引数に'--cancel_acceptance'を追加してください。"
            )
            return False

        if not match_task_with_query(Task.from_dict(task), task_query):
            logger.debug(f"task_id = {task_id} : TaskQueryの条件にマッチしないため、スキップします。")
            return False

        if not self.confirm_reject_task(
            task_id, assign_last_annotator=assign_last_annotator, assigned_annotator_user_id=assigned_annotator_user_id
        ):
            return False

        return True

    def _cancel_acceptance(self, task: Dict[str, Any]) -> Dict[str, Any]:
        request_body = {
            "status": "not_started",
            "account_id": self.service.api.account_id,
            "last_updated_datetime": task["updated_datetime"],
        }
        content, _ = self.service.api.operate_task(task["project_id"], task["task_id"], request_body=request_body)
        return content

    def reject_task_with_adding_comment(
        self,
        project_id: str,
        task_id: str,
        project_input_data_type: InputDataType,
        inspection_comment: Optional[str] = None,
        assign_last_annotator: bool = True,
        assigned_annotator_user_id: Optional[str] = None,
        cancel_acceptance: bool = False,
        task_query: Optional[TaskQuery] = None,
        task_index: Optional[int] = None,
    ) -> bool:
        """
        タスクを強制的に差し戻す

        Args:
            project_id:
            task_id_list:
            inspection_comment: 検査コメントの中身
            assign_last_annotator: Trueなら差し戻したタスクに対して、最後のannotation phaseを担当者を割り当てる
            assigned_annotator_user_id: 差し戻したタスクに割り当てるユーザのuser_id. assign_last_annotatorがTrueの場合、この引数は無視される。

        """
        logging_prefix = f"{task_index+1} 件目" if task_index is not None else ""

        assigned_annotator_account_id = (
            self.facade.get_account_id_from_user_id(project_id, assigned_annotator_user_id)
            if assigned_annotator_user_id is not None
            else None
        )

        task, _ = self.service.api.get_task(project_id, task_id)

        logger.debug(
            f"{logging_prefix} : task_id = {task['task_id']}, "
            f"status = {task['status']}, "
            f"phase = {task['phase']}, "
        )

        if not self._can_reject_task(
            task=task,
            assign_last_annotator=assign_last_annotator,
            assigned_annotator_user_id=assigned_annotator_user_id,
            cancel_acceptance=cancel_acceptance,
            task_query=task_query,
        ):
            return False

        if task["status"] == TaskStatus.COMPLETE.value and cancel_acceptance:
            self._cancel_acceptance(task)

        if inspection_comment is not None:
            changed_task = self.change_to_working_status(project_id, task)
            try:
                # 検査コメントを付与する
                self.add_inspection_comment(project_id, project_input_data_type, changed_task, inspection_comment)
                logger.debug(f"{logging_prefix} : task_id = {task_id}, 検査コメントの付与 完了")

            except requests.exceptions.HTTPError:
                logger.warning(f"{logging_prefix} : task_id = {task_id} 検査コメントの付与に失敗", exc_info=True)
                self.facade.change_to_break_phase(project_id, task_id)
                return False

        try:
            # タスクを差し戻す
            if assign_last_annotator:
                # 最後のannotation phaseに担当を割り当てる
                self.facade.reject_task_assign_last_annotator(project_id, task_id)
                logger.info(f"{logging_prefix} : task_id = {task_id} のタスクを差し戻しました。タスクの担当者は直前の教師付フェーズの担当者。")
                return True

            else:
                # 指定したユーザに担当を割り当てる
                self.facade.reject_task(
                    project_id,
                    task_id,
                    account_id=self.service.api.account_id,
                    annotator_account_id=assigned_annotator_account_id,
                )
                str_annotator_user = f"タスクの担当者: {assigned_annotator_user_id}"
                logger.info(f"{logging_prefix} : task_id = {task_id} の差し戻し完了. {str_annotator_user}")
                return True

        except requests.exceptions.HTTPError as e:
            logger.warning(e)
            logger.warning(f"{logging_prefix} : task_id = {task_id} タスクの差し戻しに失敗")

            new_task = self.service.wrapper.get_task_or_none(project_id, task_id)
            if new_task["status"] == TaskStatus.WORKING.value and new_task["account_id"] == self.service.api.account_id:
                self.facade.change_to_break_phase(project_id, task_id)
            return False

    def reject_task_for_task_wrapper(
        self,
        tpl: Tuple[int, str],
        project_id: str,
        project_input_data_type: InputDataType,
        inspection_comment: Optional[str] = None,
        assign_last_annotator: bool = True,
        assigned_annotator_user_id: Optional[str] = None,
        cancel_acceptance: bool = False,
        task_query: Optional[TaskQuery] = None,
    ) -> bool:
        task_index, task_id = tpl
        return self.reject_task_with_adding_comment(
            project_id=project_id,
            task_id=task_id,
            task_index=task_index,
            project_input_data_type=project_input_data_type,
            inspection_comment=inspection_comment,
            assign_last_annotator=assign_last_annotator,
            assigned_annotator_user_id=assigned_annotator_user_id,
            cancel_acceptance=cancel_acceptance,
            task_query=task_query,
        )

    def reject_task_list(
        self,
        project_id: str,
        task_id_list: List[str],
        inspection_comment: Optional[str] = None,
        assign_last_annotator: bool = True,
        assigned_annotator_user_id: Optional[str] = None,
        cancel_acceptance: bool = False,
        task_query: Optional[TaskQuery] = None,
        parallelism: Optional[int] = None,
    ) -> None:
        if task_query is not None:
            task_query = self.facade.set_account_id_of_task_query(project_id, task_query)

        project, _ = self.service.api.get_project(project_id)
        project_input_data_type = InputDataType(project["input_data_type"])

        logger.info(f"差し戻すタスク数: {len(task_id_list)}")

        if parallelism is not None:
            partial_func = partial(
                self.reject_task_for_task_wrapper,
                project_id=project_id,
                project_input_data_type=project_input_data_type,
                inspection_comment=inspection_comment,
                assign_last_annotator=assign_last_annotator,
                assigned_annotator_user_id=assigned_annotator_user_id,
                cancel_acceptance=cancel_acceptance,
                task_query=task_query,
            )
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(partial_func, enumerate(task_id_list))
                success_count = len([e for e in result_bool_list if e])

        else:
            # 逐次処理
            success_count = 0
            for task_index, task_id in enumerate(task_id_list):
                result = self.reject_task_with_adding_comment(
                    project_id,
                    task_id,
                    task_index=task_index,
                    project_input_data_type=project_input_data_type,
                    inspection_comment=inspection_comment,
                    assign_last_annotator=assign_last_annotator,
                    assigned_annotator_user_id=assigned_annotator_user_id,
                    cancel_acceptance=cancel_acceptance,
                    task_query=task_query,
                )
                if result:
                    success_count += 1

        logger.info(f"{success_count} / {len(task_id_list)} 件 タスクを差し戻しました。")


class RejectTasks(AbstractCommandLineInterface):
    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli task reject: error:"

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
        assign_last_annotator = not args.not_assign and args.assigned_annotator_user_id is None

        super().validate_project(args.project_id, [ProjectMemberRole.OWNER])

        dict_task_query = annofabcli.common.cli.get_json_from_args(args.task_query)
        task_query: Optional[TaskQuery] = TaskQuery.from_dict(dict_task_query) if dict_task_query is not None else None

        main_obj = RejectTasksMain(self.service, all_yes=self.all_yes)
        main_obj.reject_task_list(
            args.project_id,
            task_id_list,
            inspection_comment=args.comment,
            assign_last_annotator=assign_last_annotator,
            assigned_annotator_user_id=args.assigned_annotator_user_id,
            cancel_acceptance=args.cancel_acceptance,
            task_query=task_query,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    RejectTasks(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    parser.add_argument(
        "-c",
        "--comment",
        type=str,
        help="差し戻すときに付与する検査コメントを指定します。" "画像プロジェクトならばタスク内の先頭の画像の左上(x=0,y=0)に、動画プロジェクトなら動画の先頭（start=0, end=100)に付与します。",
    )

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

    parser.add_argument("--cancel_acceptance", action="store_true", help="受入完了状態を取り消して、タスクを差し戻します。")

    argument_parser.add_task_query()

    parser.add_argument(
        "--parallelism", type=int, help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず'--yes'を指定してください。指定しない場合は、逐次的に処理します。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "reject"
    subcommand_help = "タスクを強制的に差し戻します。"
    description = (
        "タスクを強制的に差し戻します。差し戻す際、検査コメントを付与することもできます。"
        "作業中状態のタスクに対しては変更できません。"
        "この差戻しは差戻しとして扱われず、抜取検査・抜取受入のスキップ判定に影響を及ぼしません。"
    )
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
