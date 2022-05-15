from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import more_itertools
from annofabapi.dataclass.annotation import AdditionalData
from annofabapi.models import AdditionalDataDefinitionType
from annofabapi.utils import get_message_for_i18n
from dataclasses_json import DataClassJsonMixin

AttributeValue = Optional[Union[str, int, bool]]


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

    @classmethod
    def _to_attribute_for_api(cls, additional_data: dict[str, Any], attribute_value: AttributeValue) -> AdditionalData:
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
        result = {
            "additional_data_definition_id": additional_data_definition_id,
            "flag": None,
            "integer": None,
            "comment": None,
            "choice": None,
        }
        print(f"additional_data={additional_data}")
        if attribute_value is None:
            return AdditionalData(**result)

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

        elif additional_data_type in [AdditionalDataDefinitionType.CHOICE.value, AdditionalDataDefinitionType.SELECT.value]:
            # 排他選択の場合、属性値に選択肢IDが入っているため、対象の選択肢を探す
            choice_info = more_itertools.first_true(
                additional_data["choices"], pred=lambda e: get_message_for_i18n(e["name"]) == attribute_value
            )
            if choice_info is None:
                attribute_name = get_message_for_i18n(additional_data["name"])
                raise ValueError(
                    f"アノテーション仕様の'{attribute_name}'属性に、選択肢名(英語)が'{attribute_value}'である選択肢は存在しません。"
                    f" :: additional_data_definition_id='{additional_data_definition_id}'"
                )

            result["choice"] = choice_info["choice_id"]

        return AdditionalData(**result)

    def to_query_for_api(self, annotation_specs: dict[str, Any]) -> AnnotationQueryForAPI:
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
            return AnnotationQueryForAPI(label_id=label_id)

        # ラベル配下の属性情報から、`self.attributes`に対応する属性情報を探す
        tmp_additional_data_definition_ids = set(label_info["additional_data_definitions"])
        tmp_additionals = [
            e
            for e in annotation_specs["additionals"]
            if e["additional_data_definition_id"] in tmp_additional_data_definition_ids
        ]

        attributes_for_webapi: list[AdditionalData] = []
        for attribute_name, attribute_value in self.attributes.items():
            additional_data = more_itertools.first_true(
                tmp_additionals,
                pred=lambda e: get_message_for_i18n(e["name"]) == attribute_name,  # pylint: disable=cell-var-from-loop
            )
            if additional_data is None:
                raise ValueError(
                    f"アノテーション仕様の'{self.label}'ラベルに、属性名(英語)が'{attribute_name}'である属性は存在しません。 :: label_id='{label_id}'"
                )

            attributes_for_webapi.append(self._to_attribute_for_api(additional_data, attribute_value))

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
