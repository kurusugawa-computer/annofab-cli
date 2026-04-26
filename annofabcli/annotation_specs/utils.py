from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from annofabapi.util.annotation_specs import AnnotationSpecsAccessor, get_english_message


def get_label_name_en(label: dict[str, Any]) -> str:
    """
    ラベル情報から英語名を取得する。

    Args:
        label: ラベル情報

    Returns:
        ラベルの英語名
    """
    return get_english_message(label["label_name"])


def get_attribute_name_en(attribute: dict[str, Any]) -> str:
    """
    属性情報から英語名を取得する。

    Args:
        attribute: 属性情報

    Returns:
        属性の英語名
    """
    return get_english_message(attribute["name"])




def create_name(message_en: str, message_ja: str | None = None) -> dict[str, Any]:
    """
    Annofabの多言語メッセージ形式を生成する。

    Args:
        message_en: 英語メッセージ
        message_ja: 日本語メッセージ。未指定の場合は英語メッセージと同じ内容になる。

    Returns:
        Annofab APIが要求する ``name`` オブジェクト
    """
    messages = []
    messages.append({"lang": "en-US", "message": message_en})
    if message_ja is None:
        message_ja = message_en
    messages.append({"lang": "ja-JP", "message": message_ja})
    return {"messages": messages, "default_lang": "ja-JP"}


def get_target_labels(
    annotation_specs_accessor: AnnotationSpecsAccessor,
    *,
    label_ids: Sequence[str] | None,
    label_name_ens: Sequence[str] | None,
) -> list[dict[str, Any]]:
    """
    CLI引数で指定されたラベルID・ラベル名から追加対象ラベル一覧を取得する。

    Args:
        annotation_specs_accessor: アノテーション仕様アクセサ
        label_ids: 指定されたラベルID一覧。未指定時はNone
        label_name_ens: 指定されたラベル英語名一覧。未指定時はNone

    Returns:
        重複を除いた追加対象ラベル一覧

    Raises:
        ValueError: ラベルが見つからない、またはラベル名が曖昧な場合
    """
    resolved_label_ids = [] if label_ids is None else list(label_ids)
    resolved_label_name_ens = [] if label_name_ens is None else list(label_name_ens)

    result = []
    result_label_ids: set[str] = set()

    for label_id in resolved_label_ids:
        label = annotation_specs_accessor.get_label(label_id=label_id)
        if label_id not in result_label_ids:
            result.append(label)
            result_label_ids.add(label_id)

    for label_name_en in resolved_label_name_ens:
        label = annotation_specs_accessor.get_label(label_name=label_name_en)
        label_id = label["label_id"]
        if label_id not in result_label_ids:
            result.append(label)
            result_label_ids.add(label_id)

    if len(result) == 0:
        raise ValueError("追加先のラベルを1件以上指定してください。")
    return result
