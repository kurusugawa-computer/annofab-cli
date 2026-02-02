from __future__ import annotations

import logging
import multiprocessing
import uuid
from dataclasses import dataclass
from typing import Any

import annofabapi
import requests
from annofabapi.models import CommentType, TaskPhase, TaskStatus
from dataclasses_json import DataClassJsonMixin

from annofabcli.comment.utils import get_comment_type_name
from annofabcli.common.cli import CommandLineWithConfirm
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.type_util import assert_noreturn

logger = logging.getLogger(__name__)

SUPPORTED_ANNOTATION_TYPES_FOR_INSPECTION_DATA = frozenset(
    [
        "user_bounding_box",
        "bounding_box",
        "polygon",
        "polyline",
        "point",
        "range",
    ]
)
"""検査コメントの座標情報（InspectionData形式）への変換をサポートしているアノテーションタイプ"""


@dataclass
class AddedComment(DataClassJsonMixin):
    """
    追加対象のコメント。
    """

    comment: str
    """コメントの中身"""

    data: dict[str, Any] | None = None
    """コメントを付与する位置や区間"""

    annotation_id: str | None = None
    """コメントに紐付けるアノテーションID"""

    phrases: list[str] | None = None
    """参照している定型指摘ID"""

    comment_id: str | None = None
    """コメントID。省略時はUUIDv4が自動生成される。"""


AddedCommentsForTask = dict[str, list[AddedComment]]
"""
タスク配下の追加対象のコメント
keyはinput_data_id
"""

AddedComments = dict[str, AddedCommentsForTask]
"""
追加対象のコメント
keyはtask_id
"""


def convert_annotation_body_to_inspection_data(annotation_body: dict[str, Any], annotation_type: str) -> dict[str, Any]:
    """
    アノテーションのbody部分を、検査コメントの座標情報（`InspectionData`形式）に変換する。

    Args:
        annotation_body: Annotationの座標情報。AnnotationDetailContentOutputのdict形式
        annotation_type: アノテーションタイプ。`SUPPORTED_ANNOTATION_TYPES_FOR_INSPECTION_DATA`のいずれかを指定すること。

    Returns:
        検査コメントの座標情報（`InspectionData`形式）
    """
    if annotation_type == "user_bounding_box":
        # 3次元バウンディングボックスの場合はそのまま返す
        return annotation_body["data"]
    elif annotation_type == "bounding_box":
        # 中心点を計算
        left_top = annotation_body["data"]["left_top"]
        right_bottom = annotation_body["data"]["right_bottom"]
        center_x = (left_top["x"] + right_bottom["x"]) / 2
        center_y = (left_top["y"] + right_bottom["y"]) / 2
        return {"x": center_x, "y": center_y, "_type": "Point"}
    elif annotation_type in ["polygon", "polyline"]:
        # 先頭の点を取得
        points = annotation_body["data"]["points"]
        assert len(points) > 0
        first_point = points[0]
        return {"x": first_point["x"], "y": first_point["y"], "_type": "Point"}
    elif annotation_type == "point":
        # 点の形式に変換（pointキーから取り出す）
        point = annotation_body["data"]["point"]
        return {"x": point["x"], "y": point["y"], "_type": "Point"}
    elif annotation_type == "range":
        # 区間の開始位置をTime形式に変換
        begin = annotation_body["data"]["begin"]
        return {"start": begin, "end": begin, "_type": "Time"}
    else:
        supported_types = ", ".join(sorted(SUPPORTED_ANNOTATION_TYPES_FOR_INSPECTION_DATA))
        raise ValueError(f"Unsupported annotation_type: {annotation_type}. Supported types: {supported_types}")


class PutCommentMain(CommandLineWithConfirm):
    def __init__(self, service: annofabapi.Resource, project_id: str, comment_type: CommentType, all_yes: bool = False) -> None:  # noqa: FBT001, FBT002
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.project_id = project_id

        self.comment_type = comment_type
        self.comment_type_name = get_comment_type_name(comment_type)

        # アノテーション仕様を取得
        annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        self.dict_label_id_annotation_type = {label["label_id"]: label["annotation_type"] for label in annotation_specs["labels"]}

        CommandLineWithConfirm.__init__(self, all_yes)

    def _create_request_body(self, task: dict[str, Any], input_data_id: str, comments: list[AddedComment]) -> list[dict[str, Any]]:
        """batch_update_comments に渡すリクエストボディを作成する。"""
        task_id = task["task_id"]

        # annotation_idが指定されているがdataがNoneのコメントがあるか確認
        need_annotation_data = any(c.annotation_id is not None and c.data is None for c in comments)

        dict_annotation_id_label_id: dict[str, str] = {}
        dict_annotation_id_data: dict[str, dict[str, Any]] = {}

        if need_annotation_data:
            # アノテーション詳細を取得
            editor_annotation, _ = self.service.api.get_editor_annotation(self.project_id, task_id, input_data_id, query_params={"v": "2"})
            details = editor_annotation["details"]

            for detail in details:
                annotation_id = detail["annotation_id"]
                label_id = detail["label_id"]
                dict_annotation_id_label_id[annotation_id] = label_id

                # annotation_typeを取得
                annotation_type = self.dict_label_id_annotation_type.get(label_id)
                if annotation_type in SUPPORTED_ANNOTATION_TYPES_FOR_INSPECTION_DATA:
                    # サポート対象のannotation_typeの場合、dataを変換して保存
                    dict_annotation_id_data[annotation_id] = convert_annotation_body_to_inspection_data(detail["data"], annotation_type)
        else:
            # annotation_idからlabel_idを取得するためだけにAPIを呼ぶ
            editor_annotation, _ = self.service.api.get_editor_annotation(self.project_id, task_id, input_data_id, query_params={"v": "2"})
            details = editor_annotation["details"]
            dict_annotation_id_label_id = {e["annotation_id"]: e["label_id"] for e in details}

        def _convert(comment: AddedComment) -> dict[str, Any] | None:
            data = comment.data
            annotation_id = comment.annotation_id

            # dataがNoneでannotation_idが指定されている場合、dataを補完
            if data is None and annotation_id is not None:
                if annotation_id in dict_annotation_id_data:
                    # user_bounding_boxのdataを使用
                    data = dict_annotation_id_data[annotation_id]
                    logger.debug(f"task_id='{task_id}', input_data_id='{input_data_id}', annotation_id='{annotation_id}' :: dataを補完しました。")
                elif annotation_id in dict_annotation_id_label_id:
                    # annotation_idは存在するがサポート対象外
                    label_id = dict_annotation_id_label_id[annotation_id]
                    annotation_type = self.dict_label_id_annotation_type.get(label_id, "unknown")
                    supported_types_str = ", ".join(sorted(SUPPORTED_ANNOTATION_TYPES_FOR_INSPECTION_DATA))
                    logger.warning(
                        f"task_id='{task_id}', input_data_id='{input_data_id}', annotation_id='{annotation_id}' :: "
                        f"annotation_typeが'{annotation_type}'のため、dataの補完をスキップします。"
                        f"サポートしているのは: {supported_types_str} です。"
                    )
                    return None
                # annotation_idが存在しない場合は無視（警告なし）

            return {
                "comment_id": comment.comment_id if comment.comment_id is not None else str(uuid.uuid4()),
                "phase": task["phase"],
                "phase_stage": task["phase_stage"],
                "account_id": self.service.api.account_id,
                "comment_type": self.comment_type.value,
                "comment": comment.comment,
                "comment_node": {
                    "data": data,
                    "annotation_id": annotation_id,
                    "label_id": dict_annotation_id_label_id.get(annotation_id) if annotation_id is not None else None,
                    "status": "open",
                    "_type": "Root",
                },
                "phrases": comment.phrases,
                "_type": "Put",
            }

        converted_comments = [_convert(e) for e in comments]
        return [c for c in converted_comments if c is not None]

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
        try:
            if task["account_id"] != self.service.api.account_id:
                self.service.wrapper.change_task_operator(project_id, task_id, self.service.api.account_id)
                logger.debug(f"task_id='{task_id}' :: 担当者を自分自身に変更しました。")

            changed_task = self.service.wrapper.change_task_status_to_working(project_id, task_id)
            return changed_task  # noqa: TRY300

        except requests.HTTPError:
            logger.warning(f"task_id='{task_id}' :: 担当者の変更、または作業中状態への変更に失敗しました。", exc_info=True)
            raise

    def _can_add_comment(
        self,
        task: dict[str, Any],
    ) -> bool:
        task_id = task["task_id"]

        if self.comment_type == CommentType.INSPECTION:  # noqa: SIM102
            if task["phase"] == TaskPhase.ANNOTATION.value:
                logger.warning(f"task_id='{task_id}' :: フェーズが検査/受入でないため検査コメントを付与できません。 :: task_phase='{task['phase']}'")
                return False

        if task["status"] not in [TaskStatus.NOT_STARTED.value, TaskStatus.WORKING.value, TaskStatus.BREAK.value]:
            logger.warning(f"task_id='{task_id}' :: タスクの状態が未着手,作業中,休憩中 以外の状態なので、コメントを付与できません。 :: task_status='{task['status']}'")
            return False
        return True

    def add_comments_for_task(
        self,
        task_id: str,
        comments_for_task: AddedCommentsForTask,
        task_index: int | None = None,
    ) -> int:
        """
        タスクにコメントを付与します。

        Args:
            task_id: タスクID
            comments_for_task: 1つのタスクに付与するコメントの集合
            task_index: タスクの連番

        Returns:
            コメントを付与した入力データの個数
        """
        logging_prefix = f"{task_index + 1} 件目" if task_index is not None else ""

        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"{logging_prefix} :: task_id='{task_id}' のタスクは存在しないので、スキップします。")
            return 0

        logger.debug(f"{logging_prefix} : task_id='{task['task_id']}', status='{task['status']}', phase='{task['phase']}'")

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
                logger.warning(f"{logging_prefix} :: task_id='{task_id}'のタスクに input_data_id='{input_data_id}'の入力データは存在しません。")
                continue
            try:
                # コメントを付与する
                if len(comments) > 0:
                    request_body = self._create_request_body(task=changed_task, input_data_id=input_data_id, comments=comments)
                    self.service.api.batch_update_comments(self.project_id, task_id, input_data_id, request_body=request_body)
                    added_comments_count += 1
                    logger.debug(f"{logging_prefix} :: task_id='{task_id}', input_data_id='{input_data_id}' :: {len(comments)}件のコメントを付与しました。")
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    f"{logging_prefix} :: task_id='{task_id}', input_data_id='{input_data_id}' :: コメントの付与に失敗しました。",
                    exc_info=True,
                )

        self.service.wrapper.change_task_status_to_break(self.project_id, task_id)
        # 担当者が変えている場合は、元に戻す
        if task["account_id"] != changed_task["account_id"]:
            self.service.wrapper.change_task_operator(self.project_id, task_id, task["account_id"])
            logger.debug(f"{logging_prefix} :: task_id='{task_id}' :: 担当者を元のユーザ( account_id='{task['account_id']}'）に戻しました。")

        return added_comments_count

    def add_comments_for_task_wrapper(
        self,
        tpl: tuple[int, tuple[str, AddedCommentsForTask]],
    ) -> int:
        task_index, (task_id, comments_for_task) = tpl
        return self.add_comments_for_task(task_id=task_id, comments_for_task=comments_for_task, task_index=task_index)

    def add_comments_for_task_list(
        self,
        comments_for_task_list: AddedComments,
        parallelism: int | None = None,
    ) -> None:
        comments_count = sum(len(e) for e in comments_for_task_list.values())
        logger.info(f"{self.comment_type_name}を付与するタスク数: {len(comments_for_task_list)}, {self.comment_type_name}を付与する入力データ数: {comments_count}")

        if parallelism is not None:
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(self.add_comments_for_task_wrapper, enumerate(comments_for_task_list.items()))
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
                    logger.warning(f"task_id='{task_id}' :: コメントの付与に失敗しました。", exc_info=True)
                    continue

        logger.info(f"{added_comments_count} / {comments_count} 件の入力データに{self.comment_type_name}を付与しました。")


def convert_cli_comments(dict_comments: dict[str, Any], *, comment_type: CommentType) -> AddedComments:
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

        data: dict[str, Any] | None = None
        """コメントを付与する位置や区間"""

        annotation_id: str | None = None
        """コメントに紐付けるアノテーションID"""

        phrases: list[str] | None = None
        """参照している定型指摘ID"""

    @dataclass
    class AddedOnholdComment(DataClassJsonMixin):
        """
        追加対象の保留コメント
        """

        comment: str
        """コメントの中身"""

        annotation_id: str | None = None
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
        assert_noreturn(comment_type)

    result = {}
    for task_id, comments_for_task in dict_comments.items():
        sub_result = {input_data_id: [func_convert(e) for e in comments] for input_data_id, comments in comments_for_task.items() if len(comments) > 0}
        result.update({task_id: sub_result})
    return result
