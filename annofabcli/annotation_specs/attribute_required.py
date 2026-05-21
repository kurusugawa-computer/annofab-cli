from __future__ import annotations

import copy
import logging
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any

import annofabapi
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor, get_attribute_name_en

from annofabcli.annotation_specs.utils import get_target_attributes
from annofabcli.common.cli import CommandLineWithConfirm

logger = logging.getLogger(__name__)

REQUIRED_CONDITION = {"value": "", "_type": "NotEquals"}
"""required 制約を表す condition。"""


@dataclass(frozen=True)
class TargetAttribute:
    """
    required 制約の変更対象となる属性情報。

    Attributes:
        attribute_id: 属性ID
        attribute_name_en: 属性名(英語)
    """

    attribute_id: str
    attribute_name_en: str


def create_required_restriction(attribute_id: str) -> dict[str, Any]:
    """
    required 制約の restriction を生成する。

    Args:
        attribute_id: 対象属性ID

    Returns:
        required 制約の restriction
    """
    return {
        "additional_data_definition_id": attribute_id,
        "condition": copy.deepcopy(REQUIRED_CONDITION),
    }


def is_required_restriction(restriction: Mapping[str, Any], *, attribute_id: str | None = None) -> bool:
    """
    restriction が required 制約かどうかを判定する。

    Args:
        restriction: 判定対象の restriction
        attribute_id: 指定された場合は、対象属性IDも一致するか検証する

    Returns:
        required 制約なら True
    """
    if attribute_id is not None and restriction["additional_data_definition_id"] != attribute_id:
        return False
    return restriction["condition"] == REQUIRED_CONDITION


def create_comment_for_set_attribute_required(attribute_names: Collection[str]) -> str:
    """
    属性を必須にしたときのデフォルトコメントを生成する。

    Args:
        attribute_names: 必須にする属性名(英語)一覧

    Returns:
        アノテーション仕様変更コメント
    """
    return "以下の属性を必須にしました。\n" + "\n".join(attribute_names)


def create_comment_for_unset_attribute_required(attribute_names: Collection[str]) -> str:
    """
    属性の必須制約を外したときのデフォルトコメントを生成する。

    Args:
        attribute_names: 必須制約を外す属性名(英語)一覧

    Returns:
        アノテーション仕様変更コメント
    """
    return "以下の属性の必須制約を解除しました。\n" + "\n".join(attribute_names)


def create_confirm_message_for_attribute_required(action: str, target_attributes: Collection[TargetAttribute]) -> str:
    """
    属性の required 制約変更前の確認メッセージを生成する。

    Args:
        action: 実行内容
        target_attributes: 対象属性一覧

    Returns:
        確認メッセージ
    """
    lines = [f"以下の属性({len(target_attributes)}件)に対して、{action}。よろしいですか？"]
    lines.extend(f" * attribute_name_en='{attribute.attribute_name_en}', attribute_id='{attribute.attribute_id}'" for attribute in target_attributes)
    return "\n".join(lines)


def resolve_target_attributes_to_set_required(
    annotation_specs: dict[str, Any],
    *,
    attribute_ids: Collection[str] | None,
    attribute_name_ens: Collection[str] | None,
) -> list[TargetAttribute]:
    """
    required 制約を追加する対象属性を解決する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        attribute_ids: 対象属性ID一覧
        attribute_name_ens: 対象属性名(英語)一覧

    Returns:
        required 制約を追加する対象属性一覧
    """
    annotation_specs_accessor = AnnotationSpecsAccessor(annotation_specs)
    target_attributes = [
        TargetAttribute(
            attribute_id=attribute["additional_data_definition_id"],
            attribute_name_en=get_attribute_name_en(attribute),
        )
        for attribute in get_target_attributes(
            annotation_specs_accessor,
            attribute_ids=attribute_ids,
            attribute_name_ens=attribute_name_ens,
        )
    ]

    existing_required_attribute_ids = {restriction["additional_data_definition_id"] for restriction in annotation_specs["restrictions"] if is_required_restriction(restriction)}
    target_attributes_to_add = []
    for target_attribute in target_attributes:
        if target_attribute.attribute_id in existing_required_attribute_ids:
            logger.info(f"属性名(英語)='{target_attribute.attribute_name_en}', 属性ID='{target_attribute.attribute_id}' は既に必須です。")
            continue
        target_attributes_to_add.append(target_attribute)
    return target_attributes_to_add


def build_request_body_for_set_attribute_required(
    annotation_specs: dict[str, Any],
    *,
    target_attributes_to_add: Collection[TargetAttribute],
    comment: str | None,
) -> dict[str, Any]:
    """
    required 制約追加用の request body を生成する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        target_attributes_to_add: required 制約を追加する対象属性一覧
        comment: 変更コメント

    Returns:
        Annofab API に渡す request body
    """
    request_body = copy.deepcopy(annotation_specs)
    request_body["restrictions"].extend(create_required_restriction(attribute.attribute_id) for attribute in target_attributes_to_add)
    if comment is None:
        comment = create_comment_for_set_attribute_required([attribute.attribute_name_en for attribute in target_attributes_to_add])
    request_body["comment"] = comment
    request_body["last_updated_datetime"] = annotation_specs["updated_datetime"]
    return request_body


def resolve_target_attributes_to_unset_required(
    annotation_specs: dict[str, Any],
    *,
    attribute_ids: Collection[str] | None,
    attribute_name_ens: Collection[str] | None,
) -> list[TargetAttribute]:
    """
    required 制約を解除する対象属性を解決する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        attribute_ids: 対象属性ID一覧
        attribute_name_ens: 対象属性名(英語)一覧

    Returns:
        required 制約を解除する対象属性一覧
    """
    annotation_specs_accessor = AnnotationSpecsAccessor(annotation_specs)
    target_attributes = [
        TargetAttribute(
            attribute_id=attribute["additional_data_definition_id"],
            attribute_name_en=get_attribute_name_en(attribute),
        )
        for attribute in get_target_attributes(
            annotation_specs_accessor,
            attribute_ids=attribute_ids,
            attribute_name_ens=attribute_name_ens,
        )
    ]

    existing_required_attribute_ids = {restriction["additional_data_definition_id"] for restriction in annotation_specs["restrictions"] if is_required_restriction(restriction)}
    target_attributes_to_remove = []
    for target_attribute in target_attributes:
        if target_attribute.attribute_id not in existing_required_attribute_ids:
            logger.info(f"属性名(英語)='{target_attribute.attribute_name_en}', 属性ID='{target_attribute.attribute_id}' は必須ではありません。")
            continue
        target_attributes_to_remove.append(target_attribute)
    return target_attributes_to_remove


def build_request_body_for_unset_attribute_required(
    annotation_specs: dict[str, Any],
    *,
    target_attributes_to_remove: Collection[TargetAttribute],
    comment: str | None,
) -> dict[str, Any]:
    """
    required 制約解除用の request body を生成する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        target_attributes_to_remove: required 制約を解除する対象属性一覧
        comment: 変更コメント

    Returns:
        Annofab API に渡す request body
    """
    request_body = copy.deepcopy(annotation_specs)
    target_attribute_id_set = {attribute.attribute_id for attribute in target_attributes_to_remove}
    request_body["restrictions"] = [
        restriction for restriction in request_body["restrictions"] if not (restriction["additional_data_definition_id"] in target_attribute_id_set and is_required_restriction(restriction))
    ]
    if comment is None:
        comment = create_comment_for_unset_attribute_required([attribute.attribute_name_en for attribute in target_attributes_to_remove])
    request_body["comment"] = comment
    request_body["last_updated_datetime"] = annotation_specs["updated_datetime"]
    return request_body


class AttributeRequiredMain(CommandLineWithConfirm):
    """
    属性の required 制約を追加・削除する本体処理。
    """

    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        project_id: str,
        all_yes: bool,
    ) -> None:
        self.service = service
        self.project_id = project_id
        CommandLineWithConfirm.__init__(self, all_yes)

    def set_attribute_required(
        self,
        *,
        attribute_ids: Collection[str] | None,
        attribute_name_ens: Collection[str] | None,
        comment: str | None = None,
    ) -> bool:
        """
        指定した属性に required 制約を追加する。

        Args:
            attribute_ids: 対象属性ID一覧
            attribute_name_ens: 対象属性名(英語)一覧
            comment: 変更コメント

        Returns:
            更新を実行した場合はTrue、更新が不要または確認で中断した場合はFalse
        """
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        target_attributes_to_add = resolve_target_attributes_to_set_required(
            old_annotation_specs,
            attribute_ids=attribute_ids,
            attribute_name_ens=attribute_name_ens,
        )

        if len(target_attributes_to_add) == 0:
            logger.info("必須にする属性はないため、アノテーション仕様を変更しません。")
            return False

        confirm_message = create_confirm_message_for_attribute_required("必須制約を追加します", target_attributes_to_add)
        if not self.confirm_processing(confirm_message):
            return False

        request_body = build_request_body_for_set_attribute_required(
            old_annotation_specs,
            target_attributes_to_add=target_attributes_to_add,
            comment=comment,
        )
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"{len(target_attributes_to_add)} 件の属性に必須制約を設定しました。")
        return True

    def unset_attribute_required(
        self,
        *,
        attribute_ids: Collection[str] | None,
        attribute_name_ens: Collection[str] | None,
        comment: str | None = None,
    ) -> bool:
        """
        指定した属性の required 制約を削除する。

        Args:
            attribute_ids: 対象属性ID一覧
            attribute_name_ens: 対象属性名(英語)一覧
            comment: 変更コメント

        Returns:
            更新を実行した場合はTrue、更新が不要または確認で中断した場合はFalse
        """
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        target_attributes_to_remove = resolve_target_attributes_to_unset_required(
            old_annotation_specs,
            attribute_ids=attribute_ids,
            attribute_name_ens=attribute_name_ens,
        )

        if len(target_attributes_to_remove) == 0:
            logger.info("必須制約を解除する属性はないため、アノテーション仕様を変更しません。")
            return False

        confirm_message = create_confirm_message_for_attribute_required("属性の必須制約を解除します", target_attributes_to_remove)
        if not self.confirm_processing(confirm_message):
            return False

        request_body = build_request_body_for_unset_attribute_required(
            old_annotation_specs,
            target_attributes_to_remove=target_attributes_to_remove,
            comment=comment,
        )
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"{len(target_attributes_to_remove)} 件の属性の必須制約を解除しました。")
        return True
