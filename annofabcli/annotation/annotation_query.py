from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

import more_itertools
from annofabapi.models import AdditionalDataDefinitionType
from annofabapi.utils import get_message_for_i18n
from dataclasses_json import DataClassJsonMixin

AttributeValue = Union[str, int, bool]


@dataclass
class AnnotationQuery(DataClassJsonMixin):
    """
    アノテーションを絞り込むためのクエリ
    """

    label: str
    """ラベル名（英語）"""

    # attributes: Optional[List[AdditionalData]] = None
    attributes: Optional[Dict[str, AttributeValue]] = None
    """
    keyが属性名(英語),valueが属性値のdict
    属性が排他選択の場合、属性値は選択肢名(英語)
    """

    def to_yyy(self, additional_data: dict[str, Any], attribute_value: AttributeValue) -> dict[str, Any]:
        """アノテーション仕様の属性情報と属性値から、WebAPIに渡すクエリの属性部分を返す。

        Args:
            additional_data: アノテーション仕様の属性情報
            attribute_value: 属性値

        Raises:
            ValueError: 属性が排他選択の場合、属性値に指定された選択肢名の選択肢情報が見つからなかった

        Returns:
            WebAPIに渡すクエリの属性部分
        """
        additional_data_definition_id = additional_data["additional_data_definition_id"]
        result = {"additional_data_definition_id": additional_data_definition_id}
        additional_data_type = additional_data["type"]
        if additional_data_type == AdditionalDataDefinitionType.FLAG.value:
            result["flag"] = attribute_value

        elif additional_data_type == AdditionalDataDefinitionType.INTEGER.value:
            result["integer"] = attribute_value

        elif additional_data_type in [
            AdditionalDataDefinitionType.TEXT,
            AdditionalDataDefinitionType.COMMENT,
            AdditionalDataDefinitionType.TRACKING,
            AdditionalDataDefinitionType.LINK,
        ]:
            result["comment"] = attribute_value

        elif additional_data_type in [AdditionalDataDefinitionType.CHOICE, AdditionalDataDefinitionType.SELECT]:
            # 排他選択の場合、属性値に選択肢IDが入っているため、対象の選択肢を探す
            choice_info = more_itertools.first_true(
                additional_data["choices"], pred=lambda e: get_message_for_i18n(e["name"]) == attribute_value
            )
            if choice_info is None:
                attribute_name = get_message_for_i18n(additional_data["name"])
                raise ValueError(
                    f"アノテーション仕様の'{attribute_name}'属性に、選択肢名(英語)が'{attribute_value}'である選択肢は存在しません。 :: additional_data_definition_id='{additional_data_definition_id}'"
                )

            result["choice"] = choice_info["choice_id"]

        return result

    def to_xxx(self, annotation_specs: dict[str, Any]) -> dict[str, Any]:
        """
        WebAPIのquery_params( https://annofab.com/docs/api/#section/AnnotationQuery )に渡すdictに変換する。

        Args:
            annotation_specs: アノテーション仕様（V2版）

        Returns:
            dict[str,Any]: WebAPIのquery_paramsに渡すdict
        """
        label_info = more_itertools.first_true(
            annotation_specs["labels"], pred=lambda e: get_message_for_i18n(e["label_name"]) == self.label
        )
        if label_info is None:
            raise ValueError(f"アノテーション仕様に、ラベル名（英語）が'{self.label}'であるラベルは存在しません。")

        label_id = label_info["label_id"]
        if self.attributes is None:
            return {"label_id": label_id}

        # ラベル配下の属性情報から、`self.attributes`に対応する属性情報を探す
        tmp_additional_data_definition_ids = set(label_info["additional_data_definitions"])
        tmp_additionals = [
            e
            for e in annotation_specs["additionals"]
            if e["additional_data_definition_id"] in tmp_additional_data_definition_ids
        ]

        attributes_for_webapi = []
        for attribute_name, attribute_value in self.attributes.items():
            additional_data = more_itertools.first_true(
                tmp_additionals, pred=lambda e: get_message_for_i18n(e["name"]) == attribute_name
            )
            if additional_data is None:
                raise ValueError(
                    f"アノテーション仕様の'{self.label}'ラベルに、属性名(英語)が'{attribute_name}'である属性は存在しません。 :: label_id='{label_id}'"
                )

            attributes_for_webapi.append(self.to_yyy(additional_data, attribute_value))

        return {"label_id": label_id, "attributes": attributes_for_webapi}
