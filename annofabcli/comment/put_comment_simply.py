import logging
import multiprocessing
import uuid
from collections.abc import Collection
from dataclasses import dataclass
from functools import partial
from typing import Any, Optional

import annofabapi
import annofabapi.utils
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

    data: Optional[dict[str, Any]]
    """コメントを付与する位置や区間"""

    phrases: Optional[list[str]] = None
    """参照している定型指摘ID"""


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
                "comment_id": str(uuid.uuid4()),
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

    def _can_add_comment(
        self,
        task: dict[str, Any],
    ) -> bool:
        task_id = task["task_id"]

        if self.comment_type == CommentType.INSPECTION:  # noqa: SIM102
            if task["phase"] == TaskPhase.ANNOTATION.value:
                logger.warning(f"task_id='{task_id}': 教師付フェーズなので、検査コメントを付与できません。")
                return False

        if task["status"] not in [TaskStatus.NOT_STARTED.value, TaskStatus.WORKING.value, TaskStatus.BREAK.value]:
            logger.warning(f"task_id='{task_id}' : タスクの状態が未着手,作業中,休憩中 以外の状態なので、コメントを付与できません。（task_status='{task['status']}'）")
            return False
        return True

    def put_comment_for_task(
        self,
        task_id: str,
        comment_info: AddedSimpleComment,
        task_index: Optional[int] = None,
    ) -> bool:
        """
        タスクにコメントを付与します。

        Args:
            task_id: タスクID
            comment_info: コメント情報
            task_index: タスクの連番

        Returns:
            付与したコメントの数
        """
        logging_prefix = f"{task_index + 1} 件目" if task_index is not None else ""

        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"{logging_prefix} : task_id='{task_id}' のタスクは存在しないので、スキップします。")
            return False

        logger.debug(f"{logging_prefix} : task_id = {task['task_id']}, status = {task['status']}, phase = {task['phase']}, ")

        if not self._can_add_comment(
            task=task,
        ):
            return False

        if not self.confirm_processing(f"task_id='{task_id}' のタスクに{self.comment_type_name}を付与しますか？"):
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

    def add_comments_for_task_wrapper(self, tpl: tuple[int, str], comment_info: AddedSimpleComment) -> bool:
        task_index, task_id = tpl
        try:
            return self.put_comment_for_task(task_id=task_id, comment_info=comment_info, task_index=task_index)
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"task_id='{task_id}' :: コメントの付与に失敗しました。", exc_info=True)
            return False

    def put_comment_for_task_list(
        self,
        task_ids: Collection[str],
        comment_info: AddedSimpleComment,
        parallelism: Optional[int] = None,
    ) -> None:
        logger.info(f"{len(task_ids)} 件のタスクに{self.comment_type_name}を付与します。")

        if parallelism is not None:
            func = partial(self.add_comments_for_task_wrapper, comment_info=comment_info)
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
                    )
                    if result:
                        success_count += 1
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"task_id='{task_id}' :: {self.comment_type_name}の付与に失敗しました。", exc_info=True)
                    continue

        logger.info(f"{success_count} / {len(task_ids)} 件のタスクに{self.comment_type_name}を付与しました。")
