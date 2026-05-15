import logging
from collections.abc import Collection
from typing import Any

from annofabapi.util.annotation_specs import get_attribute_name_en, get_choice_name_en, get_label_name_en
from more_itertools import first_true

logger = logging.getLogger(__name__)


class AttributeRestrictionMessage:
    """
    アノテーション仕様の属性制約情報から、自然言語で書かれたメッセージを生成する

    Args:
        labels: アノテーション仕様のラベル情報
        additionals: アノテーション仕様の属性情報
        raise_if_not_found: 属性やラベルが見つからなかった場合に例外を発生させるかどうか

    """

    def __init__(
        self,
        labels: list[dict[str, Any]],
        additionals: list[dict[str, Any]],
        *,
        raise_if_not_found: bool = False,
    ) -> None:
        self.attribute_dict = {e["additional_data_definition_id"]: e for e in additionals}
        self.label_dict = {e["label_id"]: e for e in labels}
        self.raise_if_not_found = raise_if_not_found

    def get_labels_text(self, label_ids: Collection[str]) -> str:
        label_message_list = []
        for label_id in label_ids:
            label = self.label_dict.get(label_id)
            if label is not None:
                label_name = get_label_name_en(label)
            else:
                logger.warning(f"ラベルIDが'{label_id}'であるラベルは存在しません。")
                if self.raise_if_not_found:
                    raise ValueError(f"ラベルIDが'{label_id}'であるラベルは存在しません。")
                label_name = ""

            label_message_list.append(f"'{label_name}'")

        return ", ".join(label_message_list)

    def get_object_for_equals_or_notequals(self, value: str, attribute: dict[str, Any] | None) -> str:
        """制約条件が `Equals` or `NotEquals`のときの目的語を生成する。
        属性の種類がドロップダウンかセレクトボックスのときは、選択肢の名前を返す。

        Args:
            value: 制約条件の値
            attribute: 属性情報

        Returns:
            valueが'foo'の場合：
            -  属性の種類が排他選択でない場合： `'foo'` （valueを返す）
            -  属性の種類が排他選択である場合： `'FOO'` （選択肢の名前を返す）

        """
        if attribute is not None and attribute["type"] in ["choice", "select"]:
            # ラジオボタンかドロップダウンのとき
            choices = attribute["choices"]
            choice = first_true(choices, pred=lambda e: e["choice_id"] == value)
            if value == "" or choice is not None:
                # `value == ""`を判定条件に加える理由：「排他選択属性が空である/空でない」という制約の場合、`value`は空文字列になるため。
                choice_name = get_choice_name_en(choice) if choice is not None else ""
                return f"'{choice_name}'"

            else:
                message = f"選択肢IDが'{value}'である選択肢は存在しません。 :: 属性名='{get_attribute_name_en(attribute)}', 属性ID='{attribute['additional_data_definition_id']}'"
                logger.warning(message)
                if self.raise_if_not_found:
                    raise ValueError(message)
                return f"'{value}'"
        else:
            return f"'{value}'"

    def get_restriction_text(self, attribute_id: str, condition: dict[str, Any]) -> str:
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
            subject = f"'{get_attribute_name_en(attribute)}'"
        else:
            logger.warning(f"属性IDが'{attribute_id}'である属性は存在しません。")
            if self.raise_if_not_found:
                raise ValueError(f"属性IDが'{attribute_id}'である属性は存在しません。")

            subject = "''"

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

    def get_attribute_from_name(self, attribute_name: str) -> dict[str, Any] | None:
        tmp = [attribute for attribute in self.attribute_dict.values() if get_attribute_name_en(attribute) == attribute_name]
        if len(tmp) == 1:
            return tmp[0]
        elif len(tmp) == 0:
            logger.warning(f"属性名(英語)が'{attribute_name}'の属性は存在しません。")
            return None
        else:
            logger.warning(f"属性名(英語)が'{attribute_name}'の属性は複数存在します。")
            return None

    def get_label_from_name(self, label_name: str) -> dict[str, Any] | None:
        tmp = [label for label in self.label_dict.values() if get_label_name_en(label) == label_name]
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
        target_attribute_names: Collection[str] | None = None,
        target_label_names: Collection[str] | None = None,
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
        target_attribute_names: Collection[str] | None = None,
        target_label_names: Collection[str] | None = None,
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

    def get_target_restrictions(
        self,
        restrictions: list[dict[str, Any]],
        *,
        target_attribute_names: Collection[str] | None = None,
        target_label_names: Collection[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        指定条件に一致する属性制約を返す。

        Args:
            restrictions: 属性制約のリスト
            target_attribute_names: 取得対象の属性名（英語）のlist
            target_label_names: 取得対象のラベル名（英語）のlist

        Returns:
            絞り込み後の属性制約一覧
        """
        if target_attribute_names is None and target_label_names is None:
            return restrictions

        target_attribute_ids = self.get_target_attribute_ids(target_attribute_names=target_attribute_names, target_label_names=target_label_names)
        return [restriction for restriction in restrictions if restriction["additional_data_definition_id"] in target_attribute_ids]
