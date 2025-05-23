from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Union

import more_itertools
from annofabapi.dataclass.annotation import AdditionalDataV1
from annofabapi.models import AdditionalDataDefinitionType
from annofabapi.util.annotation_specs import get_english_message
from dataclasses_json import DataClassJsonMixin

AttributeValue = Optional[Union[str, int, bool]]
"""属性値の型情報"""


def _get_additional_data_v1(additional_data: dict[str, Any], attribute_value: AttributeValue) -> AdditionalDataV1:
    """API用の`AdditionalDataV1`に相当する属性情報を取得する。

    Args:
        additional_data: アノテーション仕様の属性情報
        attribute_value: コマンドライン引数から渡された属性値。選択肢属性の場合は、選択肢の英語名になります。

    Raises:
        ValueError: 属性が排他選択の場合、属性値に指定された選択肢名の選択肢情報が見つからなかった

    Returns:
        WebAPI用の属性情報
    """

    def get_attribute_name(additional_data: dict[str, Any]) -> str:
        return get_english_message(additional_data["name"])

    additional_data_definition_id = additional_data["additional_data_definition_id"]
    result = {
        "additional_data_definition_id": additional_data_definition_id,
    }
    if attribute_value is None:
        return AdditionalDataV1.from_dict(result, infer_missing=True)

    additional_data_type: str = additional_data["type"]
    if additional_data_type == AdditionalDataDefinitionType.FLAG.value:
        result["flag"] = attribute_value

    elif additional_data_type == AdditionalDataDefinitionType.INTEGER.value:
        result["integer"] = attribute_value

    elif additional_data_type in [
        AdditionalDataDefinitionType.TEXT.value,
        AdditionalDataDefinitionType.COMMENT.value,
        AdditionalDataDefinitionType.TRACKING.value,
        AdditionalDataDefinitionType.LINK.value,
    ]:
        result["comment"] = attribute_value

    elif additional_data_type in [
        AdditionalDataDefinitionType.CHOICE.value,
        AdditionalDataDefinitionType.SELECT.value,
    ]:
        # 排他選択の場合、属性値に選択肢IDが入っているため、対象の選択肢を探す
        tmp = [e for e in additional_data["choices"] if get_english_message(e["name"]) == attribute_value]

        if len(tmp) == 0:
            raise ValueError(
                f"アノテーション仕様の'{get_attribute_name(additional_data)}'属性に、選択肢名(英語)が'{attribute_value}'である選択肢は存在しません。"
                f" :: additional_data_definition_id='{additional_data_definition_id}'"
            )
        if len(tmp) > 1:
            raise ValueError(
                f"アノテーション仕様の'{get_attribute_name(additional_data)}'属性に、選択肢名(英語)が'{attribute_value}'である選択肢が複数（{len(tmp)} 個）存在します。"
                f" :: additional_data_definition_id='{additional_data_definition_id}'"
            )

        result["choice"] = tmp[0]["choice_id"]

    return AdditionalDataV1.from_dict(result, infer_missing=True)


def _get_additional_data_v2(additional_data: dict[str, Any], attribute_value: AttributeValue) -> dict[str, Any]:
    """
    アノテーション仕様の属性情報と属性値から、API用の `AdditionalDataV2` に相当するdictを取得します。

    Args:
        additional_data: アノテーション仕様の属性情報
        attribute_value: コマンドライン引数から渡された属性値。選択肢属性の場合は、選択肢の英語名になります。

    Raises:
        ValueError: 属性が排他選択の場合、属性値に指定された選択肢名の選択肢情報が見つからなかった

    Returns:
        WebAPI用の属性情報
    """

    def get_choice_id_from_choice_name_en(choice_name_en: str) -> str:
        # 排他選択の場合、属性値に選択肢IDが入っているため、対象の選択肢を探す
        tmp = [e for e in additional_data["choices"] if get_english_message(e["name"]) == choice_name_en]

        if len(tmp) == 0:  # pylint: disable=no-else-raise
            raise ValueError(f"アノテーション仕様の'{get_attribute_name(additional_data)}'属性に、選択肢名(英語)が'{choice_name_en}'である選択肢は存在しません。")
        elif len(tmp) > 1:
            raise ValueError(f"アノテーション仕様の'{get_attribute_name(additional_data)}'属性に、選択肢名(英語)が'{choice_name_en}'である選択肢が複数（{len(tmp)} 個）存在します。")

        return tmp[0]["choice_id"]

    def get_attribute_name(additional_data: dict[str, Any]) -> str:
        return get_english_message(additional_data["name"])

    additional_data_definition_id = additional_data["additional_data_definition_id"]

    additional_data_type: str = additional_data["type"]

    if additional_data_type == AdditionalDataDefinitionType.FLAG.value:
        result_value = {"value": attribute_value, "_type": "Flag"}
    elif additional_data_type == AdditionalDataDefinitionType.INTEGER.value:
        result_value = {"value": attribute_value, "_type": "Integer"}
    elif additional_data_type == AdditionalDataDefinitionType.COMMENT.value:
        result_value = {"value": attribute_value, "_type": "Comment"}
    elif additional_data_type == AdditionalDataDefinitionType.TEXT.value:
        result_value = {"value": attribute_value, "_type": "Text"}
    elif additional_data_type == AdditionalDataDefinitionType.CHOICE.value:
        assert isinstance(attribute_value, str)
        result_value = {"choice_id": get_choice_id_from_choice_name_en(attribute_value), "_type": "Choice"}
    elif additional_data_type == AdditionalDataDefinitionType.SELECT.value:
        assert isinstance(attribute_value, str)
        result_value = {"choice_id": get_choice_id_from_choice_name_en(attribute_value), "_type": "Select"}
    elif additional_data_type == AdditionalDataDefinitionType.TRACKING.value:
        result_value = {"value": attribute_value, "_type": "Tracking"}
    elif additional_data_type == AdditionalDataDefinitionType.LINK.value:
        result_value = {"annotation_id": attribute_value, "_type": "Link"}

    else:
        raise RuntimeError(f"{additional_data_type=}がサポート対象外です。")

    return {"definition_id": additional_data_definition_id, "value": result_value}


def convert_attributes_from_cli_to_api(attributes: dict[str, AttributeValue], annotation_specs: dict[str, Any], *, label_id: Optional[str] = None) -> list[AdditionalDataV1]:
    """
    CLI用の属性をAPI用の属性に変換します。

    Args:
        attributes: CLI用の属性
        annotation_specs: アノテーション仕様(V2,V3版)
        label_id: 指定したlabel_idを持つラベル配下の属性から、属性情報を探します。Noneの場合は、すべての属性から属性情報を探します。

    Raises:
        ValueError: 指定された属性名や選択肢名の情報が見つからない、または複数見つかった

    Returns:
        API用の属性情報のList
    """

    def get_label_name(label_info: dict[str, Any]) -> str:
        return get_english_message(label_info["label_name"])

    if label_id is None:
        tmp_additionals = annotation_specs["additionals"]
    else:
        label_info = more_itertools.first_true(annotation_specs["labels"], pred=lambda e: e["label_id"] == label_id)
        if label_info is None:
            raise ValueError(f"アノテーション仕様に、label_id='{label_id}' であるラベルは存在しません。")

        tmp_additional_data_definition_ids = set(label_info["additional_data_definitions"])
        tmp_additionals = [e for e in annotation_specs["additionals"] if e["additional_data_definition_id"] in tmp_additional_data_definition_ids]

    attributes_for_webapi: list[AdditionalDataV1] = []
    for attribute_name, attribute_value in attributes.items():
        additional_data = more_itertools.first_true(
            tmp_additionals,
            pred=lambda e: get_english_message(e["name"]) == attribute_name,  # noqa: B023  # pylint: disable=cell-var-from-loop
        )
        tmp = [e for e in tmp_additionals if get_english_message(e["name"]) == attribute_name]
        if len(tmp) == 0:
            if label_info is None:
                error_message = f"アノテーション仕様に、属性名(英語)が'{attribute_name}'である属性は存在しません。"
            else:
                error_message = f"アノテーション仕様の'{get_label_name(label_info)}'ラベルに、属性名(英語)が'{attribute_name}'である属性は存在しません。 :: label_id='{label_id}'"
            raise ValueError(error_message)

        if len(tmp) > 1:
            if label_info is None:
                error_message = f"アノテーション仕様に、属性名(英語)が'{attribute_name}'である属性が複数存在します。"
            else:
                error_message = f"アノテーション仕様の'{get_label_name(label_info)}'ラベルに、属性名(英語)が'{attribute_name}'である属性が複数存在します。 :: label_id='{label_id}'"
            raise ValueError(error_message)
        additional_data = tmp[0]
        attributes_for_webapi.append(_get_additional_data_v1(additional_data, attribute_value))

    return attributes_for_webapi


def convert_attributes_from_cli_to_additional_data_list_v2(attributes: dict[str, AttributeValue], annotation_specs: dict[str, Any], *, label_id: Optional[str] = None) -> list[dict[str, Any]]:
    """
    CLI用の属性情報をAPI用の `AdditionalDataV2` に相当するdictに変換します。

    Args:
        attributes: CLI用の属性情報
        annotation_specs: アノテーション仕様
        label_id: 指定したlabel_idを持つラベル配下の属性から、属性情報を探します。Noneの場合は、すべての属性から属性情報を探します。

    Raises:
        ValueError: 指定された属性名や選択肢名の情報が見つからない、または複数見つかった

    Returns:
        API用の属性情報のList
    """

    def get_label_name(label_info: dict[str, Any]) -> str:
        return get_english_message(label_info["label_name"])

    if label_id is None:
        tmp_additionals = annotation_specs["additionals"]
    else:
        label_info = more_itertools.first_true(annotation_specs["labels"], pred=lambda e: e["label_id"] == label_id)
        if label_info is None:
            raise ValueError(f"アノテーション仕様に、label_id='{label_id}' であるラベルは存在しません。")

        tmp_additional_data_definition_ids = set(label_info["additional_data_definitions"])
        tmp_additionals = [e for e in annotation_specs["additionals"] if e["additional_data_definition_id"] in tmp_additional_data_definition_ids]

    result = []
    for attribute_name, attribute_value in attributes.items():
        additional_data = more_itertools.first_true(
            tmp_additionals,
            pred=lambda e: get_english_message(e["name"]) == attribute_name,  # noqa: B023  # pylint: disable=cell-var-from-loop
        )
        tmp = [e for e in tmp_additionals if get_english_message(e["name"]) == attribute_name]
        if len(tmp) == 0:  # pylint: disable=no-else-raise
            if label_info is None:
                error_message = f"アノテーション仕様に、属性名(英語)が'{attribute_name}'である属性は存在しません。"
            else:
                error_message = f"アノテーション仕様の'{get_label_name(label_info)}'ラベルに、属性名(英語)が'{attribute_name}'である属性は存在しません。 :: label_id='{label_id}'"
            raise ValueError(error_message)

        elif len(tmp) > 1:
            if label_info is None:
                error_message = f"アノテーション仕様に、属性名(英語)が'{attribute_name}'である属性が複数存在します。"
            else:
                error_message = f"アノテーション仕様の'{get_label_name(label_info)}'ラベルに、属性名(英語)が'{attribute_name}'である属性が複数存在します。 :: label_id='{label_id}'"
            raise ValueError(error_message)
        additional_data = tmp[0]
        result.append(_get_additional_data_v2(additional_data, attribute_value))

    return result


@dataclass
class AnnotationQueryForCLI(DataClassJsonMixin):
    """
    CLIでアノテーションを絞り込むためのクエリ。
    """

    label: Optional[str] = None
    """ラベル名（英語）"""

    attributes: Optional[dict[str, AttributeValue]] = None
    """
    keyが属性名(英語),valueが属性値のdict。
    属性が排他選択の場合、属性値は選択肢名(英語)。
    属性値がNoneのときは、「未指定」で絞り込む。
    """

    def __post_init__(self) -> None:
        if self.label is None and self.attributes is None:
            raise ValueError("'label'か'attributes'のいずれかは'not None'である必要があります。")

    def to_query_for_api(self, annotation_specs: dict[str, Any]) -> AnnotationQueryForAPI:
        """
        WebAPIのquery_params( https://annofab.com/docs/api/#section/AnnotationQuery )に渡すdictに変換する。

        Args:
            annotation_specs: アノテーション仕様（V2,V3版）

        Returns:
            dict[str,Any]: WebAPIのquery_paramsに渡すdict
        """
        assert self.label is not None or self.attributes is not None
        label_id: Optional[str] = None
        attributes_for_webapi: Optional[list[AdditionalDataV1]] = None

        if self.label is not None:
            tmp = [e for e in annotation_specs["labels"] if get_english_message(e["label_name"]) == self.label]

            if len(tmp) == 0:
                raise ValueError(f"アノテーション仕様に、ラベル名（英語）が'{self.label}'であるラベルは存在しません。")
            if len(tmp) > 1:
                raise ValueError(f"アノテーション仕様に、ラベル名（英語）が'{self.label}'であるラベルが複数（{len(tmp)} 個）存在します。")

            label_id = tmp[0]["label_id"]

            if self.attributes is None:
                return AnnotationQueryForAPI(label_id=label_id)

        if self.attributes is not None:
            # `self.attributes`に対応する属性情報を探す
            attributes_for_webapi = convert_attributes_from_cli_to_api(self.attributes, annotation_specs, label_id=label_id)

        return AnnotationQueryForAPI(label_id=label_id, attributes=attributes_for_webapi)


@dataclass
class AnnotationQueryForAPI(DataClassJsonMixin):
    """
    WebAPIでアノテーションを絞り込むためのクエリ。
    https://annofab.com/docs/api/#section/AnnotationQuery に対応しています。
    """

    label_id: Optional[str] = None
    """ラベルID"""

    attributes: Optional[list[AdditionalDataV1]] = None
    """属性IDと属性値のList"""

    def __post_init__(self) -> None:
        if self.label_id is None and self.attributes is None:
            raise ValueError("'label_id'か'attributes'のいずれかは'not None'である必要があります。")
