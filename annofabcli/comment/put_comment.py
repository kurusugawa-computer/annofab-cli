from __future__ import annotations

import json
import logging
import multiprocessing
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import annofabapi
import pandas
import requests
from annofabapi.models import CommentType, TaskPhase, TaskStatus
from annofabapi.pydantic_models.input_data_type import InputDataType
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


def convert_annotation_body_to_inspection_data(  # noqa: PLR0911
    annotation_body: dict[str, Any],
    annotation_type: str,
    input_data_type: InputDataType,
) -> dict[str, Any]:
    """
    アノテーションのbody部分を、検査コメントの座標情報（`InspectionData`形式）に変換する。

    Args:
        annotation_body: Annotationの座標情報。AnnotationDetailContentOutputのdict形式
        annotation_type: アノテーションタイプ。`SUPPORTED_ANNOTATION_TYPES_FOR_INSPECTION_DATA`のいずれかを指定すること。
        input_data_type: プロジェクトの入力データタイプ。

    Returns:
        検査コメントの座標情報（`InspectionData`形式）
    """
    match input_data_type:
        case InputDataType.MOVIE:
            match annotation_type:
                case "range":
                    # 区間の開始位置をTime形式に変換
                    return {"start": annotation_body["data"]["begin"], "end": annotation_body["data"]["end"], "_type": "Time"}
                case _:
                    # "Classification"など、Time形式以外のアノテーションタイプ
                    return {"start": 0, "end": 100, "_type": "Time"}

        case InputDataType.CUSTOM:
            match annotation_type:
                case "user_bounding_box":
                    # 3次元バウンディングボックスの場合、data.dataの文字列をパースして返す
                    return {"data": annotation_body["data"]["data"], "_type": "Custom"}
                case _:
                    # セグメントなど
                    return {
                        "data": '{"kind": "CUBOID", "shape": {"dimensions": {"width": 1.0, "height": 1.0, "depth": 1.0}, "location": {"x": 0.0, "y": 0.0, "z": 0.0}, "rotation": {"x": 0.0, "y": 0.0, "z": 0.0}, "direction": {"front": {"x": 1.0, "y": 0.0, "z": 0.0}, "up": {"x": 0.0, "y": 0.0, "z": 1.0}}}, "version": "2"}',  # noqa: E501
                        "_type": "Custom",
                    }

        case InputDataType.IMAGE:
            match annotation_type:
                case "bounding_box":
                    # 中心点を計算
                    left_top = annotation_body["data"]["left_top"]
                    right_bottom = annotation_body["data"]["right_bottom"]
                    center_x = (left_top["x"] + right_bottom["x"]) / 2
                    center_y = (left_top["y"] + right_bottom["y"]) / 2
                    return {"x": center_x, "y": center_y, "_type": "Point"}
                case "polygon" | "polyline":
                    # 先頭の点を取得
                    points = annotation_body["data"]["points"]
                    assert len(points) > 0
                    first_point = points[0]
                    return {"x": first_point["x"], "y": first_point["y"], "_type": "Point"}
                case "point":
                    # 点の形式に変換（pointキーから取り出す）
                    point = annotation_body["data"]["point"]
                    return {"x": point["x"], "y": point["y"], "_type": "Point"}
                case "range":
                    # 区間の開始位置をTime形式に変換
                    return {"start": annotation_body["data"]["begin"], "end": annotation_body["data"]["end"], "_type": "Time"}
                case _:
                    # 塗りつぶしや分類など
                    return {"x": 0, "y": 0, "_type": "Point"}


class PutCommentMain(CommandLineWithConfirm):
    def __init__(self, service: annofabapi.Resource, project_id: str, comment_type: CommentType, all_yes: bool = False) -> None:  # noqa: FBT001, FBT002
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.project_id = project_id

        self.comment_type = comment_type
        self.comment_type_name = get_comment_type_name(comment_type)

        # プロジェクト情報を取得
        project, _ = self.service.api.get_project(self.project_id)
        self.input_data_type = InputDataType(project["input_data_type"])

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
                if label_id in self.dict_label_id_annotation_type:
                    # アノテーション仕様に存在しないラベルを使っているアノテーション（アノテーションを作成してから仕様を変更した場合）もあるので、判定する
                    annotation_type = self.dict_label_id_annotation_type[label_id]
                    dict_annotation_id_data[annotation_id] = convert_annotation_body_to_inspection_data(detail["body"], annotation_type, input_data_type=self.input_data_type)
        else:
            # annotation_idからlabel_idを取得するためだけにAPIを呼ぶ
            editor_annotation, _ = self.service.api.get_editor_annotation(self.project_id, task_id, input_data_id, query_params={"v": "2"})
            details = editor_annotation["details"]
            dict_annotation_id_label_id = {e["annotation_id"]: e["label_id"] for e in details}

        def _convert(comment: AddedComment) -> dict[str, Any] | None:
            data = comment.data
            annotation_id = comment.annotation_id

            # dataがNoneでannotation_idが指定されている場合、dataを補完
            if data is None:
                assert annotation_id is not None
                data = dict_annotation_id_data[annotation_id]

            assert data is not None
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

        if task["status"] not in [TaskStatus.NOT_STARTED.value, TaskStatus.BREAK.value]:
            logger.warning(f"task_id='{task_id}' :: タスクの状態が未着手,休憩中 以外の状態なので、コメントを付与できません。 :: task_status='{task['status']}'")
            return False
        return True

    def add_comments_for_task(
        self,
        task_id: str,
        comments_for_task: AddedCommentsForTask,
        task_index: int | None = None,
    ) -> tuple[int, int]:
        """
        タスクにコメントを付与します。

        Args:
            task_id: タスクID
            comments_for_task: 1つのタスクに付与するコメントの集合
            task_index: タスクの連番

        Returns:
            (コメントを付与した入力データの個数, 付与したコメントの個数)のタプル
        """
        logging_prefix = f"{task_index + 1} 件目" if task_index is not None else ""

        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"{logging_prefix} :: task_id='{task_id}' のタスクは存在しないので、スキップします。")
            return (0, 0)

        logger.debug(f"{logging_prefix} : task_id='{task['task_id']}', status='{task['status']}', phase='{task['phase']}'")

        if not self._can_add_comment(
            task=task,
        ):
            return (0, 0)

        if not self.confirm_processing(f"task_id='{task_id}' のタスクに{self.comment_type_name}を付与しますか？"):
            return (0, 0)

        # コメントを付与するには作業中状態にする必要がある
        changed_task = self.change_to_working_status(self.project_id, task)
        added_input_data_count = 0
        added_comment_count = 0
        for input_data_id, comments in comments_for_task.items():
            if input_data_id not in task["input_data_id_list"]:
                logger.warning(f"{logging_prefix} :: task_id='{task_id}'のタスクに input_data_id='{input_data_id}'の入力データは存在しません。")
                continue
            try:
                # コメントを付与する
                if len(comments) > 0:
                    request_body = self._create_request_body(task=changed_task, input_data_id=input_data_id, comments=comments)
                    self.service.api.batch_update_comments(self.project_id, task_id, input_data_id, request_body=request_body)
                    added_input_data_count += 1
                    added_comment_count += len(comments)
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

        return (added_input_data_count, added_comment_count)

    def add_comments_for_task_wrapper(
        self,
        tpl: tuple[int, tuple[str, AddedCommentsForTask]],
    ) -> tuple[int, int]:
        task_index, (task_id, comments_for_task) = tpl
        return self.add_comments_for_task(task_id=task_id, comments_for_task=comments_for_task, task_index=task_index)

    def add_comments_for_task_list(
        self,
        comments_for_task_list: AddedComments,
        parallelism: int | None = None,
    ) -> None:
        tasks_count = len(comments_for_task_list)
        input_data_count = sum(len(e) for e in comments_for_task_list.values())
        total_comment_count = sum(len(comments) for comments_for_task in comments_for_task_list.values() for comments in comments_for_task.values())
        logger.info(
            f"{self.comment_type_name}を付与するタスク数: {tasks_count}, {self.comment_type_name}を付与する入力データ数: {input_data_count}, {self.comment_type_name}の総数: {total_comment_count}"
        )

        if parallelism is not None:
            with multiprocessing.Pool(parallelism) as pool:
                result_list = pool.map(self.add_comments_for_task_wrapper, enumerate(comments_for_task_list.items()))
                added_input_data_count = sum(e[0] for e in result_list)
                added_comment_count = sum(e[1] for e in result_list)
                succeeded_tasks_count = sum(1 for e in result_list if e[0] > 0)

        else:
            # 逐次処理
            added_input_data_count = 0
            added_comment_count = 0
            succeeded_tasks_count = 0
            for task_index, (task_id, comments_for_task) in enumerate(comments_for_task_list.items()):
                try:
                    result_input_data, result_comment = self.add_comments_for_task(
                        task_id=task_id,
                        comments_for_task=comments_for_task,
                        task_index=task_index,
                    )
                    added_input_data_count += result_input_data
                    added_comment_count += result_comment
                    if result_input_data > 0:
                        succeeded_tasks_count += 1
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"task_id='{task_id}' :: コメントの付与に失敗しました。", exc_info=True)
                    continue

        logger.info(
            f"{succeeded_tasks_count} / {tasks_count} 件のタスク, "
            f"{added_input_data_count} / {input_data_count} 件の入力データ, "
            f"{added_comment_count} / {total_comment_count} 件の{self.comment_type_name}を付与しました。"
        )


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

        comment_id: str | None = None
        """コメントID。省略時はUUIDv4が自動生成される。"""

    @dataclass
    class AddedOnholdComment(DataClassJsonMixin):
        """
        追加対象の保留コメント
        """

        comment: str
        """コメントの中身"""

        annotation_id: str | None = None
        """コメントに紐付けるアノテーションID"""

        comment_id: str | None = None
        """コメントID。省略時はUUIDv4が自動生成される。"""

    def convert_inspection_comment(comment: dict[str, Any]) -> AddedComment:
        tmp = AddedInspectionComment.from_dict(comment)
        return AddedComment(comment=tmp.comment, data=tmp.data, annotation_id=tmp.annotation_id, phrases=tmp.phrases, comment_id=tmp.comment_id)

    def convert_onhold_comment(comment: dict[str, Any]) -> AddedComment:
        tmp = AddedOnholdComment.from_dict(comment)
        return AddedComment(comment=tmp.comment, annotation_id=tmp.annotation_id, data=None, phrases=None, comment_id=tmp.comment_id)

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


def read_comment_csv(csv_file: Path, comment_type: CommentType) -> dict[str, Any]:
    """
    CSVファイルからコメント情報を読み込み、convert_cli_comments()に渡せる形式に変換する。

    Args:
        csv_file: CSVファイルのパス
        comment_type: コメントの種類（検査コメントまたは保留コメント）

    Returns:
        dict[task_id, dict[input_data_id, list[comment_dict]]]形式の辞書

    Raises:
        ValueError: 必須カラムが不足している場合、またはJSON列のパースに失敗した場合
    """
    # すべての列をstr型として読み込む
    df = pandas.read_csv(str(csv_file), dtype=str)

    # 必須カラムチェック
    required_columns = ["task_id", "input_data_id", "comment"]
    missing_columns = set(required_columns) - set(df.columns)
    if len(missing_columns) > 0:
        raise ValueError(f"必須カラムが不足しています: {missing_columns}")

    # データ構築
    result: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for idx, row in enumerate(df.itertuples(index=False), start=2):  # CSVの行番号は2から（ヘッダーが1行目）
        task_id = row.task_id
        input_data_id = row.input_data_id

        # コメントdict作成
        comment_dict: dict[str, Any] = {"comment": row.comment}

        # data列（JSON文字列）のパース
        if hasattr(row, "data") and pandas.notna(row.data) and row.data.strip() != "":
            try:
                comment_dict["data"] = json.loads(row.data)
            except json.JSONDecodeError as e:
                logger.warning(f"CSVの{idx}行目: data列のJSON解析に失敗しました。 :: data='{row.data}' :: {e}", exc_info=True)
                raise ValueError(f"CSVの{idx}行目: data列のJSON解析に失敗しました。 :: data='{row.data}'") from e

        # annotation_id列
        if hasattr(row, "annotation_id") and pandas.notna(row.annotation_id) and row.annotation_id.strip() != "":
            comment_dict["annotation_id"] = row.annotation_id

        # phrases列（検査コメントのみ、JSON配列文字列）
        if comment_type == CommentType.INSPECTION and hasattr(row, "phrases") and pandas.notna(row.phrases) and row.phrases.strip() != "":
            try:
                parsed_phrases = json.loads(row.phrases)
                if isinstance(parsed_phrases, list):
                    comment_dict["phrases"] = parsed_phrases
                else:
                    logger.warning(f"CSVの{idx}行目: phrases列は配列である必要があります。 :: phrases='{row.phrases}'")
                    raise TypeError(f"CSVの{idx}行目: phrases列は配列である必要があります。 :: phrases='{row.phrases}'")
            except json.JSONDecodeError as e:
                logger.warning(f"CSVの{idx}行目: phrases列のJSON解析に失敗しました。 :: phrases='{row.phrases}' :: {e}", exc_info=True)
                raise ValueError(f"CSVの{idx}行目: phrases列のJSON解析に失敗しました。 :: phrases='{row.phrases}'") from e

        # comment_id列
        if hasattr(row, "comment_id") and pandas.notna(row.comment_id) and row.comment_id.strip() != "":
            comment_dict["comment_id"] = row.comment_id

        # 階層構造に追加
        if task_id not in result:
            result[task_id] = {}
        if input_data_id not in result[task_id]:
            result[task_id][input_data_id] = []
        result[task_id][input_data_id].append(comment_dict)

    return result
