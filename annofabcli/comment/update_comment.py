"""コメントの部分更新用の入力を読み込む。"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas
from annofabapi.models import CommentType
from pydantic import ConfigDict, field_validator

from annofabcli.comment.put_comment import AddedComment, AddedComments, _create_added_comments_for_task


class UpdatedCommentInput(AddedComment):
    """更新対象のIDと、明示的に指定された更新内容。"""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    """更新対象のタスクID。"""
    input_data_id: str
    """更新対象の入力データID。"""
    comment_id: str
    """更新対象のコメントID。"""

    @field_validator("comment", "data")
    @classmethod
    def reject_null(cls, value: str | dict[str, Any] | None) -> str | dict[str, Any]:
        """本文と座標への明示的なnull指定を拒否する。

        Args:
            value: 指定された本文または座標。

        Returns:
            null以外の値。
        """
        if value is None:
            raise ValueError("commentとdataにnullは指定できません。変更しない場合はキーを省略してください。")
        return value


def convert_updated_comment_list(comment_list: list[dict[str, Any]], *, comment_type: CommentType) -> AddedComments:
    """JSON形式の更新入力をタスク・入力データごとにまとめる。

    Args:
        comment_list: 更新対象のIDと更新する項目のリスト。
        comment_type: 更新するコメントの種類。

    Returns:
        タスクID・入力データIDごとの更新入力。
    """
    result: AddedComments = defaultdict(_create_added_comments_for_task)
    for record in comment_list:
        item = UpdatedCommentInput.model_validate(record)
        if comment_type == CommentType.ONHOLD and item.model_fields_set & {"data", "phrases"}:
            raise ValueError("保留コメントにはdataとphrasesは指定できません。")
        changes = item.model_dump(exclude_unset=True, exclude={"task_id", "input_data_id"})
        result[item.task_id][item.input_data_id].append(AddedComment.model_validate(changes))
    return result


def read_updated_comment_csv(csv_file: Path, *, comment_type: CommentType) -> AddedComments:
    """CSV形式の更新入力を読み込む。空欄は変更しない項目として扱う。

    Args:
        csv_file: 更新入力のCSVファイル。
        comment_type: 更新するコメントの種類。

    Returns:
        タスクID・入力データIDごとの更新入力。
    """
    df = pandas.read_csv(csv_file, dtype="string")
    required_columns = {"task_id", "input_data_id", "comment_id"}
    if not required_columns.issubset(df.columns):
        raise ValueError(f"必須カラムが不足しています: {required_columns - set(df.columns)}")
    records = []
    for row in df.to_dict(orient="records"):
        record = {key: value for key, value in row.items() if value is not None}
        for key in ("data", "phrases"):
            if key in record:
                record[key] = json.loads(record[key])
        records.append(record)
    return convert_updated_comment_list(records, comment_type=comment_type)
