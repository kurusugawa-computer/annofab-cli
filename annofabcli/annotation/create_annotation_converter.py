from __future__ import annotations

import copy
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, assert_never

import ulid
from annofabapi.models import AdditionalDataDefinitionType, DefaultAnnotationType
from annofabapi.plugin import EditorPluginId
from annofabapi.pydantic_models.input_data_type import InputDataType
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor, get_english_message

from annofabcli.annotation.editor_props import validate_editor_props_for_cli


@dataclass(frozen=True)
class AnnotationDetailToCreate:
    """作成するアノテーションの詳細。"""

    label: str
    """アノテーション仕様のラベル名(英語)。"""
    data: dict[str, Any]
    """アノテーションのdata。"""
    attributes: dict[str, str | bool | int | None] | None
    """属性情報。"""
    annotation_id: str | None
    """アノテーションID。"""
    editor_props: dict[str, Any]
    """アノテーションエディタ用のプロパティ。"""


def _create_annotation_id(label: Mapping[str, Any], project: Mapping[str, Any]) -> str:
    if project["input_data_type"] == InputDataType.CUSTOM.value and project["configuration"]["plugin_id"] == EditorPluginId.THREE_DIMENSION.value:
        return str(ulid.new())
    if label["annotation_type"] == DefaultAnnotationType.CLASSIFICATION.value:
        return str(label["label_id"])
    return str(uuid.uuid4())


def _round_coordinates(data: dict[str, Any]) -> dict[str, Any]:
    if data["_type"] not in {"BoundingBox", "Points", "SinglePoint"}:
        return data
    result = copy.deepcopy(data)
    if result["_type"] == "BoundingBox":
        points = [result["left_top"], result["right_bottom"]]
    elif result["_type"] == "Points":
        points = result["points"]
    else:
        points = [result["point"]]
    for point in points:
        for key in ["x", "y"]:
            if isinstance(point[key], float):
                point[key] = round(point[key])
    return result


class CreateAnnotationConverter:
    """内包データのアノテーションを `put_annotation` API 用に変換する。"""

    def __init__(self, project: dict[str, Any], annotation_specs: dict[str, Any], *, default_editor_props: dict[str, Any]) -> None:
        self.project = project
        self.annotation_specs_accessor = AnnotationSpecsAccessor(annotation_specs)
        self.default_editor_props = validate_editor_props_for_cli(default_editor_props)

    def _convert_attribute_value(self, value: str | int | bool | None, attribute_type: AdditionalDataDefinitionType, choices: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:  # noqa: FBT001, PLR0911
        if value is None:
            return None
        if attribute_type == AdditionalDataDefinitionType.FLAG:
            if not isinstance(value, bool):
                raise ValueError("フラグ型の属性値はbool型である必要があります。")
            return {"_type": "Flag", "value": value}
        if attribute_type == AdditionalDataDefinitionType.INTEGER:
            if not isinstance(value, int):
                raise ValueError("整数型の属性値はint型である必要があります。")
            return {"_type": "Integer", "value": value}
        if attribute_type in {AdditionalDataDefinitionType.COMMENT, AdditionalDataDefinitionType.TEXT, AdditionalDataDefinitionType.TRACKING}:
            return {"_type": attribute_type.value.title(), "value": str(value)}
        if attribute_type == AdditionalDataDefinitionType.LINK:
            return None if value == "" else {"_type": "Link", "annotation_id": str(value)}
        if attribute_type in {AdditionalDataDefinitionType.CHOICE, AdditionalDataDefinitionType.SELECT}:
            if value == "":
                return None
            candidates = [choice for choice in choices if get_english_message(choice["name"]) == str(value)]
            if len(candidates) != 1:
                raise ValueError("選択肢名に一致する選択肢が存在しないか、複数存在します。")
            return {"_type": "Choice" if attribute_type == AdditionalDataDefinitionType.CHOICE else "Select", "choice_id": candidates[0]["choice_id"]}
        assert_never(attribute_type)

    def _convert_attributes(self, attributes: dict[str, str | bool | int | None], label: Any) -> list[dict[str, Any]]:  # noqa: ANN401
        result = []
        for name, value in attributes.items():
            try:
                definition: dict[str, Any] = dict(self.annotation_specs_accessor.get_attribute(attribute_name=name, label=label))
            except ValueError as e:
                raise ValueError(f"属性名(英語)が'{name}'である属性情報が存在しないか、複数存在します。") from e
            result.append(
                {"definition_id": definition["additional_data_definition_id"], "value": self._convert_attribute_value(value, AdditionalDataDefinitionType(definition["type"]), definition["choices"])}
            )
        return result

    def convert(self, detail: AnnotationDetailToCreate) -> dict[str, Any]:
        """アノテーション詳細を API リクエスト形式に変換する。"""
        label = dict(self.annotation_specs_accessor.get_label(label_name=detail.label))
        if label["annotation_type"] in {DefaultAnnotationType.SEGMENTATION.value, DefaultAnnotationType.SEGMENTATION_V2.value, "instance_segment", "semantic_segment"}:
            raise ValueError("外部ファイルが必要なアノテーションはこのコマンドではサポートしていません。")
        return {
            "_type": "Create",
            "label_id": label["label_id"],
            "annotation_id": detail.annotation_id or _create_annotation_id(label, self.project),
            "additional_data_list": self._convert_attributes(detail.attributes, label) if detail.attributes is not None else [],
            "editor_props": {**self.default_editor_props, **validate_editor_props_for_cli(detail.editor_props)},
            "body": {"_type": "Inner", "data": _round_coordinates(detail.data)},
        }
