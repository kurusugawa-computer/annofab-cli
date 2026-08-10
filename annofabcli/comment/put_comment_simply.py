import logging
import multiprocessing
import uuid
from collections.abc import Collection
from dataclasses import dataclass
from functools import partial
from typing import Any

import annofabapi
from annofabapi.models import CommentType, TaskPhase, TaskStatus

from annofabcli.comment.utils import get_comment_type_name
from annofabcli.common.cli import CommandLineWithConfirm
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


@dataclass
class AddedSimpleComment:
    """
    付与するシンプルな検査コメント
    """

    comment: str
    """コメントの中身"""

    data: dict[str, Any] | None
    """コメントを付与する位置や区間"""

    phrases: list[str] | None = None
    """参照している定型指摘ID"""

    comment_id: str | None = None
    """コメントID。省略時はUUIDv4が自動生成される。"""


class PutCommentSimplyMain(CommandLineWithConfirm):
    def __init__(self, service: annofabapi.Resource, project_id: str, comment_type: CommentType, all_yes: bool = False) -> None:  # noqa: FBT001, FBT002
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.project_id = project_id

        self.comment_type = comment_type
        self.comment_type_name = get_comment_type_name(comment_type)

        CommandLineWithConfirm.__init__(self, all_yes)

    def _create_request_body(self, task: dict[str, Any], comment_info: AddedSimpleComment) -> list[dict[str, Any]]:
        """batch_update_comments に渡すリクエストボディを作成する。"""

        def _convert(comment: AddedSimpleComment) -> dict[str, Any]:
            return {
                "comment": comment.comment,
                "comment_id": comment.comment_id if comment.comment_id is not None else str(uuid.uuid4()),
                "phase": task["phase"],
                "phase_stage": task["phase_stage"],
                "comment_type": self.comment_type.value,
                "account_id": self.service.api.account_id,
                "comment_node": {"data": comment.data, "status": "open", "_type": "Root"},
                "phrases": comment.phrases,
                "_type": "Put",
            }

        return [_convert(comment_info)]

    def change_to_working_status(self, project_id: str, task: dict[str, Any]) -> dict[str, Any]:
        """
        作業中状態に遷移する。必要ならば担当者を自分自身に変更する。

        Args:
            project_id:
            task:

        Returns:
            作業中状態遷移後のタスク
        """

        task_id = task["task_id"]

        if task["account_id"] != self.service.api.account_id:
            self.service.wrapper.change_task_operator(project_id, task_id, self.service.api.account_id)
            logger.debug(f"{task_id}: 担当者を自分自身に変更しました。")

        changed_task = self.service.wrapper.change_task_status_to_working(project_id, task_id)
        return changed_task

    def cancel_acceptance_if_needed(self, task: dict[str, Any], *, cancel_acceptance: bool, logging_prefix: str = "") -> dict[str, Any]:
        """必要ならば受入完了状態を取り消す。"""

        if not self._needs_cancel_acceptance(task, cancel_acceptance=cancel_acceptance):
            return task

        task_id = task["task_id"]
        canceled_task = self.service.wrapper.cancel_completed_task(
            self.project_id,
            task_id,
            operator_account_id=task["account_id"],
            last_updated_datetime=task["updated_datetime"],
        )
        logger.debug(f"{logging_prefix} :: task_id='{task_id}'のタスクに対して受入取消を実施（完了状態から未着手状態に変更）しました。")
        return canceled_task

    def _needs_cancel_acceptance(self, task: dict[str, Any], *, cancel_acceptance: bool) -> bool:
        """受入完了状態の取消が必要かどうかを返す。"""

        if not cancel_acceptance:
            return False

        return task["phase"] == TaskPhase.ACCEPTANCE.value and task["status"] == TaskStatus.COMPLETE.value

    def _can_add_comment(
        self,
        task: dict[str, Any],
        *,
        include_break_task: bool,
        include_on_hold_task: bool,
    ) -> bool:
        task_id = task["task_id"]

        if self.comment_type == CommentType.INSPECTION:  # noqa: SIM102
            if task["phase"] == TaskPhase.ANNOTATION.value:
                logger.warning(f"task_id='{task_id}' :: フェーズが検査/受入でないため検査コメントを付与できません。 :: task_phase='{task['phase']}'")
                return False

        if task["status"] == TaskStatus.BREAK.value and not include_break_task:
            logger.info(f"task_id='{task_id}' :: タスクは休憩中状態のため、処理をスキップします。休憩中状態のタスクを処理する場合は、`--include_break_task` を指定してください。")
            return False

        if task["status"] == TaskStatus.ON_HOLD.value and not include_on_hold_task:
            logger.info(f"task_id='{task_id}' :: タスクは保留中状態のため、処理をスキップします。保留中状態のタスクを処理する場合は、`--include_on_hold_task` を指定してください。")
            return False

        if task["status"] not in [TaskStatus.NOT_STARTED.value, TaskStatus.BREAK.value, TaskStatus.ON_HOLD.value]:
            logger.warning(f"task_id='{task_id}' :: タスクの状態が未着手、休憩中、保留中以外の状態なので、コメントを付与できません。 :: task_status='{task['status']}'")
            return False
        return True

    def _can_change_operator_to_me(self, task: dict[str, Any], *, change_operator_to_me: bool, logging_prefix: str) -> bool:
        if task["account_id"] == self.service.api.account_id or change_operator_to_me:
            return True

        logger.info(f"{logging_prefix} :: task_id='{task['task_id']}' :: 自身が担当者ではないタスクに検査コメントを作成するには、`--change_operator_to_me` を指定してください。")
        return False

    def put_comment_for_task(
        self,
        task_id: str,
        comment_info: AddedSimpleComment,
        task_index: int | None = None,
        *,
        cancel_acceptance: bool = False,
        change_operator_to_me: bool = True,
        include_break_task: bool = True,
        include_on_hold_task: bool = False,
    ) -> bool:
        """
        タスクにコメントを付与します。

        Args:
            task_id: タスクID
            comment_info: コメント情報
            task_index: タスクの連番
            cancel_acceptance: Trueなら受入完了状態を取り消してからコメントを付与する。
            change_operator_to_me: 自身が担当者ではないタスクの担当者を一時的に自分自身へ変更するかどうか。
            include_break_task: 休憩中状態のタスクを処理対象に含めるかどうか。
            include_on_hold_task: 保留中状態のタスクを処理対象に含めるかどうか。

        Returns:
            付与したコメントの数
        """
        logging_prefix = f"{task_index + 1} 件目" if task_index is not None else ""

        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"{logging_prefix} : task_id='{task_id}' のタスクは存在しないので、スキップします。")
            return False

        logger.debug(f"{logging_prefix} : task_id = {task['task_id']}, status = {task['status']}, phase = {task['phase']}, ")

        needs_cancel_acceptance = self._needs_cancel_acceptance(task, cancel_acceptance=cancel_acceptance)
        if not needs_cancel_acceptance and not self._can_add_comment(task=task, include_break_task=include_break_task, include_on_hold_task=include_on_hold_task):
            return False

        if not self.confirm_processing(f"task_id='{task_id}' のタスクに{self.comment_type_name}を付与しますか？"):
            return False

        task = self.cancel_acceptance_if_needed(task, cancel_acceptance=cancel_acceptance, logging_prefix=logging_prefix)

        if not self._can_add_comment(task=task, include_break_task=include_break_task, include_on_hold_task=include_on_hold_task) or not self._can_change_operator_to_me(
            task,
            change_operator_to_me=change_operator_to_me,
            logging_prefix=logging_prefix,
        ):
            return False

        # コメントを付与するには作業中状態にする必要があるので、タスクの状態を作業中にする
        changed_task = self.change_to_working_status(self.project_id, task)

        input_data_id = task["input_data_id_list"][0]

        try:
            # コメントを付与する
            request_body = self._create_request_body(task=changed_task, comment_info=comment_info)
            self.service.api.batch_update_comments(self.project_id, task_id, input_data_id, request_body=request_body)
            logger.debug(f"{logging_prefix} :: task_id='{task_id}' のタスクにコメントを付与しました。")
            return True  # noqa: TRY300
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"{logging_prefix} :: task_id='{task_id}', input_data_id='{input_data_id}' :: コメントの付与に失敗しました。", exc_info=True)
            return False
        finally:
            self.service.wrapper.change_task_status_to_break(self.project_id, task_id)
            # 担当者が変えている場合は、元に戻す
            if task["account_id"] != changed_task["account_id"]:
                self.service.wrapper.change_task_operator(self.project_id, task_id, task["account_id"])
                logger.debug(f"task_id'{task_id}' :: 担当者を元のユーザ( account_id='{task['account_id']}'）に戻しました。")

    def add_comments_for_task_wrapper(
        self,
        tpl: tuple[int, str],
        comment_info: AddedSimpleComment,
        *,
        cancel_acceptance: bool = False,
        change_operator_to_me: bool = True,
        include_break_task: bool = True,
        include_on_hold_task: bool = False,
    ) -> bool:
        task_index, task_id = tpl
        try:
            return self.put_comment_for_task(
                task_id=task_id,
                comment_info=comment_info,
                task_index=task_index,
                cancel_acceptance=cancel_acceptance,
                change_operator_to_me=change_operator_to_me,
                include_break_task=include_break_task,
                include_on_hold_task=include_on_hold_task,
            )
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"task_id='{task_id}' :: コメントの付与に失敗しました。", exc_info=True)
            return False

    def put_comment_for_task_list(
        self,
        task_ids: Collection[str],
        comment_info: AddedSimpleComment,
        parallelism: int | None = None,
        *,
        cancel_acceptance: bool = False,
        change_operator_to_me: bool = True,
        include_break_task: bool = True,
        include_on_hold_task: bool = False,
    ) -> None:
        logger.info(f"{len(task_ids)} 件のタスクに{self.comment_type_name}を付与します。")

        if parallelism is not None:
            func = partial(
                self.add_comments_for_task_wrapper,
                comment_info=comment_info,
                cancel_acceptance=cancel_acceptance,
                change_operator_to_me=change_operator_to_me,
                include_break_task=include_break_task,
                include_on_hold_task=include_on_hold_task,
            )
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(func, enumerate(task_ids))
                success_count = len([e for e in result_bool_list if e])

        else:
            # 逐次処理
            success_count = 0
            for task_index, task_id in enumerate(task_ids):
                try:
                    result = self.put_comment_for_task(
                        task_id=task_id,
                        comment_info=comment_info,
                        task_index=task_index,
                        cancel_acceptance=cancel_acceptance,
                        change_operator_to_me=change_operator_to_me,
                        include_break_task=include_break_task,
                        include_on_hold_task=include_on_hold_task,
                    )
                    if result:
                        success_count += 1
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"task_id='{task_id}' :: {self.comment_type_name}の付与に失敗しました。", exc_info=True)
                    continue

        logger.info(f"{success_count} / {len(task_ids)} 件のタスクに{self.comment_type_name}を付与しました。")
