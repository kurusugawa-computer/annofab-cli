from __future__ import annotations

from typing import Any, Literal, assert_never

from annofabapi.models import InputDataType
from annofabapi.util.page import create_3dpc_editor_url, create_image_editor_url, create_video_editor_url

AnnotationEditorType = Literal["image", "video", "3dpc"]
"""アノテーションエディタの種類。"""

ANNOTATION_EDITOR_TYPE_CHOICES: tuple[AnnotationEditorType, ...] = ("image", "video", "3dpc")
"""``--annotation_editor_type`` に指定できる値。"""


def get_annotation_editor_type_from_input_data_type(input_data_type: str) -> AnnotationEditorType:
    """
    入力データ種別に対応するアノテーションエディタの種類を返します。

    Args:
        input_data_type: プロジェクトの入力データ種別
    """
    if input_data_type == InputDataType.IMAGE.value:
        return "image"
    elif input_data_type == InputDataType.MOVIE.value:
        return "video"
    elif input_data_type == InputDataType.CUSTOM.value:
        return "3dpc"

    raise ValueError(f"入力データ種別 '{input_data_type}' はサポートされていません。")


def get_seek_seconds_for_video_editor(detail: dict[str, Any]) -> float | None:
    """
    動画エディタで再生位置を指定する秒数を取得します。

    Args:
        detail: アノテーションJSONのdetails配下の要素
    """
    if detail["data"]["_type"] != "Range":
        return None

    return detail["data"]["begin"] / 1000


def create_annotation_editor_url(simple_annotation: dict[str, Any], detail: dict[str, Any], annotation_editor_type: AnnotationEditorType | None = None) -> str:
    """
    アノテーションエディタ画面のURLを生成します。

    Args:
        simple_annotation: アノテーションJSONファイルの内容
        detail: アノテーションJSONのdetails配下の要素
        annotation_editor_type: アノテーションエディタの種類
    """
    if annotation_editor_type == "image":
        return create_image_editor_url(
            simple_annotation["project_id"],
            simple_annotation["task_id"],
            input_data_id=simple_annotation["input_data_id"],
            annotation_id=detail["annotation_id"],
        )
    elif annotation_editor_type == "video":
        return create_video_editor_url(
            simple_annotation["project_id"],
            simple_annotation["task_id"],
            annotation_id=detail["annotation_id"],
            seek_seconds=get_seek_seconds_for_video_editor(detail),
        )
    elif annotation_editor_type == "3dpc":
        return create_3dpc_editor_url(
            simple_annotation["project_id"],
            simple_annotation["task_id"],
            input_data_id=simple_annotation["input_data_id"],
            annotation_id=detail["annotation_id"],
        )
    elif annotation_editor_type is not None:
        assert_never(annotation_editor_type)

    annotation_type = detail["data"]["_type"]
    if annotation_type == "Range":
        return create_video_editor_url(
            simple_annotation["project_id"],
            simple_annotation["task_id"],
            annotation_id=detail["annotation_id"],
            seek_seconds=get_seek_seconds_for_video_editor(detail),
        )
    elif annotation_type == "Unknown":
        return create_3dpc_editor_url(
            simple_annotation["project_id"],
            simple_annotation["task_id"],
            input_data_id=simple_annotation["input_data_id"],
            annotation_id=detail["annotation_id"],
        )

    return create_image_editor_url(
        simple_annotation["project_id"],
        simple_annotation["task_id"],
        input_data_id=simple_annotation["input_data_id"],
        annotation_id=detail["annotation_id"],
    )
