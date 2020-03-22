import argparse
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import annofabapi.utils
import dateutil
import requests
from annofabapi.dataclass.task import Task
from annofabapi.models import Inspection, InspectionStatus, ProjectMemberRole, TaskPhase, TaskStatus
from more_itertools import first_true

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)

InspectionJson = Dict[str, Dict[str, List[Inspection]]]
"""
Dict[task_id, Dict[input_data_id, List[Inspection]]] の検査コメント情報
"""


class ComleteTasks(AbstractCommandLineInterface):
    """
    タスクを受け入れ完了にする
    """

    @staticmethod
    def inspection_list_to_input_data_dict(inspection_list: List[Inspection]) -> Dict[str, List[Inspection]]:
        """
        検査コメントのListを、Dict[InputDataId, List[Inspection]]] の形式に変換する。

        """
        input_data_dict: Dict[str, List[Inspection]] = {}
        for inspection in inspection_list:
            input_data_id = inspection["input_data_id"]
            inspection_list = input_data_dict.get(input_data_id, [])
            inspection_list.append(inspection)
            input_data_dict[input_data_id] = inspection_list
        return input_data_dict

    @staticmethod
    def inspection_list_to_dict(all_inspection_list: List[Inspection]) -> InspectionJson:
        """
        検査コメントのListを、Dict[TaskId, Dict[InputDataId, List[Inspection]]] の形式に変換する。

        """
        task_dict: InspectionJson = {}
        for inspection in all_inspection_list:
            task_id = inspection["task_id"]
            input_data_dict: Dict[str, List[Inspection]] = task_dict.get(task_id, {})

            input_data_id = inspection["input_data_id"]
            inspection_list = input_data_dict.get(input_data_id, [])
            inspection_list.append(inspection)
            input_data_dict[input_data_id] = inspection_list

            task_dict[task_id] = input_data_dict

        return task_dict

    def reply_inspection_comment(
        self,
        task: Task,
        input_data_id: str,
        unanswered_comment_list: List[Inspection],
        reply_comment: str,
        commenter_account_id: str,
    ):
        """
        未回答の検査コメントに対して、返信を付与する。
        """

        def to_req_inspection(i: Inspection) -> Dict[str, Any]:
            return {
                "data": {
                    "project_id": task.project_id,
                    "comment": reply_comment,
                    "task_id": task.task_id,
                    "input_data_id": input_data_id,
                    "inspection_id": str(uuid.uuid4()),
                    "phase": task.phase.value,
                    "phase_stage": task.phase_stage,
                    "commenter_account_id": commenter_account_id,
                    "data": i["data"],
                    "parent_inspection_id": i["inspection_id"],
                    "status": InspectionStatus.NO_CORRECTION_REQUIRED.value,
                    "created_datetime": annofabapi.utils.str_now(),
                },
                "_type": "Put",
            }

        request_body = [to_req_inspection(e) for e in unanswered_comment_list]
        return self.service.api.batch_update_inspections(
            task.project_id, task.task_id, input_data_id, request_body=request_body
        )[0]

    def update_status_of_inspections(
        self,
        project_id: str,
        task_id: str,
        input_data_id: str,
        inspection_list: List[Inspection],
        inspection_status: InspectionStatus,
    ):

        if inspection_list is None or len(inspection_list) == 0:
            logger.warning(f"変更対象の検査コメントはなかった。task_id = {task_id}, input_data_id = {input_data_id}")
            return

        target_inspection_id_list = [inspection["inspection_id"] for inspection in inspection_list]

        def filter_inspection(arg_inspection: Inspection) -> bool:
            """
            statusを変更する検査コメントの条件。
            """

            return arg_inspection["inspection_id"] in target_inspection_id_list

        self.service.wrapper.update_status_of_inspections(
            project_id, task_id, input_data_id, filter_inspection, inspection_status
        )
        logger.debug(f"{task_id}, {input_data_id}, {len(inspection_list)}件 検査コメントの状態を変更")

    def get_unprocessed_inspection_list(self, task: Task, input_data_id) -> List[Inspection]:
        """
        未処置の検査コメントリストを取得する。
        ただし、現在のタスクフェーズで編集できる検査コメントのみである。

        Args:
            task:
            input_data_id:
            target_phase:
            target_phase_stage:

        Returns:

        """
        inspectin_list, _ = self.service.api.get_inspections(task.project_id, task.task_id, input_data_id)
        return [
            e
            for e in inspectin_list
            if e["status"] == InspectionStatus.ANNOTATOR_ACTION_REQUIRED.value
            and e["phase"] == task.phase.value
            and e["phase_stage"] == task.phase_stage
        ]

    def get_unprocessed_inspection_list_by_task_id(
        self, project_id: str, task: Task, target_phase: TaskPhase, target_phase_stage: int
    ) -> List[Inspection]:
        all_inspection_list = []
        for input_data_id in task.input_data_id_list:
            inspectins, _ = self.service.api.get_inspections(project_id, task.task_id, input_data_id)
            all_inspection_list.extend(
                [
                    e
                    for e in inspectins
                    if e["status"] == InspectionStatus.ANNOTATOR_ACTION_REQUIRED.value
                    and e["phase"] == target_phase.value
                    and e["phase_stage"] == target_phase_stage
                ]
            )

        return all_inspection_list

    def change_to_working_status(self, task: Task, my_account_id: str) -> bool:
        # 担当者変更
        changed_operator = False
        try:
            if task.account_id != my_account_id:
                self.facade.change_operator_of_task(task.project_id, task.task_id, my_account_id)
                changed_operator = True
                logger.debug(f"{task.task_id}: 担当者を自分自身に変更しました。")

            self.facade.change_to_working_status(task.project_id, task.task_id, my_account_id)
            return changed_operator

        except requests.HTTPError as e:
            logger.warning(e)
            logger.warning(f"{task.task_id}: 担当者の変更、または作業中状態への変更に失敗しました。")
            raise

    def get_unanswered_comment_list(self, task: Task, input_data_id: str) -> List[Inspection]:
        """
        未回答の検査コメントのリストを取得する。

        Returns:

        """

        def exists_answered_comment(parent_inspection_id: str) -> bool:
            """
            回答済の返信コメントがあるかどうか

            Args:
                parent_inspection_id:

            Returns:

            """
            if task.started_datetime is None:
                # タスク未着手状態なので、回答済のコメントはない
                return False
            task_started_datetime = task.started_datetime
            answered_comment = first_true(
                inspection_list,
                pred=lambda e: e["parent_inspection_id"] == parent_inspection_id
                and dateutil.parser.parse(e["created_datetime"]) >= dateutil.parser.parse(task_started_datetime),
            )
            return answered_comment is not None

        inspection_list, _ = self.service.api.get_inspections(task.project_id, task.task_id, input_data_id)
        # 未処置の検査コメント
        unprocessed_inspection_list = [
            e
            for e in inspection_list
            if e["parent_inspection_id"] is None and e["status"] == InspectionStatus.ANNOTATOR_ACTION_REQUIRED.value
        ]

        unanswered_comment_list = [
            e for e in unprocessed_inspection_list if not exists_answered_comment(e["inspection_id"])
        ]
        return unanswered_comment_list

    def complete_task_for_annotation_phase(
        self, task: Task, my_account_id: str, reply_comment: Optional[str] = None,
    ):
        """
        annotation phaseのタスクを完了状態にする。

        Args:
            project_id:
            task: 操作対象のタスク。annotation phase状態であること前提。
            reply_comment:
            my_account_id:
            changed_operator:

        Returns:

        """

        unanswered_comment_list_dict: Dict[str, List[Inspection]] = {}
        for input_data_id in task.input_data_id_list:
            unanswered_comment_list = self.get_unanswered_comment_list(task, input_data_id)
            unanswered_comment_list_dict[input_data_id] = unanswered_comment_list

        unanswered_comment_count_for_task = sum([len(e) for e in unanswered_comment_list_dict.values()])
        if unanswered_comment_count_for_task == 0:
            # 担当者変更
            self.change_to_working_status(task, my_account_id)
            self.facade.complete_task(task.project_id, task.task_id, my_account_id)
            logger.info(f"{task.task_id}: {task.phase.value}  {task.phase_stage} フェーズを完了状態にしました。")
            return
        else:
            logger.debug(f"{task.task_id}: 未回答の検査コメントが {unanswered_comment_count_for_task} 件あります。")
            if reply_comment is None:
                logger.warning(f"{task.task_id}: 未回答の検査コメントがある({unanswered_comment_count_for_task} 件)ため、スキップします。")
                return
            else:
                # 担当者変更
                changed_operator = self.change_to_working_status(task, my_account_id)
                if changed_operator:
                    time.sleep(2)

                logger.debug(f"{task.task_id}: 未回答の検査コメント {unanswered_comment_count_for_task} 件に対して、返信コメントを付与します。")
                for input_data_id, unanswered_comment_list in unanswered_comment_list_dict.items():
                    if len(unanswered_comment_list) == 0:
                        continue
                    self.reply_inspection_comment(
                        task,
                        input_data_id=input_data_id,
                        unanswered_comment_list=unanswered_comment_list,
                        reply_comment=reply_comment,
                        commenter_account_id=my_account_id,
                    )

                self.facade.complete_task(task.project_id, task.task_id, my_account_id)
                logger.info(f"{task.task_id}: {task.phase.value}  {task.phase_stage} フェーズを完了状態にしました。")

    def complete_task_for_inspection_acceptance_phase(
        self, task: Task, my_account_id: str, inspection_status: Optional[InspectionStatus] = None,
    ):
        unprocessed_inspection_list_dict: Dict[str, List[Inspection]] = {}
        for input_data_id in task.input_data_id_list:
            unprocessed_inspection_list = self.get_unprocessed_inspection_list(task, input_data_id)
            unprocessed_inspection_list_dict[input_data_id] = unprocessed_inspection_list

        unprocessed_inspection_count = sum([len(e) for e in unprocessed_inspection_list_dict.values()])

        if unprocessed_inspection_count == 0:
            self.change_to_working_status(task, my_account_id)
            self.facade.complete_task(task.project_id, task.task_id, my_account_id)
            logger.info(f"{task.task_id}: {task.phase.value} {task.phase_stage} フェーズを完了状態にしました。")
            return

        else:
            logger.debug(f"{task.task_id}: 未処置の検査コメントが {unprocessed_inspection_count} 件あります。")
            if inspection_status is None:
                logger.warning(f"{task.task_id}: 未処置の検査コメントが {unprocessed_inspection_count} 件あるため、スキップします。")
                return

            changed_operator = self.change_to_working_status(task, my_account_id)
            if changed_operator:
                time.sleep(2)

            logger.debug(f"{task.task_id}: 未処置の検査コメントを、{inspection_status.value} 状態にします。")
            for input_data_id, unprocessed_inspection_list in unprocessed_inspection_list_dict.items():
                if len(unprocessed_inspection_list) == 0:
                    continue

                self.update_status_of_inspections(
                    task.project_id,
                    task.task_id,
                    input_data_id,
                    inspection_list=unprocessed_inspection_list,
                    inspection_status=inspection_status,
                )

            self.facade.complete_task(task.project_id, task.task_id, my_account_id)
            logger.info(f"{task.task_id}: {task.phase.value}  {task.phase_stage} フェーズを完了状態にしました。")

    def complete_task_list(
        self,
        project_id: str,
        task_id_list: List[str],
        target_phase: TaskPhase,
        target_phase_stage: int,
        reply_comment: Optional[str] = None,
        inspection_status: Optional[InspectionStatus] = None,
    ):
        """
        検査コメントのstatusを変更（対応完了 or 対応不要）にした上で、タスクを受け入れ完了状態にする
        Args:
            project_id: 対象のproject_id
            task_id_list:
            target_phase: 操作対象のタスクフェーズ
            target_phase_stage: 操作対象のタスクのフェーズステージ
            inspection_status: 変更後の検査コメントの状態
            reply_comment: 未回答の検査コメントに対する指摘
            inspection_status: 未処置の検査コメントの状態
        """
        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])

        my_account_id = self.facade.get_my_account_id()
        project_title = self.facade.get_project_title(project_id)
        logger.info(f"{project_title} のタスク {len(task_id_list)} 件に対して、今のフェーズを完了状態にします。")

        completed_task_count = 0
        for task_index, task_id in enumerate(task_id_list):
            dict_task = self.service.wrapper.get_task_or_none(project_id, task_id)
            if dict_task is None:
                logger.warning(f"{task_id} のタスクを取得できませんでした。")
                continue

            task: Task = Task.from_dict(dict_task)  # type: ignore
            logger.info(
                f"{task_index+1} 件目: タスク情報 task_id={task_id}, "
                f"phase={task.phase.value}, phase_stage={task.phase_stage}, status={task.status.value}"
            )
            if not (task.phase == target_phase and task.phase_stage == target_phase_stage):
                logger.warning(f"{task_id} は操作対象のフェーズ、フェーズステージではないため、スキップします。")
                continue

            if task.status == TaskStatus.COMPLETE:
                logger.warning(f"{task_id} は既に完了状態であるため、スキップします。")
                continue

            try:
                if task.phase == TaskPhase.ANNOTATION:
                    self.complete_task_for_annotation_phase(
                        task, my_account_id=my_account_id, reply_comment=reply_comment
                    )
                else:
                    self.complete_task_for_inspection_acceptance_phase(
                        task, my_account_id=my_account_id, inspection_status=inspection_status
                    )

                completed_task_count += 1
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(e)
                logger.warning(f"{task_id}: {task.phase} フェーズを完了状態にするのに失敗しました。")
                logger.exception(e)
                new_task: Task = Task.from_dict(  # type: ignore
                    self.service.wrapper.get_task_or_none(project_id, task_id)
                )
                if new_task.status == TaskStatus.WORKING and new_task.account_id == my_account_id:
                    self.facade.change_to_break_phase(project_id, task_id, my_account_id)
                continue

        logger.info(f"{completed_task_count} / {len(task_id_list)} 件のタスクに対して、今のフェーズを完了状態にしました。")

    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        if args.phase == TaskPhase.ANNOTATION.value:
            if args.inspection_status is not None:
                logger.warning(f"'--phase'に'{TaskPhase.ANNOTATION.value}'を指定しているとき、" f"'--inspection_status'の値は無視されます。")
        elif args.phase in [TaskPhase.INSPECTION.value, TaskPhase.ACCEPTANCE.value]:
            if args.reply_comment is not None:
                logger.warning(
                    f"'--phase'に'{TaskPhase.INSPECTION.value}'または'{TaskPhase.ACCEPTANCE.value}'を指定しているとき、"
                    f"'--reply_comment'の値は無視されます。"
                )
        return True

    def main(self):
        args = self.args

        if not self.validate(args):
            return

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        inspection_status = InspectionStatus(args.inspection_status) if args.inspection_status is not None else None
        self.complete_task_list(
            args.project_id,
            task_id_list=task_id_list,
            target_phase=TaskPhase(args.phase),
            target_phase_stage=args.phase_stage,
            inspection_status=inspection_status,
            reply_comment=args.reply_comment,
        )


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id(required=True)

    parser.add_argument(
        "--phase",
        type=str,
        choices=[TaskPhase.ANNOTATION.value, TaskPhase.INSPECTION.value, TaskPhase.ACCEPTANCE.value],
        help=("操作対象のタスクのフェーズを指定してください。"),
    )

    parser.add_argument(
        "--phase_stage", type=int, default=1, help=("操作対象のタスクのフェーズのステージ番号を指定してください。デフォルトは'1'です。"),
    )

    parser.add_argument(
        "--reply_comment",
        type=str,
        help=(
            f"未回答の検査コメントに対する返信コメントを指定してください。"
            f"'--phase'に'{TaskPhase.ANNOTATION.value}' を指定したときのみ有効なオプションです。"
            f"指定しない場合は、未回答の検査コメントを含むタスクをスキップします。"
        ),
    )

    parser.add_argument(
        "--inspection_status",
        type=str,
        choices=[InspectionStatus.ERROR_CORRECTED.value, InspectionStatus.NO_CORRECTION_REQUIRED.value],
        help=(
            "操作対象のフェーズ未処置の検査コメントをどの状態に変更するかを指定します。"
            f"'--phase'に'{TaskPhase.INSPECTION.value}'または'{TaskPhase.ACCEPTANCE.value}' を指定したときのみ有効なオプションです。"
            "指定しない場合、未処置の検査コメントが含まれるタスクはスキップします。"
            f"{InspectionStatus.ERROR_CORRECTED.value}: 対応完了,"
            f"{InspectionStatus.NO_CORRECTION_REQUIRED.value}: 対応不要"
        ),
    )

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ComleteTasks(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "complete"
    subcommand_help = "タスクを完了状態にして次のフェーズに進めます。（教師付の提出、検査/受入の合格）"
    description = (
        "タスクを完了状態にして次のフェーズに進めます。（教師付の提出、検査/受入の合格） "
        "教師付フェーズを完了にする場合は、未回答の検査コメントに対して返信することができます"
        "（未回答の検査コメントに対して返信しないと、タスクを提出できないため）。"
        "検査/受入フェーズを完了する場合は、未処置の検査コメントを対応完了/対応不要状態に変更できます"
        "（未処置の検査コメントが残っている状態では、タスクを合格にできないため）。"
    )
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
