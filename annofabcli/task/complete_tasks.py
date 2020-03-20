import argparse
import logging
import dateutil
import time
import uuid
from typing import Any, Dict, List, Optional

import annofabapi.utils
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
                    "phase": task.phase,
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
        logger.debug(request_body)
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

    def complete_acceptance_task(
        self,
        project_id: str,
        task: Task,
        inspection_status: InspectionStatus,
        input_data_dict: Dict[str, List[Inspection]],
        account_id: str,
        changed_operator: bool = False,
    ):
        """
        検査コメントのstatusを変更（対応完了 or 対応不要）にした上で、タスクを受け入れ完了状態にする

        Args:
            project_id:
            task:
            inspection_status:
            input_data_dict:
            account_id:
            changed_operator: 担当者を変更したかどうか。APIの都合で、担当者を変えた場合はsleepした方がよいため。

        Returns:

        """
        task_id = task.task_id

        if changed_operator and sum([len(e) for e in input_data_dict.values()]) > 0:
            # 担当者変更してから数秒待たないと、検査コメントの付与に失敗する(「検査コメントの作成日時が不正です」と言われる）
            time.sleep(3)

        # 検査コメントの状態を変更する
        for input_data_id, inspection_list in input_data_dict.items():
            self.update_status_of_inspections(
                project_id, task_id, input_data_id, inspection_list=inspection_list, inspection_status=inspection_status
            )

        # タスクの状態を検査する
        self.facade.complete_task(project_id, task_id, account_id)
        logger.info(f"{task_id}: 検査/受入フェーズを完了状態にしました。")

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

    def change_to_working_status(self, task: Task, my_account_id: str):
        # 担当者変更
        changed_operator = False
        try:
            if task.account_id != my_account_id:
                self.facade.change_operator_of_task(task.project_id, task.task_id, my_account_id)
                changed_operator = True
                logger.debug(f"{task.task_id}: 担当者を自分自身に変更しました。")

            self.facade.change_to_working_status(task.project_id, task.task_id, my_account_id)

        except requests.HTTPError as e:
            logger.warning(e)
            logger.warning(f"{task.task_id}: 担当者の変更、または作業中状態への変更に失敗しました。")


    def get_unanswered_comment_list(self, task: Task, input_data_id: str) -> List[Inspection]:
        """
        未回答の検査コメントのリストを取得する。

        Returns:

        """
        def exists_answered_comment(parent_inspection_comment_id: str) -> bool:
            """
            回答済の返信コメントがあるかどうか

            Args:
                parent_inspection_comment_id:

            Returns:

            """
            return first_true(inspection_list,
                              pred=lambda e: e["parent_inspection_comment_id"] == parent_inspection_comment_id
                                             and dateutil.parser.parse(e["created_datetime"]) > dateutil.parser.parse(
                                  task.started_datetime)) is not None

        inspection_list, _ = self.service.api.get_inspections(task.project_id, task.task_id, input_data_id)
        # 未処置の検査コメント
        unprocessed_inspection_list = [
                e
                for e in inspection_list
                if e["parent_inspection_comment_id"] is None
                and e["status"] == InspectionStatus.ANNOTATOR_ACTION_REQUIRED.value
        ]

        unanswered_comment_list = [
            e for e in unprocessed_inspection_list if not exists_answered_comment(e["parent_inspection_comment_id"])
        ]
        return unanswered_comment_list




    def complete_task_for_annotation_phase(
        self,
        project_id: str,
        task: Task,
        my_account_id: str,
        reply_comment: Optional[str] = None,
        changed_operator: bool = False,
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

        exists_unanswered_comment = False
        for input_data_id in task.input_data_id_list:
            unanswered_comment_list = self.get_unanswered_comment_list(task, input_data_id)
            if len(unanswered_comment_list) > 0:
                exists_unanswered_comment = True
                logger.info(f"{task.task_id}: input_data_id={input_data_id}: 未回答の検査コメントが {len(unanswered_comment_list)} 件ありました。")
                if reply_comment is not None:
                    # 返信する
                    self.reply_inspection_comment(
                        task,
                        input_data_id=input_data_id,
                        unanswered_comment_list=unanswered_comment_list,
                        reply_comment=reply_comment,
                        commenter_account_id=my_account_id,
                    )

        if reply_comment is not None or not exists_unanswered_comment:
            self.facade.complete_task(project_id, task.task_id, my_account_id)
            logger.info(f"{task.task_id}: {task.phase.value} フェーズを完了状態にしました。")
        else:
            logger.warning(f"{task.task_id}: 未回答の検査コメントがあるため、スキップします。")

        # if task.phase == TaskPhase.ANNOTATION or len(unprocessed_inspection_list) == 0:
        #     self.facade.complete_task(project_id, task.task_id, my_account_id)
        #     logger.info(f"{task.task_id}: {task.phase.value} フェーズを完了状態にしました。")
        #     return
        #
        # # if task.phase == TaskPhase.ANNOTATION and len(unprocessed_inspection_list) > 0:
        # if task.phase == TaskPhase.ANNOTATION and len(unprocessed_inspection_list) > 0:
        #     # 返信する
        #     # TODO 二重で返信しないようにする
        #     # TODO 返信コメントをコマンドライン引数から取得できるようにする
        #     # 検査コメントの状態を変更する
        #     for input_data_id in task.input_data_id_list:
        #
        #     self.facade.complete_task(project_id, task.task_id, my_account_id)
        #     return
        #
        # if change_inspection_status is None:
        #     logger.info(f"{task.task_id}: 未処置の検査コメントがあるためスキップします。")
        #     return
        #
        # if target_inspections_dict is None:
        #     input_data_dict = self.inspection_list_to_input_data_dict(unprocessed_inspection_list)
        # else:
        #     input_data_dict = target_inspections_dict[task.task_id]
        #
        # self.complete_acceptance_task(
        #     project_id,
        #     task,
        #     inspection_status=change_inspection_status,
        #     input_data_dict=input_data_dict,
        #     account_id=my_account_id,
        #     changed_operator=changed_operator,
        # )

    def complete_task(
        self,
        project_id: str,
        my_account_id: str,
        change_inspection_status: Optional[InspectionStatus],
        task: Task,
        unprocessed_inspection_list: List[Inspection],
        changed_operator: bool = False,
    ):
        logger.debug(f"{len(unprocessed_inspection_list)} 件 未処置コメント")
        if task.phase == TaskPhase.ANNOTATION or len(unprocessed_inspection_list) == 0:
            self.facade.complete_task(project_id, task.task_id, my_account_id)
            logger.info(f"{task.task_id}: {task.phase.value} フェーズを完了状態にしました。")
            return

        # if task.phase == TaskPhase.ANNOTATION and len(unprocessed_inspection_list) > 0:
        if task.phase == TaskPhase.ANNOTATION and len(unprocessed_inspection_list) > 0:
            # 返信する
            # TODO 二重で返信しないようにする
            # TODO 返信コメントをコマンドライン引数から取得できるようにする
            # 検査コメントの状態を変更する
            logger.debug("自動返信")
            for input_data_id in task.input_data_id_list:
                self.reply_inspection_comment(
                    project_id,
                    task,
                    input_data_id=input_data_id,
                    unprocessed_inspection_list=unprocessed_inspection_list,
                    reply_comment="対応しました（自動投稿）",
                    commenter_account_id=my_account_id,
                )

            self.facade.complete_task(project_id, task.task_id, my_account_id)
            return

        if change_inspection_status is None:
            logger.info(f"{task.task_id}: 未処置の検査コメントがあるためスキップします。")
            return

        if target_inspections_dict is None:
            input_data_dict = self.inspection_list_to_input_data_dict(unprocessed_inspection_list)
        else:
            input_data_dict = target_inspections_dict[task.task_id]

        self.complete_acceptance_task(
            project_id,
            task,
            inspection_status=change_inspection_status,
            input_data_dict=input_data_dict,
            account_id=my_account_id,
            changed_operator=changed_operator,
        )

    def complete_task_list(
        self,
        project_id: str,
        task_id_list: List[str],
        target_phase: TaskPhase,
        target_phase_stage: int,
        change_inspection_status: Optional[InspectionStatus] = None,
    ):
        """
        検査コメントのstatusを変更（対応完了 or 対応不要）にした上で、タスクを受け入れ完了状態にする
        Args:
            project_id: 対象のproject_id
            inspection_status: 変更後の検査コメントの状態
            inspection_json: 変更対象の検査コメントのJSON情報

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
                f"{task_index+1} 件目: タスク情報 task_id={task_id}, phase={task.phase.value}, phase_stage={task.phase_stage}, status={task.status.value}"
            )
            if not (task.phase == target_phase and task.phase_stage == target_phase_stage):
                logger.warning(f"{task_id} は操作対象のフェーズ、フェーズステージではないため、スキップします。")
                continue

            if task.status == TaskStatus.COMPLETE:
                logger.warning(f"{task_id} は既に完了状態であるため、スキップします。")
                continue

            unprocessed_inspection_list = self.get_unprocessed_inspection_list_by_task_id(
                project_id, task, target_phase, target_phase_stage
            )
            if len(unprocessed_inspection_list) > 0:
                logger.debug(f"未処置の検査コメントが {len(unprocessed_inspection_list)} 件あります。")
                if change_inspection_status is None:
                    logger.debug(f"{task_id}: 未処置の検査コメントがあるためスキップします。")
                    continue

            if not self.confirm_processing(f"タスク'{task_id}'の {task.phase.value} フェーズを、完了状態にしますか？"):
                continue

            # 担当者変更
            changed_operator = False
            try:
                if task.account_id != my_account_id:
                    self.facade.change_operator_of_task(project_id, task_id, my_account_id)
                    changed_operator = True
                    logger.debug(f"{task_id}: 担当者を変更しました。")

                self.facade.change_to_working_status(project_id, task_id, my_account_id)

            except requests.HTTPError as e:
                logger.warning(e)
                logger.warning(f"{task_id}: 担当者の変更に失敗しました。")
                continue

            try:
                self.complete_task(
                    project_id=project_id,
                    my_account_id=my_account_id,
                    change_inspection_status=change_inspection_status,
                    target_inspections_dict=target_inspections_dict,
                    task=task,
                    unprocessed_inspection_list=unprocessed_inspection_list,
                    changed_operator=changed_operator,
                )
                completed_task_count += 1
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(e)
                logger.warning(f"{task_id}: {task.phase} フェーズを完了状態にするのに失敗しました。")
                self.facade.change_to_break_phase(project_id, task_id, my_account_id)
                continue

        logger.info(f"{completed_task_count} / {len(task_id_list)} 件のタスクに対して、今のフェーズを完了状態にしました。")

    def main(self):
        args = self.args
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        inspection_status = InspectionStatus(args.inspection_status) if args.inspection_status is not None else None
        self.complete_task_list(
            args.project_id,
            task_id_list=task_id_list,
            target_phase=TaskPhase(args.phase),
            target_phase_stage=args.phase_stage,
            change_inspection_status=inspection_status,
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
    subcommand_help = "タスクの今のフェーズを完了状態（教師付の提出、検査/受入の合格）にします。"
    description = "タスクの今のフェーズを完了状態（教師付の提出、検査/受入の合格）にします。" "未処置の検査コメントがある場合、検査コメントを適切な状態に変更できます。"
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
