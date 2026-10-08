from __future__ import annotations

import argparse
import copy
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, Self

import pandas
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from annofabcli.common.cli import ArgumentParser, CommandLine, get_json_from_args, get_list_from_args
from annofabcli.common.utils import duplicated_set

logger = logging.getLogger(__name__)

Operation = Literal["add", "update", "delete"]
"""定型指摘に対する操作。"""

TEXT_LANGUAGES = {
    "inspection_phrase_text_ja": "ja-JP",
    "inspection_phrase_text_en": "en-US",
    "inspection_phrase_text_vi": "vi-VN",
}
"""入力項目とAPIの言語コードの対応。追加時の表示言語の優先順も表す。"""

OPERATION_NAMES = {"add": "追加", "update": "更新", "delete": "削除"}
"""ログや変更コメントに使用する操作名。"""


class InspectionPhraseInput(BaseModel):
    """追加・更新する定型指摘1件分の入力。"""

    model_config = ConfigDict(extra="forbid", strict=True)
    """未知の項目と文字列以外の入力を拒否する。"""

    inspection_phrase_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    """定型指摘ID。自動生成せず、追加・更新ともに必須。"""

    inspection_phrase_text_ja: str | None = None
    """日本語本文。未指定時は補完しない。"""

    inspection_phrase_text_en: str | None = None
    """英語本文。未指定時は補完しない。"""

    inspection_phrase_text_vi: str | None = None
    """ベトナム語本文。未指定時は補完しない。"""

    @field_validator("inspection_phrase_text_ja", "inspection_phrase_text_en", "inspection_phrase_text_vi", mode="before")
    @classmethod
    def normalize_empty_text(cls, value: str | None) -> str | None:
        """空の本文を未指定として扱う。

        Args:
            value: 入力値。

        Returns:
            空文字・空白のみの場合はNone、それ以外は入力値。
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def validate_texts(self) -> Self:
        """1言語以上の本文が指定されていることを検証する。

        Args:
            self: 検証する入力。

        Returns:
            検証済みの入力。
        """
        if not self.messages():
            raise ValueError("定型指摘の本文を日本語・英語・ベトナム語のいずれかで1つ以上指定してください。")
        return self

    def messages(self) -> list[dict[str, str]]:
        """指定された言語だけをAPIのメッセージに変換する。

        Args:
            self: 変換する入力。

        Returns:
            言語コードと本文のリスト。
        """
        return [{"lang": lang, "message": value} for field, lang in TEXT_LANGUAGES.items() if (value := getattr(self, field)) is not None]


def read_inspection_phrases_json(target: str) -> list[InspectionPhraseInput]:
    """JSON配列から定型指摘入力を読み込む。

    Args:
        target: JSON文字列または ``file://`` 付きファイル指定。

    Returns:
        定型指摘入力のリスト。
    """
    data = get_json_from_args(target)
    if not isinstance(data, list):
        raise TypeError("`--inspection_phrase_json` にはJSON配列を指定してください。")
    return [InspectionPhraseInput.model_validate(row) for row in data]


def read_inspection_phrases_csv(path: Path) -> list[InspectionPhraseInput]:
    """ヘッダー付きCSVから定型指摘入力を読み込む。

    Args:
        path: CSVファイルパス。

    Returns:
        定型指摘入力のリスト。
    """
    df = pandas.read_csv(path, dtype="string", keep_default_na=False)
    required_column = "inspection_phrase_id"
    if required_column not in df.columns:
        raise ValueError("CSVに `inspection_phrase_id` 列が必要です。")
    unexpected_columns = set(df.columns) - set(InspectionPhraseInput.model_fields)
    if unexpected_columns:
        raise ValueError(f"CSVに指定できない列があります。 :: {sorted(unexpected_columns)}")
    return [InspectionPhraseInput.model_validate(row) for row in df.to_dict(orient="records")]


def update_inspection_phrase_text(text: dict[str, Any], item: InspectionPhraseInput) -> None:
    """指定された言語の本文だけを更新する。

    Args:
        text: 更新するAPIの多言語本文。
        item: 検証済みの更新入力。

    Returns:
        None。
    """
    messages_by_lang = {message["lang"]: message for message in text["messages"]}
    for message in item.messages():
        lang = message["lang"]
        if lang in messages_by_lang:
            messages_by_lang[lang]["message"] = message["message"]
        else:
            text["messages"].append(message)
    nonempty_languages = [message["lang"] for message in text["messages"] if message["message"].strip()]
    if not nonempty_languages:
        raise ValueError("更新後の定型指摘には1言語以上の本文が必要です。")
    if text["default_lang"] not in nonempty_languages:
        text["default_lang"] = nonempty_languages[0]


def build_request_body_for_inspection_phrases(
    annotation_specs: dict[str, Any],
    *,
    operation: Operation,
    phrase_inputs: Sequence[InspectionPhraseInput] = (),
    phrase_ids: Sequence[str] = (),
    comment: str | None = None,
) -> dict[str, Any]:
    """全件を検証し、定型指摘を変更したアノテーション仕様を作る。

    Args:
        annotation_specs: 現在のアノテーション仕様（v3）。
        operation: 追加・更新・削除の種類。
        phrase_inputs: 追加・更新する定型指摘。
        phrase_ids: 削除する定型指摘ID。
        comment: 変更コメント。省略時は自動生成する。

    Returns:
        APIに渡すリクエストボディ。元の仕様は変更しない。
    """
    target_ids = list(phrase_ids) if operation == "delete" else [item.inspection_phrase_id for item in phrase_inputs]
    if not target_ids:
        raise ValueError("定型指摘を1件以上指定してください。")
    duplicates = duplicated_set(target_ids)
    if duplicates:
        raise ValueError(f"定型指摘IDが重複しています。 :: {sorted(duplicates)}")

    request_body = copy.deepcopy(annotation_specs)
    phrases = request_body["inspection_phrases"]
    existing = {phrase["id"]: phrase for phrase in phrases}
    if operation == "add":
        conflicts = set(target_ids) & set(existing)
        if conflicts:
            raise ValueError(f"追加する定型指摘IDは既に存在します。 :: {sorted(conflicts)}")
        for item in phrase_inputs:
            messages = item.messages()
            phrases.append({"id": item.inspection_phrase_id, "text": {"messages": messages, "default_lang": messages[0]["lang"]}})
    else:
        missing = set(target_ids) - set(existing)
        if missing:
            raise ValueError(f"対象の定型指摘IDが存在しません。 :: {sorted(missing)}")
        if operation == "delete":
            target_id_set = set(target_ids)
            request_body["inspection_phrases"] = [phrase for phrase in phrases if phrase["id"] not in target_id_set]
        else:
            for item in phrase_inputs:
                update_inspection_phrase_text(existing[item.inspection_phrase_id]["text"], item)

    request_body["comment"] = comment if comment is not None else f"以下の定型指摘を{OPERATION_NAMES[operation]}しました。\n定型指摘ID: {', '.join(target_ids)}"
    request_body["last_updated_datetime"] = annotation_specs["updated_datetime"]
    return request_body


class EditInspectionPhrases(CommandLine):
    """定型指摘を編集し、アノテーション仕様を保存する。"""

    def main(self) -> None:
        """入力を検証してから、確認付きで仕様を一度だけ保存する。

        Args:
            self: コマンド本体。

        Returns:
            None。
        """
        args = self.args
        operation: Operation = args.inspection_phrase_operation
        phrase_inputs = []
        phrase_ids = []
        if operation == "delete":
            phrase_ids = get_list_from_args(args.inspection_phrase_id)
        elif args.inspection_phrase_json is not None:
            phrase_inputs = read_inspection_phrases_json(args.inspection_phrase_json)
        else:
            phrase_inputs = read_inspection_phrases_csv(args.inspection_phrase_csv)
        annotation_specs, _ = self.service.api.get_annotation_specs(args.project_id, query_params={"v": "3"})
        request_body = build_request_body_for_inspection_phrases(annotation_specs, operation=operation, phrase_inputs=phrase_inputs, phrase_ids=phrase_ids, comment=args.comment)
        if request_body["inspection_phrases"] == annotation_specs["inspection_phrases"]:
            logger.info("定型指摘に変更がないため、アノテーション仕様を更新しません。")
            return
        target_ids = phrase_ids if operation == "delete" else [item.inspection_phrase_id for item in phrase_inputs]
        operation_name = OPERATION_NAMES[operation]
        if not self.confirm_processing(f"{len(target_ids)} 件の定型指摘を{operation_name}します。 :: inspection_phrase_ids={target_ids}。よろしいですか？"):
            return
        self.service.api.put_annotation_specs(args.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"{len(target_ids)} 件の定型指摘を{operation_name}しました。 :: inspection_phrase_ids={target_ids}")


def add_edit_arguments(parser: argparse.ArgumentParser, *, operation: Operation) -> None:
    """定型指摘編集コマンドの共通引数を登録する。

    Args:
        parser: 引数を登録するパーサー。
        operation: 操作の種類。

    Returns:
        None。
    """
    ArgumentParser(parser).add_project_id()
    if operation == "delete":
        parser.add_argument(
            "--inspection_phrase_id",
            required=True,
            nargs="+",
            help=(
                "削除する定型指摘ID。"
                "複数指定できます。"
                " ``file://`` を先頭に付けると一覧ファイルを指定できます。"
                " ファイルを読み込む場合は、ファイル指定を1個だけ渡してください。"
                "直接指定する値や別のファイル指定とは併用できません。"
            ),
        )
    else:
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--inspection_phrase_json",
            help="定型指摘情報のJSON配列。 ``file://`` を先頭に付けるとJSONファイルを指定できます。各要素に ``inspection_phrase_id`` と1言語以上の本文が必要です。",
        )
        group.add_argument("--inspection_phrase_csv", type=Path, help="定型指摘情報のヘッダー付きCSV。 ``inspection_phrase_id`` 列と1言語以上の本文が必要です。")
        parser.epilog = (
            "本文には inspection_phrase_text_ja（日本語）、inspection_phrase_text_en（英語）、inspection_phrase_text_vi（ベトナム語）を指定します。"
            "未指定の言語は補完しません。更新時は省略・null・空文字の本文を保持します。IDに使用できる文字は英数字・アンダースコア・ハイフンです。"
        )
    parser.add_argument("--comment", help="アノテーション仕様の変更コメント。未指定の場合は自動生成します。")
    parser.set_defaults(inspection_phrase_operation=operation)
