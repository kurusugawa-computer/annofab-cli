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
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor, get_attribute_name_en

import annofabcli.common.cli
from annofabcli.annotation_specs.add_attribute import parse_default_value
from annofabcli.annotation_specs.add_labels import parse_keybind_in_csv
from annofabcli.common.annofab.annotation_specs import keybind_to_api_keybind, validate_keybind_input
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login, get_json_from_args
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import duplicated_set

logger = logging.getLogger(__name__)

ATTRIBUTE_JSON_KEYS = {
    "attribute_id",
    "attribute_name_en",
    "attribute_name_ja",
    "keybind",
    "read_only",
    "default_value",
}
"""``--attribute_json`` の各要素に指定できるキー。"""


@dataclass(frozen=True)
class AttributeUpdateInput:
    """
    コマンドラインから受け取った属性1件分の更新情報。
    """

    attribute_id: str | None = None
    """更新対象属性ID。"""

    attribute_name_en: str | None = None
    """更新対象属性の英語名。"""

    attribute_name_ja: str | None = None
    """更新後の属性日本語名。"""

    keybind: dict[str, Any] | None = None
    """更新後のkeybind。"""

    read_only: bool | None = None
    """更新後のread_only。"""

    default_value: str | int | bool | None = None
    """更新後のdefault。"""

    has_default_value: bool = False
    """``default_value`` が明示的に指定されたか。"""


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
    if (attribute_update_input.attribute_id is None) == (attribute_update_input.attribute_name_en is None):
        raise ValueError(f"{index}件目の属性は `attribute_id` または `attribute_name_en` のどちらか一方だけ指定してください。")

    has_update_field = any(
        [
            attribute_update_input.attribute_name_ja is not None,
            attribute_update_input.keybind is not None,
            attribute_update_input.read_only is not None,
            attribute_update_input.has_default_value,
        ]
    )
    if not has_update_field:
        raise ValueError(f"{index}件目の属性に更新するフィールドが指定されていません。")
    if attribute_update_input.read_only is not None and not isinstance(attribute_update_input.read_only, bool):
        raise ValueError(f"{index}件目の属性の `read_only` には真偽値を指定してください。")


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
        keybind=None if data.get("keybind") is None else validate_keybind_input(data["keybind"]),
        read_only=data.get("read_only"),
        default_value=data.get("default_value"),
        has_default_value="default_value" in data,
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
                "keybind": "string",
                "read_only": "boolean",
                "default_value": "string",
            },
        )
    except Exception as e:
        raise ValueError(f"`--attribute_csv` の読み込みに失敗しました。 :: {e}") from e

    unexpected_columns = set(df.columns) - ATTRIBUTE_JSON_KEYS
    if unexpected_columns:
        raise ValueError(f"`--attribute_csv` に指定できない列があります。 :: {sorted(unexpected_columns)}")

    result = []
    for index, row in enumerate(df.to_dict(orient="records"), start=1):
        default_value = row.get("default_value")
        attribute_update_input = AttributeUpdateInput(
            attribute_id=row.get("attribute_id"),
            attribute_name_en=row.get("attribute_name_en"),
            attribute_name_ja=row.get("attribute_name_ja"),
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

    duplicated_attribute_names = duplicated_set([attribute.attribute_name_en for attribute in attribute_update_inputs if attribute.attribute_name_en is not None])
    if duplicated_attribute_names:
        duplicated_text = ", ".join(sorted(duplicated_attribute_names))
        raise ValueError(f"入力された属性名(英語)に重複があります。 :: {duplicated_text}")


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
        if attribute_update_input.attribute_id is not None:
            target_attribute = annotation_specs_accessor.get_attribute(attribute_id=attribute_update_input.attribute_id)
        else:
            assert attribute_update_input.attribute_name_en is not None
            target_attribute = annotation_specs_accessor.get_attribute(attribute_name=attribute_update_input.attribute_name_en)

        target_attribute_id = target_attribute["additional_data_definition_id"]
        if target_attribute_id in resolved_attribute_ids:
            raise ValueError(f"同じ属性を複数回更新しようとしています。 :: attribute_id='{target_attribute_id}'")
        resolved_attribute_ids.add(target_attribute_id)
        result.append(ResolvedAttributeUpdateInput(target_attribute=target_attribute, attribute_update_input=attribute_update_input))

    return result


def update_attribute_name_ja(attribute: dict[str, Any], attribute_name_ja: str) -> None:
    """
    属性日本語名を更新する。
    """
    messages = attribute["name"]["messages"]
    for message in messages:
        if message["lang"] == "ja-JP":
            message["message"] = attribute_name_ja
            return

    messages.append({"lang": "ja-JP", "message": attribute_name_ja})


def create_comment_for_update_attributes(resolved_attribute_update_inputs: Sequence[ResolvedAttributeUpdateInput]) -> str:
    """
    属性更新時のデフォルトコメントを生成する。
    """
    attribute_names = [get_attribute_name_en(attribute_input.target_attribute) for attribute_input in resolved_attribute_update_inputs]
    return f"以下の属性情報を更新しました。\n対象属性: {', '.join(attribute_names)}"


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

        if attribute_update_input.attribute_name_ja is not None:
            update_attribute_name_ja(attribute, attribute_update_input.attribute_name_ja)
        if attribute_update_input.keybind is not None:
            attribute["keybind"] = keybind_to_api_keybind(copy.deepcopy(attribute_update_input.keybind))
        if attribute_update_input.read_only is not None:
            attribute["read_only"] = attribute_update_input.read_only
        if attribute_update_input.has_default_value:
            attribute["default"] = parse_default_value(attribute["type"], attribute_update_input.default_value)

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
            "attribute_name_en": "comment",
            "attribute_name_ja": "コメント",
            "keybind": {"alt": False, "code": "Digit1", "ctrl": True, "shift": False},
            "read_only": False,
            "default_value": "確認済み",
        },
        {"attribute_id": "f12a0b59-dfce-4241-bb87-4b2c0259fc6f", "read_only": True, "default_value": True},
    ]
    attribute_group = parser.add_mutually_exclusive_group(required=True)
    attribute_group.add_argument(
        "--attribute_json",
        type=str,
        help=(
            "更新する属性情報のJSON配列を指定します。 ``file://`` を先頭に付けるとJSON形式のファイルを指定できます。"
            " 各要素には ``attribute_id`` または ``attribute_name_en`` のどちらか一方が必要です。"
            " 任意で ``attribute_name_ja`` , ``keybind`` , ``read_only`` , ``default_value`` を指定できます。"
            f"\n(例) ``{json.dumps(sample_json, ensure_ascii=False)}``"
        ),
    )
    attribute_group.add_argument(
        "--attribute_csv",
        type=Path,
        help=(
            "更新する属性情報のCSVファイルを指定します。 CSVには ``attribute_id`` または ``attribute_name_en`` 列のどちらか一方が必要です。"
            " 任意で ``attribute_name_ja`` , ``keybind`` , ``read_only`` , ``default_value`` 列を指定できます。"
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
    description = "アノテーション仕様の既存属性に設定された日本語名、キーバインド、read_only、default_value を更新します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
