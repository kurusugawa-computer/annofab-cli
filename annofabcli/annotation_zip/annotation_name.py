from __future__ import annotations

import argparse
from collections.abc import Collection, Mapping
from dataclasses import replace
from typing import Any, Protocol, TypeVar, cast

import annofabapi
from annofabapi.util.annotation_specs import get_message_with_lang


class AnnotationInfoProtocol(Protocol):
    """一覧出力用アノテーションモデルに必要な属性。"""

    @property
    def project_id(self) -> str: ...

    @property
    def label(self) -> str: ...


AnnotationInfo = TypeVar("AnnotationInfo", bound=AnnotationInfoProtocol)


class AnnotationNameTranslator:
    """アノテーションZIP内の英語名をアノテーション仕様の日本語名へ変換します。"""

    def __init__(self, annotation_specs: Mapping[str, Any]) -> None:
        """
        Args:
            annotation_specs: V2形式のアノテーション仕様。

        Returns:
            なし。
        """
        additionals_by_id = {e["additional_data_definition_id"]: e for e in annotation_specs["additionals"]}
        self._label_names: dict[str, str] = {}
        self._attribute_names: dict[tuple[str, str], str] = {}
        self._choice_names: dict[tuple[str, str, str], str] = {}

        for label in annotation_specs["labels"]:
            label_name_en = get_message_with_lang(label["label_name"], "en-US")
            label_name_ja = get_message_with_lang(label["label_name"], "ja-JP")
            if label_name_en is None:
                continue
            if label_name_ja is not None:
                self._label_names[label_name_en] = label_name_ja

            for additional_id in label["additional_data_definitions"]:
                additional = additionals_by_id[additional_id]
                attribute_name_en = get_message_with_lang(additional["name"], "en-US")
                attribute_name_ja = get_message_with_lang(additional["name"], "ja-JP")
                if attribute_name_en is None:
                    continue
                if attribute_name_ja is not None:
                    self._attribute_names[(label_name_en, attribute_name_en)] = attribute_name_ja

                for choice in additional.get("choices", []):
                    choice_name_en = get_message_with_lang(choice["name"], "en-US")
                    choice_name_ja = get_message_with_lang(choice["name"], "ja-JP")
                    if choice_name_en is not None and choice_name_ja is not None:
                        self._choice_names[(label_name_en, attribute_name_en, choice_name_en)] = choice_name_ja

    @classmethod
    def from_project(cls, service: annofabapi.Resource, project_id: str) -> AnnotationNameTranslator:
        """プロジェクトのアノテーション仕様から変換オブジェクトを生成します。

        Args:
            service: Annofab Web APIのリソース。
            project_id: プロジェクトID。

        Returns:
            生成した変換オブジェクト。
        """
        annotation_specs, _ = service.api.get_annotation_specs(project_id, query_params={"v": "2"})
        return cls(annotation_specs)

    def label_name(self, label_name: str) -> str:
        """ラベル英語名を日本語名へ変換します。

        Args:
            label_name: ラベル英語名。

        Returns:
            日本語名。対応する日本語名がなければ入力値。
        """
        return self._label_names.get(label_name, label_name)

    def attribute_name(self, label_name: str, attribute_name: str) -> str:
        """ラベル名と属性英語名の組み合わせから属性日本語名へ変換します。

        Args:
            label_name: ラベル英語名。
            attribute_name: 属性英語名。

        Returns:
            日本語名。対応する日本語名がなければ入力値。
        """
        return self._attribute_names.get((label_name, attribute_name), attribute_name)

    def choice_name(self, label_name: str, attribute_name: str, choice_name: str) -> str:
        """ラベル名、属性名、選択肢英語名の組み合わせから選択肢日本語名へ変換します。

        Args:
            label_name: ラベル英語名。
            attribute_name: 属性英語名。
            choice_name: 選択肢英語名。

        Returns:
            日本語名。対応する日本語名がなければ入力値。
        """
        return self._choice_names.get((label_name, attribute_name, choice_name), choice_name)

    def attribute_value_key(self, key: tuple[str, str, str]) -> tuple[str, str, str]:
        """属性値のキーを日本語名へ変換します。

        Args:
            key: ラベル英語名、属性英語名、選択肢英語名の組。

        Returns:
            日本語名へ変換した組。
        """
        label_name, attribute_name, choice_name = key
        return (
            self.label_name(label_name),
            self.attribute_name(label_name, attribute_name),
            self.choice_name(label_name, attribute_name, choice_name),
        )

    def annotation_info(self, annotation: AnnotationInfo) -> AnnotationInfo:
        """一覧出力用モデルに含まれる名称を日本語名へ変換します。

        Args:
            annotation: ``label`` と任意で ``attributes`` を持つモデル。

        Returns:
            名称を変換した新しいモデル。
        """
        label_name = annotation.label
        updates: dict[str, Any] = {"label": self.label_name(label_name)}
        if hasattr(annotation, "attributes"):
            attributes = cast(Mapping[str, Any], cast(Any, annotation).attributes)
            updates["attributes"] = {
                self.attribute_name(label_name, attribute_name): self.choice_name(label_name, attribute_name, value) if isinstance(value, str) else value
                for attribute_name, value in attributes.items()
            }
        annotation_object = cast(Any, annotation)
        if hasattr(annotation_object, "model_copy"):
            return cast(AnnotationInfo, annotation_object.model_copy(update=updates))
        return cast(AnnotationInfo, replace(annotation_object, **updates))


def add_use_japanese_name_argument(parser: argparse.ArgumentParser) -> None:
    """日本語名で出力するオプションを追加します。

    Args:
        parser: 引数パーサー。

    Returns:
        なし。
    """
    parser.add_argument(
        "--use_japanese_name",
        action="store_true",
        help="ラベル名、属性名、選択肢名をアノテーション仕様に登録されている日本語名で出力します。日本語名がない場合は英語名を出力します。",
    )


def translate_annotation_infos(
    service: annofabapi.Resource,
    annotations: Collection[AnnotationInfo],
    *,
    use_japanese_name: bool,
) -> list[AnnotationInfo]:
    """一覧出力用モデルの名称を必要に応じて日本語名へ変換します。

    Args:
        service: Annofab Web APIのリソース。
        annotations: 変換対象のモデル。
        use_japanese_name: 日本語名へ変換するかどうか。

    Returns:
        出力用モデルのリスト。
    """
    result = list(annotations)
    if not use_japanese_name or len(result) == 0:
        return result
    project_id = result[0].project_id
    translator = AnnotationNameTranslator.from_project(service, project_id)
    return [translator.annotation_info(e) for e in result]
