import logging
from collections.abc import Collection
from enum import Enum
from typing import Any, Optional

from more_itertools import first_true

from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class OutputFormat(Enum):
    """
    表示するフォーマット ``--format`` で指定できる値

    Attributes:
        TEXT: 属性IDや種類を隠したシンプルなテキスト
        DETAILED_TEXT: 属性IDや属性種類などの詳細情報を表示したテキスト
    """

    TEXT = "text"
    DETAILED_TEXT = "detailed_text"


class AttributeRestrictionMessage:
    """
    アノテーション仕様の属性制約情報から、自然言語で書かれたメッセージを生成する

    Args:
        labels: アノテーション仕様のラベル情報
        additionals: アノテーション仕様の属性情報
        raise_if_not_found: 属性やラベルが見つからなかった場合に例外を発生させるかどうか
        format: 属性制約の表示フォーマット
            - `text`: 属性IDを隠したシンプルなテキスト
            - `detailed_text`: 属性IDなどの詳細情報を表示したテキスト

    """

    def __init__(
        self,
        labels: list[dict[str, Any]],
        additionals: list[dict[str, Any]],
        *,
        raise_if_not_found: bool = False,
        output_format: OutputFormat = OutputFormat.DETAILED_TEXT,  # pylint: disable=redefined-builtin
    ) -> None:
        self.attribute_dict = {e["additional_data_definition_id"]: e for e in additionals}
        self.label_dict = {e["label_id"]: e for e in labels}
        self.output_format = output_format
        self.raise_if_not_found = raise_if_not_found

    def get_labels_text(self, label_ids: Collection[str]) -> str:
        label_message_list = []
        for label_id in label_ids:
            label = self.label_dict.get(label_id)
            if label is not None:
                label_name = AnnofabApiFacade.get_label_name_en(label)
            else:
                logger.warning(f"ラベルIDが'{label_id}'であるラベルは存在しません。")
                if self.raise_if_not_found:
                    raise ValueError(f"ラベルIDが'{label_id}'であるラベルは存在しません。")
                label_name = ""

            label_message = f"'{label_name}'"
            if self.output_format == OutputFormat.DETAILED_TEXT:
                label_message = f"{label_message} (id='{label_id}')"
            label_message_list.append(label_message)

        return ", ".join(label_message_list)

    def get_object_for_equals_or_notequals(self, value: str, attribute: Optional[dict[str, Any]]) -> str:
        """制約条件が `Equals` or `NotEquals`のときの目的語を生成する。
        属性の種類がドロップダウンかセレクトボックスのときは、選択肢の名前を返す。

        Args:
            value (str): _description_
            attribute (Optional[dict[str,Any]]): _description_

        Returns:
            str: _description_
        """
        if attribute is not None and attribute["type"] in ["choice", "select"]:
            # ラジオボタンかドロップダウンのとき
            choices = attribute["choices"]
            choice = first_true(choices, pred=lambda e: e["choice_id"] == value)
            if choice is not None:
                choice_name = AnnofabApiFacade.get_choice_name_en(choice)
                tmp = f"'{value}'"
                if self.output_format == OutputFormat.DETAILED_TEXT:
                    tmp = f"{tmp} (name='{choice_name}')"
                return tmp

            else:
                message = (
                    f"選択肢IDが'{value}'である選択肢は存在しません。 :: "
                    f"属性名='{AnnofabApiFacade.get_additional_data_definition_name_en(attribute)}', "
                    f"属性ID='{attribute['additional_data_definition_id']}'"
                )
                logger.warning(message)
                if self.raise_if_not_found:
                    raise ValueError(message)
                return f"'{value}'"
        else:
            return f"'{value}'"

    def get_restriction_text(self, attribute_id: str, condition: dict[str, Any]) -> str:  # noqa: PLR0912
        """制約情報のテキストを返します。

        Args:
            attribute_id (str): 属性ID
            condition (dict[str, Any]): 制約条件

        Returns:
            str: 制約を表す文
        """
        str_type = condition["_type"]

        if str_type == "Imply":
            # 属性間の制約
            premise = condition["premise"]
            if_condition_text = self.get_restriction_text(premise["additional_data_definition_id"], premise["condition"])
            then_text = self.get_restriction_text(attribute_id, condition["condition"])
            return f"{then_text} IF {if_condition_text}"

        attribute = self.attribute_dict.get(attribute_id)
        if attribute is not None:
            subject = f"'{AnnofabApiFacade.get_additional_data_definition_name_en(attribute)}'"
            if self.output_format == OutputFormat.DETAILED_TEXT:
                subject = f"{subject} (id='{attribute_id}', type='{attribute['type']}')"
        else:
            logger.warning(f"属性IDが'{attribute_id}'である属性は存在しません。")
            if self.raise_if_not_found:
                raise ValueError(f"属性IDが'{attribute_id}'である属性は存在しません。")

            subject = "''"
            if self.output_format == OutputFormat.DETAILED_TEXT:
                subject = f"{subject} (id='{attribute_id}')"

        if str_type == "CanInput":
            verb = "CAN INPUT" if condition["enable"] else "CAN NOT INPUT"
            str_object = ""

        elif str_type == "HasLabel":
            verb = "HAS LABEL"
            str_object = self.get_labels_text(condition["labels"])

        elif str_type == "Equals":
            verb = "EQUALS"
            str_object = self.get_object_for_equals_or_notequals(condition["value"], attribute)

        elif str_type == "NotEquals":
            verb = "DOES NOT EQUAL"
            str_object = self.get_object_for_equals_or_notequals(condition["value"], attribute)

        elif str_type == "Matches":
            verb = "MATCHES"
            str_object = f"'{condition['value']}'"

        elif str_type == "NotMatches":
            verb = "DOES NOT MATCH"
            str_object = f"'{condition['value']}'"
        else:
            raise ValueError(f"condition._type='{str_type}'はサポートしていません。")

        tmp = f"{subject} {verb}"
        if str_object != "":
            tmp = f"{tmp} {str_object}"
        return tmp

    def get_attribute_from_name(self, attribute_name: str) -> Optional[dict[str, Any]]:
        tmp = [attribute for attribute in self.attribute_dict.values() if AnnofabApiFacade.get_additional_data_definition_name_en(attribute) == attribute_name]
        if len(tmp) == 1:
            return tmp[0]
        elif len(tmp) == 0:
            logger.warning(f"属性名(英語)が'{attribute_name}'の属性は存在しません。")
            return None
        else:
            logger.warning(f"属性名(英語)が'{attribute_name}'の属性は複数存在します。")
            return None

    def get_label_from_name(self, label_name: str) -> Optional[dict[str, Any]]:
        tmp = [label for label in self.label_dict.values() if AnnofabApiFacade.get_label_name_en(label) == label_name]
        if len(tmp) == 1:
            return tmp[0]
        elif len(tmp) == 0:
            logger.warning(f"ラベル名(英語)が'{label_name}'のラベルは存在しません。")
            return None
        else:
            logger.warning(f"ラベル名(英語)が'{label_name}'のラベルは複数存在します。")
            return None

    def get_target_attribute_ids(
        self,
        target_attribute_names: Optional[Collection[str]] = None,
        target_label_names: Optional[Collection[str]] = None,
    ) -> set[str]:
        result: set[str] = set()

        if target_attribute_names is not None:
            tmp_attribute_list = [self.get_attribute_from_name(attribute_name) for attribute_name in target_attribute_names]
            tmp_ids = {attribute["additional_data_definition_id"] for attribute in tmp_attribute_list if attribute is not None}
            result = result | tmp_ids

        if target_label_names is not None:
            tmp_label_list = [self.get_label_from_name(label_name) for label_name in target_label_names]
            tmp_ids_list = [label["additional_data_definitions"] for label in tmp_label_list if label is not None]
            for attribute_ids in tmp_ids_list:
                result = result | set(attribute_ids)

        return result

    def get_restriction_text_list(
        self,
        restrictions: list[dict[str, Any]],
        *,
        target_attribute_names: Optional[Collection[str]] = None,
        target_label_names: Optional[Collection[str]] = None,
    ) -> list[str]:
        """
        複数の属性制約から自然言語で記載されたメッセージのlistを返します。

        Args:
            restrictions: 属性制約のリスト
            target_attribute_names: 取得対象のラベル名（英語）のlist
            target_label_names: 取得対象の属性名（英語）のlist
        """
        if target_attribute_names is not None or target_label_names is not None:
            target_attribute_ids = self.get_target_attribute_ids(target_attribute_names=target_attribute_names, target_label_names=target_label_names)
            return [self.get_restriction_text(e["additional_data_definition_id"], e["condition"]) for e in restrictions if e["additional_data_definition_id"] in target_attribute_ids]
        else:
            return [self.get_restriction_text(e["additional_data_definition_id"], e["condition"]) for e in restrictions]
