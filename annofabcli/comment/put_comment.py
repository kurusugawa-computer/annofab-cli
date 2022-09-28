from __future__ import annotations

import logging
import multiprocessing
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import annofabapi
import annofabapi.utils
import requests
from annofabapi.models import CommentType, TaskPhase, TaskStatus
from dataclasses_json import DataClassJsonMixin

from annofabcli.comment.utils import get_comment_type_name
from annofabcli.common.cli import AbstractCommandLineWithConfirmInterface
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


@dataclass
class AddedComment(DataClassJsonMixin):
    """
    追加対象のコメント。
    """

    comment: str
    """コメントの中身"""

    data: Optional[Dict[str, Any]]
    """コメントを付与する位置や区間"""

    annotation_id: Optional[str]
    """コメントに紐付けるアノテーションID"""

    phrases: Optional[List[str]]
    """参照している定型指摘ID"""


AddedCommentsForTask = Dict[str, List[AddedComment]]
"""
タスク配下の追加対象のコメント
keyはinput_data_id
"""

AddedComments = Dict[str, AddedCommentsForTask]
"""
追加対象のコメント
keyはtask_id
"""


class PutCommentMain(AbstractCommandLineWithConfirmInterface):
    def __init__(self, service: annofabapi.Resource, project_id: str, comment_type: CommentType, all_yes: bool = False):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.project_id = project_id

        self.comment_type = comment_type
        self.comment_type_name = get_comment_type_name(comment_type)

        AbstractCommandLineWithConfirmInterface.__init__(self, all_yes)

    def _create_request_body(
        self, task: Dict[str, Any], input_data_id: str, comments: List[AddedComment]
    ) -> List[Dict[str, Any]]:
        """batch_update_comments に渡すリクエストボディを作成する。"""

        def _create_dict_annotation_id() -> Dict[str, str]:
            content, _ = self.service.api.get_editor_annotation(self.project_id, task["task_id"], input_data_id)
            details = content["details"]
            return {e["annotation_id"]: e["label_id"] for e in details}

        dict_annotation_id_label_id = _create_dict_annotation_id()

        def _convert(comment: AddedComment) -> Dict[str, Any]:
            return {
                "comment_id": str(uuid.uuid4()),
                "phase": task["phase"],
                "phase_stage": task["phase_stage"],
                "account_id": self.service.api.account_id,
                "comment_type": self.comment_type.value,
                "comment": comment.comment,
                "comment_node": {
                    "data": comment.data,
                    "annotation_id": comment.annotation_id,
                    "label_id": dict_annotation_id_label_id.get(comment.annotation_id)
                    if comment.annotation_id is not None
                    else None,
                    "status": "open",
                    "_type": "Root",
                },
                "phrases": comment.phrases,
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
                self.service.wrapper.change_task_operator(project_id, task_id, self.service.api.account_id)
                logger.debug(f"{task_id}: 担当者を自分自身に変更しました。")

            changed_task = self.service.wrapper.change_task_status_to_working(project_id, task_id)
            return changed_task

        except requests.HTTPError:
            logger.warning(f"{task_id}: 担当者の変更、または作業中状態への変更に失敗しました。", exc_info=True)
            raise

    def _can_add_comment(
        self,
        task: Dict[str, Any],
    ) -> bool:
        task_id = task["task_id"]

        if self.comment_type == CommentType.INSPECTION:
            if task["phase"] == TaskPhase.ANNOTATION.value:
                logger.warning(f"task_id='{task_id}': 教師付フェーズなので、検査コメントを付与できません。")
                return False

        if task["status"] not in [TaskStatus.NOT_STARTED.value, TaskStatus.WORKING.value, TaskStatus.BREAK.value]:
            logger.warning(
                f"task_id='{task_id}' : タスクの状態が未着手,作業中,休憩中 以外の状態なので、コメントを付与できません。（task_status='{task['status']}'）"
            )
            return False
        return True

    def add_comments_for_task(
        self,
        task_id: str,
        comments_for_task: AddedCommentsForTask,
        task_index: Optional[int] = None,
    ) -> int:
        """
        タスクにコメントを付与します。

        Args:
            task_id: タスクID
            comments_for_task: 1つのタスクに付与するコメントの集合
            task_index: タスクの連番

        Returns:
            付与したコメントの数
        """
        logging_prefix = f"{task_index+1} 件目" if task_index is not None else ""

        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"{logging_prefix} : task_id='{task_id}' のタスクは存在しないので、スキップします。")
            return 0

        logger.debug(
            f"{logging_prefix} : task_id = {task['task_id']}, "
            f"status = {task['status']}, "
            f"phase = {task['phase']}, "
        )

        if not self._can_add_comment(
            task=task,
        ):
            return 0

        if not self.confirm_processing(f"task_id='{task_id}' のタスクに{self.comment_type_name}を付与しますか？"):
            return 0

        # コメントを付与するには作業中状態にする必要がある
        changed_task = self.change_to_working_status(self.project_id, task)
        added_comments_count = 0
        for input_data_id, comments in comments_for_task.items():
            if input_data_id not in task["input_data_id_list"]:
                logger.warning(
                    f"{logging_prefix} : task_id='{task_id}'のタスクに input_data_id='{input_data_id}'の入力データは存在しません。"
                )
                continue
            try:
                # コメントを付与する
                request_body = self._create_request_body(
                    task=changed_task, input_data_id=input_data_id, comments=comments
                )
                self.service.api.batch_update_comments(
                    self.project_id, task_id, input_data_id, request_body=request_body
                )
                added_comments_count += 1
                logger.debug(
                    f"{logging_prefix} : task_id={task_id}, input_data_id={input_data_id}: "
                    f"{len(comments)}件のコメントを付与しました。"
                )
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    f"{logging_prefix} : task_id={task_id}, input_data_id={input_data_id}: コメントの付与に失敗しました。",
                    exc_info=True,
                )
            finally:
                self.service.wrapper.change_task_status_to_break(self.project_id, task_id)
                # 担当者が変えている場合は、元に戻す
                if task["account_id"] != changed_task["account_id"]:
                    self.service.wrapper.change_task_operator(self.project_id, task_id, task["account_id"])
                    logger.debug(f"{task_id}: 担当者を元のユーザ( account_id={task['account_id']}）に戻しました。")

        return added_comments_count

    def add_comments_for_task_wrapper(
        self,
        tpl: Tuple[int, Tuple[str, AddedCommentsForTask]],
    ) -> int:
        task_index, (task_id, comments_for_task) = tpl
        return self.add_comments_for_task(task_id=task_id, comments_for_task=comments_for_task, task_index=task_index)

    def add_comments_for_task_list(
        self,
        comments_for_task_list: AddedComments,
        parallelism: Optional[int] = None,
    ) -> None:
        comments_count = sum(len(e) for e in comments_for_task_list.values())
        logger.info(
            f"{self.comment_type_name}を付与するタスク数: {len(comments_for_task_list)}, "
            f"{self.comment_type_name}を付与する入力データ数: {comments_count}"
        )

        if parallelism is not None:
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(
                    self.add_comments_for_task_wrapper, enumerate(comments_for_task_list.items())
                )
                added_comments_count = sum(e for e in result_bool_list)

        else:
            # 逐次処理
            added_comments_count = 0
            for task_index, (task_id, comments_for_task) in enumerate(comments_for_task_list.items()):
                try:
                    result = self.add_comments_for_task(
                        task_id=task_id,
                        comments_for_task=comments_for_task,
                        task_index=task_index,
                    )
                    added_comments_count += result
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"task_id={task_id}: コメントの付与に失敗しました。", exc_info=True)
                    continue

        logger.info(f"{added_comments_count} / {comments_count} 件の入力データに{self.comment_type_name}を付与しました。")


def convert_cli_comments(dict_comments: Dict[str, Any], *, comment_type: CommentType) -> AddedComments:
    """
    CLIから受け取ったコメント情報を、データクラスに変換する。
    """

    @dataclass
    class AddedInspectionComment(DataClassJsonMixin):
        """
        追加対象の検査コメント
        """

        comment: str
        """コメントの中身"""

        data: Dict[str, Any]
        """コメントを付与する位置や区間"""

        annotation_id: Optional[str] = None
        """コメントに紐付けるアノテーションID"""

        phrases: Optional[List[str]] = None
        """参照している定型指摘ID"""

    @dataclass
    class AddedOnholdComment(DataClassJsonMixin):
        """
        追加対象の保留コメント
        """

        comment: str
        """コメントの中身"""

        annotation_id: Optional[str] = None
        """コメントに紐付けるアノテーションID"""

    def convert_inspection_comment(comment: dict[str, Any]) -> AddedComment:
        tmp = AddedInspectionComment.from_dict(comment)
        return AddedComment(comment=tmp.comment, data=tmp.data, annotation_id=tmp.annotation_id, phrases=tmp.phrases)

    def convert_onhold_comment(comment: dict[str, Any]) -> AddedComment:
        tmp = AddedOnholdComment.from_dict(comment)
        return AddedComment(comment=tmp.comment, annotation_id=tmp.annotation_id, data=None, phrases=None)

    if comment_type == CommentType.INSPECTION:
        func_convert = convert_inspection_comment
    elif comment_type == CommentType.ONHOLD:
        func_convert = convert_onhold_comment
    else:
        raise RuntimeError(f"{comment_type=}が無効な値です。")

    return {
        task_id: {input_data_id: [func_convert(e) for e in comments]}
        for task_id, comments_for_task in dict_comments.items()
        for input_data_id, comments in comments_for_task.items()
    }
