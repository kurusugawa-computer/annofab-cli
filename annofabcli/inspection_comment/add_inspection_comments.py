import argparse
import logging
import multiprocessing
import sys
import uuid
from dataclasses import dataclass
from functools import partial
from typing import Any, Dict, List, Optional, Tuple

import annofabapi
import annofabapi.utils
import requests
from annofabapi.dataclass.task import Task
from annofabapi.models import InputDataType, ProjectMemberRole, TaskPhase, TaskStatus
from dataclasses_json import DataClassJsonMixin

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    AbstractCommandLineWithConfirmInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import TaskQuery, match_task_with_query

logger = logging.getLogger(__name__)


@dataclass
class AddedComment(DataClassJsonMixin):
    """
    追加対象の検査コメント
    """

    comment: str
    """検査コメントの中身"""

    data: Dict[str, Any]
    """検査コメントを付与する位置や区間"""

    annotation_id: Optional[str] = None
    """検査コメントに紐付ける"""

    phrases: Optional[List[str]] = None
    """参照している定型指摘ID"""


AddedCommentsForTask = Dict[str, List[AddedComment]]
"""
タスク配下の追加対象の検査コメント
keyはinput_data_id
"""

AddedComments = Dict[str, AddedCommentsForTask]
"""
追加対象の検査コメント
keyはtask_id
"""


class AddInspectionCommentsMain(AbstractCommandLineWithConfirmInterface):
    def __init__(self, service: annofabapi.Resource, project_id: str, all_yes: bool = False):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.project_id = project_id

        # TODO: fix me
        self.project_input_data_type = InputDataType.IMAGE
        AbstractCommandLineWithConfirmInterface.__init__(self, all_yes)

    def _create_request_body(
        self, task: Dict[str, Any], input_data_id: str, comments: List[AddedComment]
    ) -> List[Dict[str, Any]]:
        """batch_update_inspections に渡すリクエストボディを作成する。"""

        def _convert(comment: AddedComment) -> Dict[str, Any]:
            return {
                "data": {
                    "project_id": self.project_id,
                    "comment": comment.comment,
                    "task_id": task["task_id"],
                    "input_data_id": input_data_id,
                    "inspection_id": str(uuid.uuid4()),
                    "phase": task["phase"],
                    "commenter_account_id": self.service.api.account_id,
                    "data": comment.data,
                    "status": "annotator_action_required",
                    "created_datetime": task["updated_datetime"],
                },
                "_type": "Put",
            }

        return [_convert(e) for e in comments]

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

    def _can_add_comment(
        self,
        task: Dict[str, Any],
    ) -> bool:
        task_id = task["task_id"]
        if task["phase"] == TaskPhase.ANNOTATION.value:
            logger.warning(f"task_id='{task_id}': 教師付フェーズなので、検査コメントを付与できません。")
            return False

        if task["status"] in [TaskStatus.NOT_STARTED.value, TaskStatus.WORKING.value, TaskStatus.BREAK.value]:
            logger.warning(
                f"task_id='{task_id}' : タスクの状態が未着手,作業中,休憩中 以外の状態なので、検査コメントを付与できません。（task_status='{task['status']}'）"
            )
            return False
        return True

    def add_comments_for_task(
        self,
        task_id: str,
        comments_for_task: AddedCommentsForTask,
        task_index: Optional[int] = None,
    ) -> bool:
        """
        タスクに検査コメントを付与します。
        """
        logging_prefix = f"{task_index+1} 件目" if task_index is not None else ""

        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"{logging_prefix} : task_id='{task_id}' のタスクは存在しないので、スキップします。")
            return False

        logger.debug(
            f"{logging_prefix} : task_id = {task['task_id']}, "
            f"status = {task['status']}, "
            f"phase = {task['phase']}, "
        )

        if not self._can_add_comment(
            task=task,
        ):
            return False

        # 検査コメントを付与するには作業中状態にする必要がある
        changed_task = self.change_to_working_status(self.project_id, task)
        for input_data_id, comments in comments_for_task.items():
            try:
                # 検査コメントを付与する
                request_body = self._create_request_body(
                    task=changed_task, input_data_id=input_data_id, comments=comments
                )
                self.service.api.batch_update_inspections(
                    self.project_id, task_id, input_data_id, request_body=request_body
                )
                logger.debug(f"{logging_prefix} : task_id={task_id}, input_data_id={input_data_id}: 検査コメントを付与しました。")
            except Exception as e:
                logger.warning(
                    f"{logging_prefix} : task_id={task_id}, input_data_id={input_data_id}: 検査コメントの付与に失敗しました。", e
                )

        self.facade.change_to_break_phase(self.project_id, task_id)

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


class PutInspectionComments(AbstractCommandLineInterface):
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

        super().validate_project(args.project_id, [ProjectMemberRole.ACCEPTER, ProjectMemberRole.OWNER])

        dict_inspection_comments = annofabcli.common.cli.get_json_from_args(args.json)

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
    PutInspectionComments(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    # argument_parser.add_task_query()

    parser.add_argument(
        "--parallelism", type=int, help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず'--yes'を指定してください。指定しない場合は、逐次的に処理します。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "put"
    subcommand_help = "検査コメントを付与します。"
    description = "検査コメントを付与します。"
    epilog = "チェッカーロールまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
