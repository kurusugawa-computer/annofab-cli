from __future__ import annotations

import argparse
import copy
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import annofabapi
import pandas
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor, get_attribute_name_en, get_message_with_lang

import annofabcli.common.cli
from annofabcli.annotation_specs.add_attribute import parse_default_value
from annofabcli.annotation_specs.add_labels import parse_keybind_in_csv
from annofabcli.annotation_specs.update_choices import (
    ChoiceUpdateInput,
    get_target_choice,
    parse_choice_update_input_from_dict,
    update_choice_name_en,
    update_choice_name_ja,
    update_choice_name_vi,
    validate_choice_name_ens_not_duplicated,
    validate_choice_update_inputs,
)
from annofabcli.common.annofab.annotation_specs import keybind_to_api_keybind, validate_keybind_input
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login, get_json_from_args
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import duplicated_set

logger = logging.getLogger(__name__)

ATTRIBUTE_KEYS = {
    "attribute_id",
    "attribute_name_en",
    "attribute_name_ja",
    "attribute_name_vi",
    "keybind",
    "read_only",
    "default_value",
}
"""属性更新入力で指定できる基本キー。"""

ATTRIBUTE_JSON_KEYS = ATTRIBUTE_KEYS | {"choice_updates"}
"""``--attribute_json`` の各要素に指定できるキー。"""

ATTRIBUTE_CSV_COLUMNS = ATTRIBUTE_KEYS
"""``--attribute_csv`` で指定できる列。"""


@dataclass(frozen=True)
class AttributeUpdateInput:
    """
    コマンドラインから受け取った属性1件分の更新情報。
    """

    attribute_id: str | None = None
    """更新対象属性ID。"""

    attribute_name_en: str | None = None
    """更新後の属性英語名。"""

    attribute_name_ja: str | None = None
    """更新後の属性日本語名。"""

    attribute_name_vi: str | None = None
    """更新後の属性ベトナム語名。"""

    keybind: dict[str, Any] | None = None
    """更新後のkeybind。"""

    read_only: bool | None = None
    """更新後のread_only。"""

    default_value: str | int | bool | None = None
    """更新後のdefault。"""

    has_default_value: bool = False
    """``default_value`` が明示的に指定されたか。"""

    choice_updates: list[ChoiceUpdateInput] | None = None
    """更新する既存選択肢の情報。"""


@dataclass(frozen=True)
class ResolvedAttributeUpdateInput:
    """
    既存アノテーション仕様に対して解決済みの属性更新情報。
    """

    target_attribute: Mapping[str, Any]
    """更新対象属性。"""

    attribute_update_input: AttributeUpdateInput
    """更新情報。"""


def validate_attribute_update_input(attribute_update_input: AttributeUpdateInput, *, index: int) -> None:
    """
    属性更新入力を検証する。
    """
    if attribute_update_input.attribute_id is None:
        raise ValueError(f"{index}件目の属性に `attribute_id` が指定されていません。")

    has_update_field = any(
        [
            attribute_update_input.attribute_name_en is not None,
            attribute_update_input.attribute_name_ja is not None,
            attribute_update_input.attribute_name_vi is not None,
            attribute_update_input.keybind is not None,
            attribute_update_input.read_only is not None,
            attribute_update_input.has_default_value,
            attribute_update_input.choice_updates is not None,
        ]
    )
    if not has_update_field:
        raise ValueError(f"{index}件目の属性に更新するフィールドが指定されていません。")
    if attribute_update_input.read_only is not None and not isinstance(attribute_update_input.read_only, bool):
        raise ValueError(f"{index}件目の属性の `read_only` には真偽値を指定してください。")
    if attribute_update_input.choice_updates is not None:
        validate_choice_update_inputs(attribute_update_input.choice_updates)


def parse_choice_update_inputs_from_dict(data: dict[str, Any], *, index: int) -> list[ChoiceUpdateInput] | None:
    """
    属性更新JSON内の ``choice_updates`` を選択肢更新入力に変換する。
    """
    if "choice_updates" not in data:
        return None

    choice_updates = data["choice_updates"]
    if not isinstance(choice_updates, list):
        raise TypeError(f"{index}件目の属性の `choice_updates` には選択肢更新情報の配列を指定してください。")

    result = []
    for choice_index, choice_update in enumerate(choice_updates, start=1):
        if not isinstance(choice_update, dict):
            raise TypeError(f"{index}件目の属性の `choice_updates` の {choice_index} 件目がオブジェクト形式ではありません。")
        result.append(parse_choice_update_input_from_dict(choice_update, index=choice_index))
    return result


def parse_attribute_update_input_from_dict(data: dict[str, Any], *, index: int) -> AttributeUpdateInput:
    """
    JSONオブジェクト1件を属性更新入力に変換する。
    """
    unexpected_keys = set(data) - ATTRIBUTE_JSON_KEYS
    if unexpected_keys:
        raise ValueError(f"{index}件目の属性に指定できないキーがあります。 :: {sorted(unexpected_keys)}")

    attribute_update_input = AttributeUpdateInput(
        attribute_id=data.get("attribute_id"),
        attribute_name_en=data.get("attribute_name_en"),
        attribute_name_ja=data.get("attribute_name_ja"),
        attribute_name_vi=data.get("attribute_name_vi"),
        keybind=None if data.get("keybind") is None else validate_keybind_input(data["keybind"]),
        read_only=data.get("read_only"),
        default_value=data.get("default_value"),
        has_default_value="default_value" in data,
        choice_updates=parse_choice_update_inputs_from_dict(data, index=index),
    )
    validate_attribute_update_input(attribute_update_input, index=index)
    return attribute_update_input


def read_attributes_json(target: str) -> list[AttributeUpdateInput]:
    """
    ``--attribute_json`` で指定されたJSONから属性更新一覧を読み込む。
    """
    raw_data = get_json_from_args(target)
    if not isinstance(raw_data, list):
        raise TypeError("`--attribute_json` には属性更新情報の配列を指定してください。")

    result = []
    for index, attribute_data in enumerate(raw_data, start=1):
        if not isinstance(attribute_data, dict):
            raise TypeError(f"{index}件目の属性がオブジェクト形式ではありません。")
        result.append(parse_attribute_update_input_from_dict(attribute_data, index=index))
    return result


def read_attributes_csv(csv_path: Path) -> list[AttributeUpdateInput]:
    """
    ``--attribute_csv`` で指定されたCSVから属性更新一覧を読み込む。
    """
    try:
        df = pandas.read_csv(
            csv_path,
            dtype={
                "attribute_id": "string",
                "attribute_name_en": "string",
                "attribute_name_ja": "string",
                "attribute_name_vi": "string",
                "keybind": "string",
                "read_only": "boolean",
                "default_value": "string",
            },
        )
    except Exception as e:
        raise ValueError(f"`--attribute_csv` の読み込みに失敗しました。 :: {e}") from e

    unexpected_columns = set(df.columns) - ATTRIBUTE_CSV_COLUMNS
    if unexpected_columns:
        raise ValueError(f"`--attribute_csv` に指定できない列があります。 :: {sorted(unexpected_columns)}")

    result = []
    for index, row in enumerate(df.to_dict(orient="records"), start=1):
        default_value = row.get("default_value")
        attribute_update_input = AttributeUpdateInput(
            attribute_id=row.get("attribute_id"),
            attribute_name_en=row.get("attribute_name_en"),
            attribute_name_ja=row.get("attribute_name_ja"),
            attribute_name_vi=row.get("attribute_name_vi"),
            keybind=parse_keybind_in_csv(row.get("keybind"), index=index),
            read_only=row.get("read_only"),
            default_value=default_value,
            has_default_value=default_value is not None,
        )
        validate_attribute_update_input(attribute_update_input, index=index)
        result.append(attribute_update_input)
    return result


def validate_attribute_update_inputs(attribute_update_inputs: Sequence[AttributeUpdateInput]) -> None:
    """
    属性更新入力一覧を検証する。
    """
    if len(attribute_update_inputs) == 0:
        raise ValueError("更新する属性を1件以上指定してください。")

    duplicated_attribute_ids = duplicated_set([attribute.attribute_id for attribute in attribute_update_inputs if attribute.attribute_id is not None])
    if duplicated_attribute_ids:
        duplicated_text = ", ".join(sorted(duplicated_attribute_ids))
        raise ValueError(f"入力された属性に重複した `attribute_id` があります。 :: {duplicated_text}")


def resolve_attribute_update_inputs(
    annotation_specs: dict[str, Any],
    *,
    attribute_update_inputs: Sequence[AttributeUpdateInput],
) -> list[ResolvedAttributeUpdateInput]:
    """
    属性更新入力一覧を既存アノテーション仕様に対して解決する。
    """
    validate_attribute_update_inputs(attribute_update_inputs)
    annotation_specs_accessor = AnnotationSpecsAccessor(annotation_specs)

    result = []
    resolved_attribute_ids: set[str] = set()
    for attribute_update_input in attribute_update_inputs:
        target_attribute = annotation_specs_accessor.get_attribute(attribute_id=attribute_update_input.attribute_id)

        target_attribute_id = target_attribute["additional_data_definition_id"]
        if target_attribute_id in resolved_attribute_ids:
            raise ValueError(f"同じ属性を複数回更新しようとしています。 :: attribute_id='{target_attribute_id}'")
        if attribute_update_input.choice_updates is not None:
            if target_attribute["type"] not in ["choice", "select"]:
                raise ValueError(f"属性ID='{target_attribute_id}' は選択肢系属性ではありません。")
            for choice_update_input in attribute_update_input.choice_updates:
                get_target_choice(target_attribute, choice_update_input)
        resolved_attribute_ids.add(target_attribute_id)
        result.append(ResolvedAttributeUpdateInput(target_attribute=target_attribute, attribute_update_input=attribute_update_input))

    return result


def update_attribute_name_ja(attribute: dict[str, Any], attribute_name_ja: str) -> None:
    """
    属性日本語名を更新する。
    """
    if get_message_with_lang(attribute["name"], "ja-JP") is None:
        attribute["name"]["messages"].append({"lang": "ja-JP", "message": attribute_name_ja})
        return

    for message in attribute["name"]["messages"]:
        if message["lang"] == "ja-JP":
            message["message"] = attribute_name_ja
            return


def update_attribute_name_vi(attribute: dict[str, Any], attribute_name_vi: str) -> None:
    """
    属性ベトナム語名を更新する。
    """
    if get_message_with_lang(attribute["name"], "vi-VN") is None:
        attribute["name"]["messages"].append({"lang": "vi-VN", "message": attribute_name_vi})
        return

    for message in attribute["name"]["messages"]:
        if message["lang"] == "vi-VN":
            message["message"] = attribute_name_vi
            return


def update_attribute_name_en(attribute: dict[str, Any], attribute_name_en: str) -> None:
    """
    属性英語名を更新する。
    """
    if get_message_with_lang(attribute["name"], "en-US") is None:
        attribute["name"]["messages"].append({"lang": "en-US", "message": attribute_name_en})
        return

    for message in attribute["name"]["messages"]:
        if message["lang"] == "en-US":
            message["message"] = attribute_name_en
            return


def update_choices(attribute: dict[str, Any], choice_updates: Sequence[ChoiceUpdateInput]) -> None:
    """
    属性配下の既存選択肢を更新する。
    """
    choice_update_dict = {choice_update.choice_id: choice_update for choice_update in choice_updates}
    for choice in attribute["choices"]:
        choice_update_input = choice_update_dict.get(choice["choice_id"])
        if choice_update_input is None:
            continue
        if choice_update_input.choice_name_en is not None:
            update_choice_name_en(choice, choice_update_input.choice_name_en)
        if choice_update_input.choice_name_ja is not None:
            update_choice_name_ja(choice, choice_update_input.choice_name_ja)
        if choice_update_input.choice_name_vi is not None:
            update_choice_name_vi(choice, choice_update_input.choice_name_vi)
        if choice_update_input.has_keybind:
            choice["keybind"] = keybind_to_api_keybind(copy.deepcopy(choice_update_input.keybind))
    validate_choice_name_ens_not_duplicated(attribute)


def validate_attribute_name_ens_not_duplicated_in_labels(annotation_specs: Mapping[str, Any]) -> None:
    """
    ラベル内の属性英語名が重複していないことを検証する。
    """
    attributes_by_id = {attribute["additional_data_definition_id"]: attribute for attribute in annotation_specs["additionals"]}
    for label in annotation_specs["labels"]:
        attribute_name_ens = []
        for attribute_id in label["additional_data_definitions"]:
            attribute = attributes_by_id.get(attribute_id)
            if attribute is not None:
                attribute_name_ens.append(get_attribute_name_en(attribute))
        duplicated_attribute_name_ens = duplicated_set([name for name in attribute_name_ens if name is not None])
        if duplicated_attribute_name_ens:
            duplicated_text = ", ".join(sorted(duplicated_attribute_name_ens))
            raise ValueError(f"ラベル内の属性名(英語)に重複があります。 :: label_id='{label['label_id']}', attribute_name_en={duplicated_text}")


def create_comment_for_update_attributes(resolved_attribute_update_inputs: Sequence[ResolvedAttributeUpdateInput]) -> str:
    """
    属性更新時のデフォルトコメントを生成する。
    """
    attribute_texts = []
    for attribute_input in resolved_attribute_update_inputs:
        attribute_id = attribute_input.target_attribute["additional_data_definition_id"]
        old_attribute_name_en = get_attribute_name_en(attribute_input.target_attribute)
        new_attribute_name_en = attribute_input.attribute_update_input.attribute_name_en
        if new_attribute_name_en is not None and new_attribute_name_en != old_attribute_name_en:
            attribute_text = f"attribute_id='{attribute_id}', attribute_name_en='{old_attribute_name_en}' -> '{new_attribute_name_en}'"
        else:
            attribute_text = f"attribute_id='{attribute_id}', attribute_name_en='{old_attribute_name_en}'"
        attribute_texts.append(attribute_text)
    return f"以下の属性情報を更新しました。\n対象属性: {', '.join(attribute_texts)}"


def build_request_body_for_update_attributes(
    annotation_specs: dict[str, Any],
    *,
    resolved_attribute_update_inputs: Sequence[ResolvedAttributeUpdateInput],
    comment: str | None,
) -> dict[str, Any]:
    """
    複数属性更新用の request body を生成する。
    """
    request_body = copy.deepcopy(annotation_specs)
    attribute_input_dict = {attribute_input.target_attribute["additional_data_definition_id"]: attribute_input.attribute_update_input for attribute_input in resolved_attribute_update_inputs}
    for attribute in request_body["additionals"]:
        attribute_update_input = attribute_input_dict.get(attribute["additional_data_definition_id"])
        if attribute_update_input is None:
            continue

        if attribute_update_input.attribute_name_en is not None:
            update_attribute_name_en(attribute, attribute_update_input.attribute_name_en)
        if attribute_update_input.attribute_name_ja is not None:
            update_attribute_name_ja(attribute, attribute_update_input.attribute_name_ja)
        if attribute_update_input.attribute_name_vi is not None:
            update_attribute_name_vi(attribute, attribute_update_input.attribute_name_vi)
        if attribute_update_input.keybind is not None:
            attribute["keybind"] = keybind_to_api_keybind(copy.deepcopy(attribute_update_input.keybind))
        if attribute_update_input.read_only is not None:
            attribute["read_only"] = attribute_update_input.read_only
        if attribute_update_input.has_default_value:
            attribute["default"] = parse_default_value(attribute["type"], attribute_update_input.default_value)
        if attribute_update_input.choice_updates is not None:
            update_choices(attribute, attribute_update_input.choice_updates)

    validate_attribute_name_ens_not_duplicated_in_labels(request_body)

    if comment is None:
        comment = create_comment_for_update_attributes(resolved_attribute_update_inputs)
    request_body["comment"] = comment
    request_body["last_updated_datetime"] = annotation_specs["updated_datetime"]
    return request_body


class UpdateAttributesMain(CommandLineWithConfirm):
    """
    既存属性の情報を更新する本体処理。
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

    def update_attributes(
        self,
        *,
        attribute_update_inputs: Sequence[AttributeUpdateInput],
        comment: str | None = None,
    ) -> bool:
        """
        複数属性の情報を更新して、アノテーション仕様を更新する。
        """
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        resolved_attribute_update_inputs = resolve_attribute_update_inputs(old_annotation_specs, attribute_update_inputs=attribute_update_inputs)
        attribute_names = [get_attribute_name_en(attribute_input.target_attribute) for attribute_input in resolved_attribute_update_inputs]

        confirm_message = f"{len(resolved_attribute_update_inputs)} 件の属性情報を更新します。対象属性={attribute_names}。よろしいですか？"
        if not self.confirm_processing(confirm_message):
            return False

        request_body = build_request_body_for_update_attributes(
            old_annotation_specs,
            resolved_attribute_update_inputs=resolved_attribute_update_inputs,
            comment=comment,
        )
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"{len(resolved_attribute_update_inputs)} 件の属性情報を更新しました。")
        return True


class UpdateAttributes(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs update_attributes: error:"

    def main(self) -> None:
        """
        コマンドライン引数を解釈し、複数属性更新処理を実行する。
        """
        args = self.args
        if args.attribute_json is not None:
            attribute_update_inputs = read_attributes_json(args.attribute_json)
        elif args.attribute_csv is not None:
            if not args.attribute_csv.exists():
                raise ValueError(f"`--attribute_csv` に指定されたファイルが存在しません。 :: {args.attribute_csv}")
            attribute_update_inputs = read_attributes_csv(args.attribute_csv)
        else:
            raise ValueError("`--attribute_json` , `--attribute_csv` のいずれかを指定してください。")

        obj = UpdateAttributesMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.update_attributes(
            attribute_update_inputs=attribute_update_inputs,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    ``update_attributes`` サブコマンドの引数を定義する。
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    sample_json = [
        {
            "attribute_id": "54fa5e97-6f88-49a4-aeb0-a91a15d11528",
            "attribute_name_en": "comment",
            "attribute_name_ja": "コメント",
            "attribute_name_vi": "bình luận",
            "keybind": {"alt": False, "code": "Digit1", "ctrl": True, "shift": False},
            "read_only": False,
            "default_value": "確認済み",
        },
        {
            "attribute_id": "71620647-98cf-48ad-b43b-4af425a24f32",
            "attribute_name_ja": "種別",
            "choice_updates": [
                {"choice_id": "08ec927c-18e6-4bba-837a-b16de7061580", "choice_name_ja": "大", "keybind": {"alt": False, "code": "Digit2", "ctrl": True, "shift": False}},
                {"choice_id": "74691a87-7962-4fa9-ba52-7cc466ecd982", "keybind": None},
            ],
        },
        {"attribute_id": "f12a0b59-dfce-4241-bb87-4b2c0259fc6f", "read_only": True, "default_value": True},
    ]
    attribute_group = parser.add_mutually_exclusive_group(required=True)
    attribute_group.add_argument(
        "--attribute_json",
        type=str,
        help=(
            "更新する属性情報のJSON配列を指定します。 ``file://`` を先頭に付けるとJSON形式のファイルを指定できます。"
            " 各要素には更新対象を示す ``attribute_id`` が必要です。"
            " 任意で更新後の ``attribute_name_en`` , ``attribute_name_ja`` , ``attribute_name_vi`` , ``keybind`` , ``read_only`` , ``default_value`` , ``choice_updates`` を指定できます。"
            " ``choice_updates`` では既存選択肢の ``choice_name_en`` , ``choice_name_ja`` , ``choice_name_vi`` , ``keybind`` を更新できます。"
            f"\n(例) ``{json.dumps(sample_json, ensure_ascii=False)}``"
        ),
    )
    attribute_group.add_argument(
        "--attribute_csv",
        type=Path,
        help=(
            "更新する属性情報のCSVファイルを指定します。 CSVには更新対象を示す ``attribute_id`` 列が必要です。"
            " 任意で更新後の ``attribute_name_en`` , ``attribute_name_ja`` , ``attribute_name_vi`` , ``keybind`` , ``read_only`` , ``default_value`` 列を指定できます。"
            " ``keybind`` 列にはJSONオブジェクト文字列を指定してください。"
        ),
    )
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``update_attributes`` コマンドのエントリポイント。
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateAttributes(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs update_attributes`` 用のparserを生成する。
    """
    subcommand_name = "update_attributes"
    subcommand_help = "アノテーション仕様の既存属性情報を更新します。"
    description = "アノテーション仕様の既存属性に設定された英語名、日本語名、ベトナム語名、キーバインド、read_only、default_value と、既存選択肢の名前、ショートカットキーを更新します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
