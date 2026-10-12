import logging
import uuid
from collections.abc import Mapping
from typing import Any

import ulid
from annofabapi.models import DefaultAnnotationType
from annofabapi.plugin import EditorPluginId
from annofabapi.pydantic_models.input_data_type import InputDataType

logger = logging.getLogger(__name__)


def resolve_annotation_id(label: Mapping[str, Any], project: Mapping[str, Any], annotation_id: str | None) -> str:
    """ラベルとプロジェクトの制約に従ってアノテーションIDを決定する。

    Args:
        label: アノテーション仕様のラベル情報。
        project: プロジェクト情報。
        annotation_id: 入力で指定されたアノテーションID。

    Returns:
        APIリクエストで使用するアノテーションID。
    """
    is_3dpc = project["input_data_type"] == InputDataType.CUSTOM.value and project["configuration"]["plugin_id"] == EditorPluginId.THREE_DIMENSION.value
    if project["input_data_type"] in {InputDataType.IMAGE.value, InputDataType.MOVIE.value} and label["annotation_type"] == DefaultAnnotationType.CLASSIFICATION.value:
        label_id = str(label["label_id"])
        if annotation_id is not None and annotation_id != label_id:
            logger.warning(f"全体アノテーションのannotation_idにはlabel_id='{label_id}'を使用します。指定されたannotation_id='{annotation_id}'は無視します。")
        return label_id
    if annotation_id:
        return annotation_id
    if is_3dpc:
        return str(ulid.new())
    if label["annotation_type"] == DefaultAnnotationType.CLASSIFICATION.value:
        return str(label["label_id"])
    return str(uuid.uuid4())
