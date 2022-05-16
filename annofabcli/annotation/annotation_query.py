from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import more_itertools
from annofabapi.dataclass.annotation import AdditionalData
from annofabapi.models import AdditionalDataDefinitionType
from annofabapi.utils import get_message_for_i18n
from dataclasses_json import DataClassJsonMixin

AttributeValue = Optional[Union[str, int, bool]]


def _get_attribute_to_api(additional_data: dict[str, Any], attribute_value: AttributeValue) -> AdditionalData:
    """API用の属性情報を取得する。

    Args:
        additional_data: アノテーション仕様の属性情報
        attribute_value: 属性値

    Raises:
        ValueError: 属性が排他選択の場合、属性値に指定された選択肢名の選択肢情報が見つからなかった

    Returns:
        WebAPI用の属性情報
    """

    def get_attribute_name(additional_data: dict[str, Any]) -> str:
        return get_message_for_i18n(additional_data["name"])

    additional_data_definition_id = additional_data["additional_data_definition_id"]
    result = {
        "additional_data_definition_id": additional_data_definition_id,
    }
    if attribute_value is None:
        return AdditionalData.from_dict(result, infer_missing=True)

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
        choice_info = more_itertools.first_true(
            additional_data["choices"], pred=lambda e: get_message_for_i18n(e["name"]) == attribute_value
        )
        tmp = [e for e in additional_data["choices"] if get_message_for_i18n(e["name"]) == attribute_value]

        if len(tmp) == 0:
            raise ValueError(
                f"アノテーション仕様の'{get_attribute_name(additional_data)}'属性に、選択肢名(英語)が'{attribute_value}'である選択肢は存在しません。"
                f" :: additional_data_definition_id='{additional_data_definition_id}'"
            )
        if len(tmp) > 1:
            raise ValueError(
                f"アノテーション仕様の'{get_attribute_name(additional_data)}'属性に、選択肢名(英語)が'{attribute_value}'である選択肢が複数存在します。"
                f" :: additional_data_definition_id='{additional_data_definition_id}'"
            )

        choice_info = tmp[0]
        result["choice"] = choice_info["choice_id"]

    return AdditionalData.from_dict(result, infer_missing=True)


def convert_attributes_from_cli_to_api(
    attributes: dict[str, AttributeValue], annotation_specs: dict[str, Any], label_id: Optional[str] = None
) -> list[AdditionalData]:
    """
    CLI用の属性をAPI用の属性に変換します。

    Args:
        attributes: CLI用の属性
        annotation_specs: アノテーション仕様
        label_id: 指定したlabel_idを持つラベル配下の属性から、属性情報を探します。Noneの場合は、すべての属性から属性情報を探します。

    Raises:
        ValueError: 指定された属性名や選択肢名の情報が見つからない、または複数見つかった

    Returns:
        API用の属性情報のList
    """

    def get_label_name(label_info: dict[str, Any]) -> str:
        return get_message_for_i18n(label_info["label_name"])

    if label_id is None:
        tmp_additionals = annotation_specs["additionals"]
    else:
        label_info = more_itertools.first_true(annotation_specs["labels"], pred=lambda e: e["label_id"] == label_id)
        if label_info is None:
            raise ValueError(f"アノテーション仕様に、label_id='{label_id}' であるラベルは存在しません。")

        tmp_additional_data_definition_ids = set(label_info["additional_data_definitions"])
        tmp_additionals = [
            e
            for e in annotation_specs["additionals"]
            if e["additional_data_definition_id"] in tmp_additional_data_definition_ids
        ]

    attributes_for_webapi: list[AdditionalData] = []
    for attribute_name, attribute_value in attributes.items():
        additional_data = more_itertools.first_true(
            tmp_additionals,
            pred=lambda e: get_message_for_i18n(e["name"]) == attribute_name,  # pylint: disable=cell-var-from-loop
        )
        tmp = [e for e in tmp_additionals if get_message_for_i18n(e["name"]) == attribute_name]
        if len(tmp) == 0:
            if label_info is None:
                error_message = f"アノテーション仕様に、属性名(英語)が'{attribute_name}'である属性は存在しません。"
            else:
                error_message = (
                    f"アノテーション仕様の'{get_label_name(label_info)}'ラベルに、"
                    f"属性名(英語)が'{attribute_name}'である属性は存在しません。 :: label_id='{label_id}'"
                )
            raise ValueError(error_message)

        if len(tmp) > 1:
            if label_info is None:
                error_message = f"アノテーション仕様に、属性名(英語)が'{attribute_name}'である属性が複数存在します。"
            else:
                error_message = (
                    f"アノテーション仕様の'{get_label_name(label_info)}'ラベルに、"
                    f"属性名(英語)が'{attribute_name}'である属性が複数存在します。 :: label_id='{label_id}'"
                )
            raise ValueError(error_message)
        additional_data = tmp[0]
        attributes_for_webapi.append(_get_attribute_to_api(additional_data, attribute_value))

    return attributes_for_webapi


@dataclass
class AnnotationQueryForCLI(DataClassJsonMixin):
    """
    CLIでアノテーションを絞り込むためのクエリ。
    """

    label: str
    """ラベル名（英語）"""

    # attributes: Optional[List[AdditionalData]] = None
    attributes: Optional[Dict[str, AttributeValue]] = None
    """
    keyが属性名(英語),valueが属性値のdict。
    属性が排他選択の場合、属性値は選択肢名(英語)。
    属性値がNoneのときは、「未指定」で絞り込む。
    """

    def to_query_for_api(self, annotation_specs: dict[str, Any]) -> AnnotationQueryForAPI:
        """
        WebAPIのquery_params( https://annofab.com/docs/api/#section/AnnotationQuery )に渡すdictに変換する。

        Args:
            annotation_specs: アノテーション仕様（V2版）

        Returns:
            dict[str,Any]: WebAPIのquery_paramsに渡すdict
        """
        tmp = [e for e in annotation_specs["labels"] if get_message_for_i18n(e["label_name"]) == self.label]

        if len(tmp) == 0:
            raise ValueError(f"アノテーション仕様に、ラベル名（英語）が'{self.label}'であるラベルは存在しません。")
        if len(tmp) > 1:
            raise ValueError(f"アノテーション仕様に、ラベル名（英語）が'{self.label}'であるラベルが複数存在します。")

        label_info = tmp[0]
        label_id = label_info["label_id"]
        if self.attributes is None:
            return AnnotationQueryForAPI(label_id=label_id)

        # ラベル配下の属性情報から、`self.attributes`に対応する属性情報を探す
        attributes_for_webapi = convert_attributes_from_cli_to_api(self.attributes, annotation_specs, label_id=label_id)
        return AnnotationQueryForAPI(label_id=label_id, attributes=attributes_for_webapi)


@dataclass
class AnnotationQueryForAPI(DataClassJsonMixin):
    """
    WebAPIでアノテーションを絞り込むためのクエリ。
    """

    label_id: str
    """ラベルID"""

    attributes: Optional[List[AdditionalData]] = None
    """属性IDと属性値のList"""
