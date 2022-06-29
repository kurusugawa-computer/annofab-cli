from __future__ import annotations

import argparse
import logging
import multiprocessing
import sys
import uuid
from functools import partial
from typing import Any, Dict, List, Optional, Tuple

import annofabapi.utils
import dateutil
import requests
from annofabapi.dataclass.task import Task
from annofabapi.models import CommentStatus, Inspection, ProjectMemberRole, TaskPhase, TaskStatus
from more_itertools import first_true

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    AbstractCommandLineWithConfirmInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery, match_task_with_query

logger = logging.getLogger(__name__)

InspectionJson = Dict[str, Dict[str, List[Inspection]]]
"""
Dict[task_id, Dict[input_data_id, List[Inspection]]] の検査コメント情報
"""


class CompleteTasksMain(AbstractCommandLineWithConfirmInterface):
    def __init__(self, service: annofabapi.Resource, all_yes: bool = False):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        AbstractCommandLineWithConfirmInterface.__init__(self, all_yes)

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
        comment: str,
    ):
        """
        未回答の検査コメントに対して、返信を付与する。
        """

        def to_req_inspection(i: Inspection) -> Dict[str, Any]:
            return {
                "comment": comment,
                "comment_id": str(uuid.uuid4()),
                "phase": task.phase.value,
                "phase_stage": task.phase_stage,
                "account_id": self.service.api.account_id,
                "comment_type": "inspection",
                "comment_node": {"root_comment_id": i["comment_id"], "_type": "Reply"},
                "_type": "Put",
            }

        request_body = [to_req_inspection(e) for e in unanswered_comment_list]

        return self.service.api.batch_update_comments(
            task.project_id, task.task_id, input_data_id, request_body=request_body
        )[0]

    def update_status_of_inspections(
        self,
        task: Task,
        input_data_id: str,
        comment_list: List[dict[str, Any]],
        comment_status: CommentStatus,
    ):

        if comment_list is None or len(comment_list) == 0:
            logger.warning(f"変更対象の検査コメントはなかった。task_id = {task.task_id}, input_data_id = {input_data_id}")
            return

        def to_req_inspection(comment: dict[str, Any]) -> dict[str, Any]:
            tmp = {
                key: comment[key]
                for key in [
                    "comment",
                    "comment_id",
                    "phase",
                    "phase_stage",
                    "account_id",
                    "comment_type",
                    "comment_node",
                    "phrases",
                    "datetime_for_sorting",
                ]
            }
            tmp["_type"] = "Put"
            tmp["comment_node"]["status"] = comment_status.value
            return tmp

        request_body = [to_req_inspection(e) for e in comment_list]

        self.service.api.batch_update_comments(task.project_id, task.task_id, input_data_id, request_body=request_body)

        logger.debug(f"{task.task_id}, {input_data_id}, {len(comment_list)}件 検査コメントの状態を変更")

    def get_unprocessed_inspection_list(self, task: Task, input_data_id: str) -> List[Inspection]:
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
        comment_list, _ = self.service.api.get_comments(
            task.project_id, task.task_id, input_data_id, query_params={"v": "2"}
        )
        return [
            e
            for e in comment_list
            if e["comment_type"] == "inspection"
            and e["phase"] == task.phase.value
            and e["phase_stage"] == task.phase_stage
            and e["comment_node"]["_type"] == "Root"
            and e["comment_node"]["status"] == "open"
        ]

    def change_to_working_status(self, task: Task) -> Task:
        """
        必要なら担当者を変更して、作業中状態にします。

        Args:
            task:

        Returns:
            作業中状態後のタスク
        """
        # 担当者変更
        my_account_id = self.service.api.account_id
        try:
            last_updated_datetime = None
            if task.account_id != my_account_id:
                _task = self.service.wrapper.change_task_operator(
                    task.project_id, task.task_id, my_account_id, last_updated_datetime=task.updated_datetime
                )
                last_updated_datetime = _task["updated_datetime"]
                logger.debug(f"{task.task_id}: 担当者を自分自身に変更しました。")

            dict_task = self.service.wrapper.change_task_status_to_working(
                project_id=task.project_id, task_id=task.task_id, last_updated_datetime=last_updated_datetime
            )
            return Task.from_dict(dict_task)

        except requests.HTTPError:
            logger.warning(f"{task.task_id}: 担当者の変更、または作業中状態への変更に失敗しました。", exc_info=True)
            raise

    def get_unanswered_comment_list(self, task: Task, input_data_id: str) -> List[Inspection]:
        """
        未回答の検査コメントのリストを取得する。

        Returns:

        """

        def exists_answered_comment(parent_comment_id: str) -> bool:
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
            # 教師付フェーズになった日時より、後に付与された返信コメントを取得する
            answered_comment = first_true(
                comment_list,
                pred=lambda e: e["comment_node"]["_type"] == "Reply"
                and e["comment_node"]["root_comment_id"] == parent_comment_id
                and dateutil.parser.parse(e["created_datetime"]) >= dateutil.parser.parse(task_started_datetime),
            )
            return answered_comment is not None

        comment_list, _ = self.service.api.get_comments(
            task.project_id, task.task_id, input_data_id, query_params={"v": "2"}
        )
        # 未処置の検査コメント
        unprocessed_inspection_list = [
            e
            for e in comment_list
            if e["comment_type"] == "inspection"
            and e["comment_node"]["_type"] == "Root"
            and e["comment_node"]["status"] == "open"
        ]

        unanswered_comment_list = [
            e for e in unprocessed_inspection_list if not exists_answered_comment(e["comment_id"])
        ]
        return unanswered_comment_list

    def complete_task_for_annotation_phase(
        self,
        task: Task,
        reply_comment: Optional[str] = None,
    ) -> bool:
        """
        annotation phaseのタスクを完了状態にする。

        Args:
            project_id:
            task: 操作対象のタスク。annotation phase状態であること前提。
            reply_comment: 未処置の検査コメントに対する返信コメント。Noneの場合、スキップする。

        Returns:
            成功したかどうか
        """

        unanswered_comment_list_dict: Dict[str, List[Inspection]] = {}
        for input_data_id in task.input_data_id_list:
            unanswered_comment_list = self.get_unanswered_comment_list(task, input_data_id)
            unanswered_comment_list_dict[input_data_id] = unanswered_comment_list

        unanswered_comment_count_for_task = sum(len(e) for e in unanswered_comment_list_dict.values())

        logger.debug(f"{task.task_id}: 未回答の検査コメントが {unanswered_comment_count_for_task} 件あります。")
        if unanswered_comment_count_for_task > 0:
            if reply_comment is None:
                logger.warning(f"{task.task_id}: 未回答の検査コメントに対する返信コメント（'--reply_comment'）が指定されていないので、スキップします。")
                return False

        if not self.confirm_processing(f"タスク'{task.task_id}'の教師付フェーズを次のフェーズに進めますか？"):
            return False

        task = self.change_to_working_status(task)
        if unanswered_comment_count_for_task > 0:
            assert reply_comment is not None
            logger.debug(f"{task.task_id}: 未回答の検査コメント {unanswered_comment_count_for_task} 件に対して、返信コメントを付与します。")
            for input_data_id, unanswered_comment_list in unanswered_comment_list_dict.items():
                if len(unanswered_comment_list) == 0:
                    continue
                self.reply_inspection_comment(
                    task,
                    input_data_id=input_data_id,
                    unanswered_comment_list=unanswered_comment_list,
                    comment=reply_comment,
                )

        self.service.wrapper.complete_task(task.project_id, task.task_id, last_updated_datetime=task.updated_datetime)
        logger.info(f"{task.task_id}: 教師付フェーズをフェーズに進めました。")
        return True

    def complete_task_for_inspection_acceptance_phase(
        self,
        task: Task,
        inspection_status: Optional[CommentStatus] = None,
    ) -> bool:

        unprocessed_inspection_list_dict: Dict[str, List[Inspection]] = {}
        for input_data_id in task.input_data_id_list:
            unprocessed_inspection_list = self.get_unprocessed_inspection_list(task, input_data_id)
            unprocessed_inspection_list_dict[input_data_id] = unprocessed_inspection_list

        unprocessed_inspection_count = sum(len(e) for e in unprocessed_inspection_list_dict.values())

        logger.debug(f"{task.task_id}: 未処置の検査コメントが {unprocessed_inspection_count} 件あります。")
        if unprocessed_inspection_count > 0:
            if inspection_status is None:
                logger.warning(f"{task.task_id}: 未処置の検査コメントに対する対応方法（'--inspection_status'）が指定されていないので、スキップします。")
                return False

        if not self.confirm_processing(f"タスク'{task.task_id}'の検査/受入フェーズを次のフェーズに進めますか？"):
            return False

        task = self.change_to_working_status(task)

        if unprocessed_inspection_count > 0:
            assert inspection_status is not None
            logger.debug(
                f"{task.task_id}: 未処置の検査コメント {unprocessed_inspection_count} 件を、{inspection_status.value} 状態にします。"
            )
            for input_data_id, unprocessed_inspection_list in unprocessed_inspection_list_dict.items():
                if len(unprocessed_inspection_list) == 0:
                    continue

                self.update_status_of_inspections(
                    task,
                    input_data_id,
                    comment_list=unprocessed_inspection_list,
                    comment_status=inspection_status,
                )

        self.service.wrapper.complete_task(task.project_id, task.task_id, last_updated_datetime=task.updated_datetime)
        logger.info(f"{task.task_id}: 検査/受入フェーズを次のフェーズに進めました。")
        return True

    @staticmethod
    def _validate_task(
        task: Task, target_phase: TaskPhase, target_phase_stage: int, task_query: Optional[TaskQuery]
    ) -> bool:
        if not (task.phase == target_phase and task.phase_stage == target_phase_stage):
            logger.warning(f"{task.task_id} は操作対象のフェーズ、フェーズステージではないため、スキップします。")
            return False

        if task.status in {TaskStatus.COMPLETE, TaskStatus.WORKING}:
            logger.warning(f"{task.task_id} は作業中また完了状態であるため、スキップします。")
            return False

        if not match_task_with_query(task, task_query):
            logger.debug(f"{task.task_id} は `--task_query` の条件にマッチしないため、スキップします。task_query={task_query}")
            return False
        return True

    def complete_task(
        self,
        project_id: str,
        task_id: str,
        target_phase: TaskPhase,
        target_phase_stage: int,
        reply_comment: Optional[str] = None,
        inspection_status: Optional[CommentStatus] = None,
        task_query: Optional[TaskQuery] = None,
        task_index: Optional[int] = None,
    ) -> bool:
        logging_prefix = f"{task_index + 1} 件目" if task_index is not None else ""

        dict_task = self.service.wrapper.get_task_or_none(project_id, task_id)
        if dict_task is None:
            logger.warning(f"{logging_prefix}: task_id='{task_id}'のタスクは存在しないので、スキップします。")
            return False

        task: Task = Task.from_dict(dict_task)
        logger.info(
            f"{logging_prefix} : タスク情報 task_id={task_id}, "
            f"phase={task.phase.value}, phase_stage={task.phase_stage}, status={task.status.value}"
        )
        if not self._validate_task(
            task, target_phase=target_phase, target_phase_stage=target_phase_stage, task_query=task_query
        ):
            return False

        try:
            if task.phase == TaskPhase.ANNOTATION:
                return self.complete_task_for_annotation_phase(task, reply_comment=reply_comment)
            else:
                return self.complete_task_for_inspection_acceptance_phase(task, inspection_status=inspection_status)

        except Exception:  # pylint: disable=broad-except
            logger.warning(f"{task_id}: {task.phase} フェーズを完了状態にするのに失敗しました。", exc_info=True)
            new_task: Task = Task.from_dict(self.service.wrapper.get_task_or_none(project_id, task_id))
            if new_task.status == TaskStatus.WORKING and new_task.account_id == self.service.api.account_id:
                self.service.wrapper.change_task_status_to_break(project_id, task_id)
            return False

    def complete_task_for_task_wrapper(
        self,
        tpl: Tuple[int, str],
        project_id: str,
        target_phase: TaskPhase,
        target_phase_stage: int,
        reply_comment: Optional[str] = None,
        inspection_status: Optional[CommentStatus] = None,
        task_query: Optional[TaskQuery] = None,
    ) -> bool:
        task_index, task_id = tpl
        try:
            return self.complete_task(
                project_id=project_id,
                task_id=task_id,
                task_index=task_index,
                target_phase=target_phase,
                target_phase_stage=target_phase_stage,
                reply_comment=reply_comment,
                inspection_status=inspection_status,
                task_query=task_query,
            )
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"タスク'{task_id}'のフェーズを完了状態にするのに失敗しました。", exc_info=True)
            return False

    def complete_task_list(
        self,
        project_id: str,
        task_id_list: List[str],
        target_phase: TaskPhase,
        target_phase_stage: int,
        reply_comment: Optional[str] = None,
        inspection_status: Optional[CommentStatus] = None,
        task_query: Optional[TaskQuery] = None,
        parallelism: Optional[int] = None,
    ):
        """
        検査コメントのstatusを変更（対応完了 or 対応不要）にした上で、タスクを受け入れ完了状態にする
        Args:
            project_id: 対象のproject_id
            task_id_list:
            target_phase: 操作対象のタスクフェーズ
            target_phase_stage: 操作対象のタスクのフェーズステージ
            reply_comment: 未回答の検査コメントに対する指摘
            inspection_status: 未処置の検査コメントの状態
        """
        if task_query is not None:
            task_query = self.facade.set_account_id_of_task_query(project_id, task_query)

        project_title = self.facade.get_project_title(project_id)
        logger.info(f"{project_title} のタスク {len(task_id_list)} 件に対して、今のフェーズを完了状態にします。")

        success_count = 0

        if parallelism is not None:
            partial_func = partial(
                self.complete_task_for_task_wrapper,
                project_id=project_id,
                target_phase=target_phase,
                target_phase_stage=target_phase_stage,
                reply_comment=reply_comment,
                inspection_status=inspection_status,
                task_query=task_query,
            )

            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(partial_func, enumerate(task_id_list))
                success_count = len([e for e in result_bool_list if e])

        else:
            # 逐次処理
            for task_index, task_id in enumerate(task_id_list):
                try:
                    result = self.complete_task(
                        project_id,
                        task_id,
                        task_index=task_index,
                        target_phase=target_phase,
                        target_phase_stage=target_phase_stage,
                        reply_comment=reply_comment,
                        inspection_status=inspection_status,
                        task_query=task_query,
                    )
                    if result:
                        success_count += 1
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"タスク'{task_id}'のフェーズを完了状態にするのに失敗しました。", exc_info=True)
                    continue

        logger.info(f"{success_count} / {len(task_id_list)} 件のタスクに対して、今のフェーズを完了状態にしました。")


class CompleteTasks(AbstractCommandLineInterface):
    """
    タスクを受け入れ完了にする
    """

    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli task complete: error:"
        if args.phase == TaskPhase.ANNOTATION.value:
            if args.inspection_status is not None:
                logger.warning(f"'--phase'に'{TaskPhase.ANNOTATION.value}'を指定しているとき、" f"'--inspection_status'の値は無視されます。")
        elif args.phase in [TaskPhase.INSPECTION.value, TaskPhase.ACCEPTANCE.value]:
            if args.reply_comment is not None:
                logger.warning(
                    f"'--phase'に'{TaskPhase.INSPECTION.value}'または'{TaskPhase.ACCEPTANCE.value}'を指定しているとき、"
                    f"'--reply_comment'の値は無視されます。"
                )

        if args.parallelism is not None and not args.yes:
            print(
                f"{COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、'--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        inspection_status = CommentStatus(args.inspection_status) if args.inspection_status is not None else None

        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])

        dict_task_query = annofabcli.common.cli.get_json_from_args(args.task_query)
        task_query: Optional[TaskQuery] = TaskQuery.from_dict(dict_task_query) if dict_task_query is not None else None

        main_obj = CompleteTasksMain(self.service, all_yes=self.all_yes)
        main_obj.complete_task_list(
            project_id,
            task_id_list=task_id_list,
            target_phase=TaskPhase(args.phase),
            target_phase_stage=args.phase_stage,
            inspection_status=inspection_status,
            reply_comment=args.reply_comment,
            task_query=task_query,
            parallelism=args.parallelism,
        )


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id(required=True)

    parser.add_argument(
        "--phase",
        type=str,
        required=True,
        choices=[TaskPhase.ANNOTATION.value, TaskPhase.INSPECTION.value, TaskPhase.ACCEPTANCE.value],
        help=("操作対象のタスクのフェーズを指定してください。"),
    )

    parser.add_argument(
        "--phase_stage",
        type=int,
        default=1,
        help=("操作対象のタスクのフェーズのステージ番号を指定してください。デフォルトは'1'です。"),
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
        choices=[CommentStatus.RESOLVED.value, CommentStatus.CLOSED.value],
        help=(
            "操作対象のフェーズ未処置の検査コメントをどの状態に変更するかを指定します。"
            f"'--phase'に'{TaskPhase.INSPECTION.value}'または'{TaskPhase.ACCEPTANCE.value}' を指定したときのみ有効なオプションです。"
            "指定しない場合、未処置の検査コメントが含まれるタスクはスキップします。"
            f"{CommentStatus.RESOLVED.value}: 対応完了,"
            f"{CommentStatus.CLOSED.value}: 対応不要"
        ),
    )

    argument_parser.add_task_query()

    parser.add_argument(
        "--parallelism", type=int, help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。"
    )

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CompleteTasks(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "complete"
    subcommand_help = "タスクを完了状態にして次のフェーズに進めます。（教師付の提出、検査/受入の合格）"
    description = (
        "タスクを完了状態にして次のフェーズに進めます。（教師付の提出、検査/受入の合格） "
        "教師付フェーズを完了にする場合は、未回答の検査コメントに対して返信することができます"
        "（未回答の検査コメントに対して返信しないと、タスクを提出できないため）。"
        "検査/受入フェーズを完了する場合は、未処置の検査コメントを対応完了/対応不要状態に変更できます"
        "（未処置の検査コメントが残っている状態では、タスクを合格にできないため）。"
        "作業中また完了状態のタスクは、次のフェーズに進めません。"
    )
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
