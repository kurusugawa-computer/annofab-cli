from __future__ import annotations

import argparse
import copy
import json
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import annofabapi
import pandas

import annofabcli.common.cli
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    get_list_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import duplicated_set

logger = logging.getLogger(__name__)


@dataclass
class ChoiceAttributeInput:
    """
    コマンドラインから受け取った選択肢1件分の入力情報。
    """

    choice_name_en: str
    """選択肢の英語名"""

    choice_name_ja: str | None = None
    """選択肢の日本語名"""

    choice_id: str | None = None
    """選択肢ID。未指定の場合はUUIDv4を自動生成する"""

    is_default: bool = False
    """属性のデフォルト値として使用する選択肢かどうか"""


def create_name(message_en: str, message_ja: str | None = None) -> dict[str, Any]:
    """
    Annofabの多言語メッセージ形式を生成する。

    Args:
        message_en: 英語メッセージ
        message_ja: 日本語メッセージ

    Returns:
        Annofab APIが要求する ``name`` オブジェクト
    """
    messages = []
    if message_ja is not None:
        messages.append({"lang": "ja-JP", "message": message_ja})
    messages.append({"lang": "en-US", "message": message_en})
    return {"messages": messages, "default_lang": "ja-JP"}


def parse_choice_input_from_dict(data: dict[str, Any], *, index: int) -> ChoiceAttributeInput:
    """
    JSONオブジェクト1件を選択肢入力に変換する。

    Args:
        data: 選択肢情報を表すdict
        index: エラーメッセージ用の1始まりの位置

    Returns:
        変換後の選択肢入力

    Raises:
        ValueError: 必須項目や型が不正な場合
    """
    choice_name_en = data.get("choice_name_en")
    if choice_name_en is None:
        raise ValueError(f"{index}件目の選択肢に `choice_name_en` が指定されていません。")

    return ChoiceAttributeInput(
        choice_name_en=choice_name_en,
        choice_name_ja=data.get("choice_name_ja"),
        choice_id=data.get("choice_id"),
        is_default=data.get("is_default", False),
    )


def read_choices_json(target: str) -> list[ChoiceAttributeInput]:
    """
    ``--choices_json`` で指定されたJSONから選択肢一覧を読み込む。

    Args:
        target: JSON文字列または ``file://`` 付きファイル指定

    Returns:
        選択肢入力の一覧

    Raises:
        TypeError: JSON全体が配列でない、または配列要素がオブジェクトでない場合
        ValueError: 各選択肢オブジェクトの必須項目が不足している場合
    """
    raw_data = get_json_from_args(target)
    if not isinstance(raw_data, list):
        raise TypeError("`--choices_json` には選択肢情報の配列を指定してください。")

    result = []
    for index, choice_data in enumerate(raw_data, start=1):
        if not isinstance(choice_data, dict):
            raise TypeError(f"{index}件目の選択肢がオブジェクト形式ではありません。")
        result.append(parse_choice_input_from_dict(choice_data, index=index))
    return result


def read_choices_csv(csv_path: Path) -> list[ChoiceAttributeInput]:
    """
    ``--choices_csv`` で指定されたCSVから選択肢一覧を読み込む。

    Args:
        csv_path: CSVファイルパス

    Returns:
        選択肢入力の一覧

    Raises:
        ValueError: CSV読み込みに失敗した場合、または必須列が不足している場合
    """
    try:
        df = pandas.read_csv(
            csv_path,
            dtype={
                "choice_id": "string",
                "choice_name_en": "string",
                "choice_name_ja": "string",
                "is_default": "Boolean",
            },
        )
    except Exception as e:
        raise ValueError(f"`--choices_csv` の読み込みに失敗しました。 :: {e}") from e

    required_columns = {"choice_name_en"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"`--choices_csv` には次の列が必要です。 :: {required_columns}")

    result = []
    for row in df.to_dict(orient="records"):
        choice_name_en = row["choice_name_en"]
        choice_name_ja = row.get("choice_name_ja")
        choice_id = row.get("choice_id")
        is_default = row.get("is_default", False)
        result.append(
            ChoiceAttributeInput(
                choice_name_en=choice_name_en,
                choice_name_ja=choice_name_ja,
                choice_id=choice_id,
                is_default=is_default,
            )
        )
    return result


def validate_choice_inputs(choice_inputs: Sequence[ChoiceAttributeInput]) -> None:
    """
    選択肢入力一覧の整合性を検証する。

    Args:
        choice_inputs: 検証対象の選択肢一覧

    Raises:
        ValueError: 件数、重複、既定値の数が不正な場合
    """
    if len(choice_inputs) == 0:
        raise ValueError("選択肢を1件以上指定してください。")

    duplicated_choice_ids = duplicated_set([choice.choice_id for choice in choice_inputs if choice.choice_id is not None])
    if duplicated_choice_ids:
        duplicated_text = ", ".join(sorted(duplicated_choice_ids))
        raise ValueError(f"入力された選択肢に重複した `choice_id` があります。 :: {duplicated_text}")

    default_count = len([choice for choice in choice_inputs if choice.is_default])
    if default_count > 1:
        raise ValueError("`is_default=true` を指定できる選択肢は0件または1件です。")


def build_choices(choice_inputs: Sequence[ChoiceAttributeInput]) -> tuple[list[dict[str, Any]], str]:
    """
    選択肢入力からAnnofab API向けのchoices配列を生成する。

    Args:
        choice_inputs: コマンドラインから受け取った選択肢一覧

    Returns:
        ``(choices, default_choice_id)`` のタプル

    Raises:
        ValueError: 選択肢入力の整合性が不正な場合
    """
    validate_choice_inputs(choice_inputs)

    choices: list[dict[str, Any]] = []
    default_choice_id = ""
    for choice_input in choice_inputs:
        choice_id = choice_input.choice_id if choice_input.choice_id is not None else str(uuid.uuid4())
        choices.append(
            {
                "choice_id": choice_id,
                "name": create_name(choice_input.choice_name_en, choice_input.choice_name_ja),
                "keybind": [],
            }
        )
        if choice_input.is_default:
            default_choice_id = choice_id

    duplicated_generated_ids = duplicated_set([choice["choice_id"] for choice in choices])
    if duplicated_generated_ids:
        duplicated_text = ", ".join(sorted(duplicated_generated_ids))
        raise ValueError(f"生成後の選択肢IDが重複しました。 :: {duplicated_text}")

    return choices, default_choice_id


def create_comment_from_attribute(attribute_name_en: str, label_names: Sequence[str]) -> str:
    """
    属性追加時のデフォルトコメントを生成する。

    Args:
        attribute_name_en: 属性の英語名
        label_names: 追加先ラベルの英語名一覧

    Returns:
        アノテーション仕様変更コメント
    """
    labels_text = ", ".join(label_names)
    return f"以下の選択肢系属性を追加しました。\n属性名(英語): {attribute_name_en}\n対象ラベル: {labels_text}"


def get_target_labels(
    labels: Sequence[dict[str, Any]],
    *,
    label_ids: Sequence[str],
    label_name_ens: Sequence[str],
) -> list[dict[str, Any]]:
    """
    CLI引数で指定されたラベルID・ラベル名から追加対象ラベル一覧を取得する。

    Args:
        labels: アノテーション仕様に含まれるラベル一覧
        label_ids: 指定されたラベルID一覧
        label_name_ens: 指定されたラベル英語名一覧

    Returns:
        重複を除いた追加対象ラベル一覧

    Raises:
        ValueError: ラベルが見つからない、またはラベル名が曖昧な場合
    """
    result = []
    result_label_ids: set[str] = set()

    dict_label = {label["label_id"]: label for label in labels}
    for label_id in label_ids:
        label = dict_label.get(label_id)
        if label is None:
            raise ValueError(f"ラベルID='{label_id}' のラベルは存在しません。")
        if label_id not in result_label_ids:
            result.append(label)
            result_label_ids.add(label_id)

    for label_name_en in label_name_ens:
        matched_labels = [label for label in labels if AnnofabApiFacade.get_label_name_en(label) == label_name_en]
        if len(matched_labels) == 0:
            raise ValueError(f"ラベル名(英語)='{label_name_en}' のラベルは存在しません。")
        if len(matched_labels) >= 2:
            raise ValueError(f"ラベル名(英語)='{label_name_en}' のラベルが複数存在します。 `--label_id` を指定してください。")

        label = matched_labels[0]
        label_id = label["label_id"]
        if label_id not in result_label_ids:
            result.append(label)
            result_label_ids.add(label_id)

    if len(result) == 0:
        raise ValueError("追加先のラベルを1件以上指定してください。")
    return result


def validate_new_attribute(
    additionals: Sequence[dict[str, Any]],
    *,
    attribute_id: str,
    attribute_name_en: str,
) -> None:
    """
    追加予定の属性ID・属性英語名が既存属性と衝突しないか検証する。

    Args:
        additionals: 既存の属性一覧
        attribute_id: 追加予定の属性ID
        attribute_name_en: 追加予定の属性英語名

    Raises:
        ValueError: 既存属性と重複する場合
    """
    if any(additional["additional_data_definition_id"] == attribute_id for additional in additionals):
        raise ValueError(f"属性ID='{attribute_id}' の属性は既に存在します。")

    if any(AnnofabApiFacade.get_additional_data_definition_name_en(additional) == attribute_name_en for additional in additionals):
        raise ValueError(f"属性名(英語)='{attribute_name_en}' の属性は既に存在します。")


def create_attribute(
    *,
    attribute_type: str,
    attribute_name_en: str,
    attribute_name_ja: str | None,
    attribute_id: str | None,
    choice_inputs: Sequence[ChoiceAttributeInput],
) -> dict[str, Any]:
    """
    選択肢系属性1件分のAnnofab API向けオブジェクトを生成する。

    Args:
        attribute_type: 属性型。 ``choice`` または ``select``
        attribute_name_en: 属性英語名
        attribute_name_ja: 属性日本語名
        attribute_id: 属性ID。未指定ならUUIDv4を自動生成
        choice_inputs: 選択肢入力一覧

    Returns:
        Annofab API向けの属性オブジェクト

    Raises:
        ValueError: 選択肢入力の整合性が不正な場合
    """
    choices, default_choice_id = build_choices(choice_inputs)
    return {
        "additional_data_definition_id": attribute_id if attribute_id is not None else str(uuid.uuid4()),
        "name": create_name(attribute_name_en, attribute_name_ja),
        # "keybind": [],
        "type": attribute_type,
        "default": default_choice_id,
        "choices": choices,
    }


class AddChoiceAttributeMain(CommandLineWithConfirm):
    """
    選択肢系属性をアノテーション仕様へ追加する本体処理。
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

    def add_choice_attribute(
        self,
        *,
        attribute_type: str,
        attribute_name_en: str,
        attribute_name_ja: str | None,
        attribute_id: str | None,
        choice_inputs: Sequence[ChoiceAttributeInput],
        label_ids: Sequence[str],
        label_name_ens: Sequence[str],
        comment: str | None = None,
    ) -> bool:
        """
        選択肢系属性を追加し、指定ラベルへ紐付けてアノテーション仕様を更新する。

        Args:
            attribute_type: 属性型。 ``choice`` または ``select``
            attribute_name_en: 属性英語名
            attribute_name_ja: 属性日本語名
            attribute_id: 属性ID。未指定ならUUIDv4を自動生成
            choice_inputs: 選択肢入力一覧
            label_ids: 追加先ラベルID一覧
            label_name_ens: 追加先ラベル英語名一覧
            comment: 変更コメント

        Returns:
            追加を実行した場合はTrue、確認で中断した場合はFalse

        Raises:
            ValueError: 入力値や既存アノテーション仕様との整合性が不正な場合
        """
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        additionals = old_annotation_specs["additionals"]
        target_labels = get_target_labels(old_annotation_specs["labels"], label_ids=label_ids, label_name_ens=label_name_ens)
        new_attribute = create_attribute(
            attribute_type=attribute_type,
            attribute_name_en=attribute_name_en,
            attribute_name_ja=attribute_name_ja,
            attribute_id=attribute_id,
            choice_inputs=choice_inputs,
        )

        validate_new_attribute(
            additionals,
            attribute_id=new_attribute["additional_data_definition_id"],
            attribute_name_en=attribute_name_en,
        )

        label_names = [AnnofabApiFacade.get_label_name_en(label) for label in target_labels]
        confirm_message = f"属性名(英語)='{attribute_name_en}', 属性種類='{attribute_type}', 選択肢数={len(new_attribute['choices'])}, 対象ラベル={label_names} を追加します。よろしいですか？"
        if not self.confirm_processing(confirm_message):
            return False

        request_body = copy.deepcopy(old_annotation_specs)
        request_body["additionals"].append(new_attribute)
        target_label_id_set = {label["label_id"] for label in target_labels}
        for label in request_body["labels"]:
            if label["label_id"] in target_label_id_set:
                label["additional_data_definitions"].append(new_attribute["additional_data_definition_id"])

        if comment is None:
            comment = create_comment_from_attribute(attribute_name_en, label_names)
        request_body["comment"] = comment
        request_body["last_updated_datetime"] = old_annotation_specs["updated_datetime"]
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"属性名(英語)='{attribute_name_en}', 属性ID='{new_attribute['additional_data_definition_id']}' の選択肢系属性を追加しました。")
        return True


class AddChoiceAttribute(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs add_choice_attribute: error:"

    def main(self) -> None:
        """
        コマンドライン引数を解釈し、選択肢系属性追加処理を実行する。
        """
        args = self.args

        if args.choices_json is not None:
            choice_inputs = read_choices_json(args.choices_json)
        elif args.choices_csv is not None:
            if not args.choices_csv.exists():
                raise ValueError(f"`--choices_csv` に指定されたファイルが存在しません。 :: {args.choices_csv}")
            choice_inputs = read_choices_csv(args.choices_csv)
        else:
            raise ValueError("`--choices_json` または `--choices_csv` のいずれかを指定してください。")

        label_ids = get_list_from_args(args.label_id)
        label_name_ens = get_list_from_args(args.label_name_en)

        obj = AddChoiceAttributeMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.add_choice_attribute(
            attribute_type=args.attribute_type,
            attribute_name_en=args.attribute_name_en,
            attribute_name_ja=args.attribute_name_ja,
            attribute_id=args.attribute_id,
            choice_inputs=choice_inputs,
            label_ids=label_ids,
            label_name_ens=label_name_ens,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    ``add_choice_attribute`` サブコマンドの引数を定義する。

    Args:
        parser: 引数を追加するArgumentParser
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    parser.add_argument(
        "--attribute_type",
        type=str,
        required=True,
        choices=["choice", "select"],
        help="追加する属性の種類。 ``choice`` はラジオボタン、 ``select`` はドロップダウンです。",
    )
    parser.add_argument("--attribute_name_en", type=str, required=True, help="追加する属性の英語名。")
    parser.add_argument("--attribute_id", type=str, help="追加する属性の属性ID。未指定の場合はUUIDv4を自動生成します。")
    parser.add_argument("--attribute_name_ja", type=str, help="追加する属性の日本語名。")

    sample_json = [
        {"choice_id": "front", "choice_name_en": "front", "choice_name_ja": "前", "is_default": True},
        {"choice_name_en": "rear"},
    ]
    choice_group = parser.add_mutually_exclusive_group(required=True)
    choice_group.add_argument(
        "--choices_json",
        type=str,
        help=f"追加する選択肢情報のJSON配列を指定します。 ``file://`` を先頭に付けるとJSON形式のファイルを指定できます。\n(例) ``{json.dumps(sample_json, ensure_ascii=False)}``",
    )
    choice_group.add_argument(
        "--choices_csv",
        type=Path,
        help="追加する選択肢情報のCSVファイルを指定します。 CSVには ``choice_name_en`` 列が必要です。 任意で ``choice_id`` , ``choice_name_ja`` , ``is_default`` 列を指定できます。",
    )

    parser.add_argument(
        "--label_name_en",
        type=str,
        nargs="+",
        help="属性を追加する対象ラベルの英語名。複数指定できます。 ``file://`` を先頭に付けると一覧ファイルを指定できます。",
    )
    parser.add_argument(
        "--label_id",
        type=str,
        nargs="+",
        help="属性を追加する対象ラベルのlabel_id。複数指定できます。 ``file://`` を先頭に付けると一覧ファイルを指定できます。",
    )
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更時に指定できるコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``add_choice_attribute`` コマンドのエントリポイント。

    Args:
        args: コマンドライン引数
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    AddChoiceAttribute(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs add_choice_attribute`` 用のparserを生成する。

    Args:
        subparsers: 親parserのsubparsers

    Returns:
        生成したArgumentParser
    """
    subcommand_name = "add_choice_attribute"
    subcommand_help = "アノテーション仕様に選択肢系属性を追加します。"
    description = "アノテーション仕様に ``choice`` （ラジオボタン）または ``select`` （ドロップダウン）の属性を追加し、指定ラベルへ紐付けます。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
