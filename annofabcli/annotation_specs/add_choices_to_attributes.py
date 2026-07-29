from __future__ import annotations

import argparse
import copy
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import annofabapi
from annofabapi.util.annotation_specs import get_attribute_name_en, get_english_message

import annofabcli.common.cli
from annofabcli.annotation_specs.add_choice_attribute import ChoiceAttributeInput, parse_choice_input_from_dict
from annofabcli.annotation_specs.add_choices_to_attribute import ResolvedAddedChoicesInput, resolve_added_choices_input
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login, get_json_from_args
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import duplicated_set

logger = logging.getLogger(__name__)

ATTRIBUTE_CHOICES_JSON_KEYS = {
    "attribute_id",
    "choices",
}
"""``--attribute_json`` の各要素に指定できるキー。"""


@dataclass(frozen=True)
class AttributeChoicesInput:
    """
    コマンドラインから受け取った1属性分の選択肢追加情報。
    """

    attribute_id: str | None
    """追加先属性ID。"""

    choices: list[ChoiceAttributeInput]
    """追加する選択肢一覧。"""


def validate_attribute_choices_input(attribute_choices_input: AttributeChoicesInput, *, index: int) -> None:
    """
    1属性分の選択肢追加入力を検証する。
    """
    if attribute_choices_input.attribute_id is None:
        raise ValueError(f"{index}件目の属性に `attribute_id` が指定されていません。")
    if len(attribute_choices_input.choices) == 0:
        raise ValueError(f"{index}件目の属性の `choices` には選択肢を1件以上指定してください。")


def parse_choices_from_dict(data: dict[str, Any], *, index: int) -> list[ChoiceAttributeInput]:
    """
    属性追加JSON内の ``choices`` を選択肢入力に変換する。
    """
    choices = data.get("choices")
    if choices is None:
        raise ValueError(f"{index}件目の属性に `choices` が指定されていません。")
    if not isinstance(choices, list):
        raise TypeError(f"{index}件目の属性の `choices` には選択肢情報の配列を指定してください。")

    result = []
    for choice_index, choice in enumerate(choices, start=1):
        if not isinstance(choice, dict):
            raise TypeError(f"{index}件目の属性の `choices` の {choice_index} 件目がオブジェクト形式ではありません。")
        result.append(parse_choice_input_from_dict(choice, index=choice_index))
    return result


def parse_attribute_choices_input_from_dict(data: dict[str, Any], *, index: int) -> AttributeChoicesInput:
    """
    JSONオブジェクト1件を選択肢追加入力に変換する。
    """
    unexpected_keys = set(data) - ATTRIBUTE_CHOICES_JSON_KEYS
    if unexpected_keys:
        raise ValueError(f"{index}件目の属性に指定できないキーがあります。 :: {sorted(unexpected_keys)}")

    attribute_choices_input = AttributeChoicesInput(
        attribute_id=data.get("attribute_id"),
        choices=parse_choices_from_dict(data, index=index),
    )
    validate_attribute_choices_input(attribute_choices_input, index=index)
    return attribute_choices_input


def read_attributes_json(target: str) -> list[AttributeChoicesInput]:
    """
    ``--attribute_json`` で指定されたJSONから選択肢追加一覧を読み込む。
    """
    raw_data = get_json_from_args(target)
    if not isinstance(raw_data, list):
        raise TypeError("`--attribute_json` には選択肢追加情報の配列を指定してください。")

    result = []
    for index, attribute_data in enumerate(raw_data, start=1):
        if not isinstance(attribute_data, dict):
            raise TypeError(f"{index}件目の属性がオブジェクト形式ではありません。")
        result.append(parse_attribute_choices_input_from_dict(attribute_data, index=index))
    return result


def validate_attribute_choices_inputs(attribute_choices_inputs: Sequence[AttributeChoicesInput]) -> None:
    """
    選択肢追加入力一覧を検証する。
    """
    if len(attribute_choices_inputs) == 0:
        raise ValueError("選択肢を追加する属性を1件以上指定してください。")

    duplicated_attribute_ids = duplicated_set([attribute.attribute_id for attribute in attribute_choices_inputs if attribute.attribute_id is not None])
    if duplicated_attribute_ids:
        duplicated_text = ", ".join(sorted(duplicated_attribute_ids))
        raise ValueError(f"入力された属性に重複した `attribute_id` があります。 :: {duplicated_text}")


def resolve_attribute_choices_inputs(
    annotation_specs: dict[str, Any],
    *,
    attribute_choices_inputs: Sequence[AttributeChoicesInput],
) -> list[ResolvedAddedChoicesInput]:
    """
    複数属性への追加選択肢を既存アノテーション仕様に対して解決する。
    """
    validate_attribute_choices_inputs(attribute_choices_inputs)

    return [
        resolve_added_choices_input(
            annotation_specs,
            attribute_id=attribute_choices_input.attribute_id,
            attribute_name_en=None,
            choice_inputs=attribute_choices_input.choices,
        )
        for attribute_choices_input in attribute_choices_inputs
    ]


def create_comment_for_add_choices_to_attributes(resolved_added_choices_inputs: Sequence[ResolvedAddedChoicesInput]) -> str:
    """
    複数属性への選択肢追加時のデフォルトコメントを生成する。
    """
    lines = ["以下の選択肢を属性に追加しました。"]
    for resolved_input in resolved_added_choices_inputs:
        attribute_name_en = get_attribute_name_en(resolved_input.target_attribute)
        choice_name_ens = [get_english_message(choice["name"]) for choice in resolved_input.added_choices]
        lines.extend(
            [
                f"属性名(英語): {attribute_name_en}",
                f"追加した選択肢: {', '.join(choice_name_ens)}",
            ]
        )
    return "\n".join(lines)


def build_request_body_for_add_choices_to_attributes(
    annotation_specs: dict[str, Any],
    *,
    resolved_added_choices_inputs: Sequence[ResolvedAddedChoicesInput],
    comment: str | None,
) -> dict[str, Any]:
    """
    複数属性への選択肢追加用の request body を生成する。
    """
    request_body = copy.deepcopy(annotation_specs)
    added_choices_by_attribute_id = {resolved_input.target_attribute["additional_data_definition_id"]: resolved_input.added_choices for resolved_input in resolved_added_choices_inputs}

    for attribute in request_body["additionals"]:
        added_choices = added_choices_by_attribute_id.get(attribute["additional_data_definition_id"])
        if added_choices is None:
            continue
        attribute["choices"].extend(added_choices)

    if comment is None:
        comment = create_comment_for_add_choices_to_attributes(resolved_added_choices_inputs)
    request_body["comment"] = comment
    request_body["last_updated_datetime"] = annotation_specs["updated_datetime"]
    return request_body


class AddChoicesToAttributesMain(CommandLineWithConfirm):
    """
    既存の複数選択肢系属性へ選択肢を追加する本体処理。
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

    def add_choices_to_attributes(
        self,
        *,
        attribute_choices_inputs: Sequence[AttributeChoicesInput],
        comment: str | None = None,
    ) -> bool:
        """
        既存の複数選択肢系属性へ選択肢を追加して、アノテーション仕様を更新する。
        """
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        resolved_added_choices_inputs = resolve_attribute_choices_inputs(old_annotation_specs, attribute_choices_inputs=attribute_choices_inputs)

        attribute_names = [get_attribute_name_en(resolved_input.target_attribute) for resolved_input in resolved_added_choices_inputs]
        choice_count = sum(len(resolved_input.added_choices) for resolved_input in resolved_added_choices_inputs)
        confirm_message = f"{len(resolved_added_choices_inputs)} 件の属性に {choice_count} 件の選択肢を追加します。対象属性={attribute_names}。よろしいですか？"
        if not self.confirm_processing(confirm_message):
            return False

        request_body = build_request_body_for_add_choices_to_attributes(
            old_annotation_specs,
            resolved_added_choices_inputs=resolved_added_choices_inputs,
            comment=comment,
        )
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"{len(resolved_added_choices_inputs)} 件の属性に {choice_count} 件の選択肢を追加しました。")
        return True


class AddChoicesToAttributes(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs add_choices_to_attributes: error:"

    def main(self) -> None:
        """
        コマンドライン引数を解釈し、複数属性への選択肢追加処理を実行する。
        """
        args = self.args
        attribute_choices_inputs = read_attributes_json(args.attribute_json)

        obj = AddChoicesToAttributesMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.add_choices_to_attributes(
            attribute_choices_inputs=attribute_choices_inputs,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    ``add_choices_to_attributes`` サブコマンドの引数を定義する。
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    sample_json = [
        {
            "attribute_id": "71620647-98cf-48ad-b43b-4af425a24f32",
            "choices": [
                {"choice_id": "xlarge", "choice_name_en": "xlarge", "choice_name_ja": "特大", "choice_name_vi": "rất lớn"},
                {"choice_id": "tiny", "choice_name_en": "tiny", "choice_name_ja": "極小"},
            ],
        },
        {
            "attribute_id": "e6d5bf13-9bf5-4c31-8a81-2d8a772c9468",
            "choices": [
                {"choice_name_en": "rainy", "choice_name_ja": "雨", "keybind": {"alt": False, "code": "Digit1", "ctrl": True, "shift": False}},
            ],
        },
    ]
    parser.add_argument(
        "--attribute_json",
        type=str,
        required=True,
        help=(
            "選択肢を追加する属性情報のJSON配列を指定します。 ``file://`` を先頭に付けるとJSON形式のファイルを指定できます。"
            " 各要素には追加先を示す ``attribute_id`` と、追加する選択肢情報の ``choices`` が必要です。"
            " ``choices`` では任意で ``choice_id`` , ``choice_name_ja`` , ``choice_name_vi`` , ``keybind`` を指定できます。 ``is_default`` は無視されます。"
            f"\n(例) ``{json.dumps(sample_json, ensure_ascii=False)}``"
        ),
    )
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``add_choices_to_attributes`` コマンドのエントリポイント。
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    AddChoicesToAttributes(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs add_choices_to_attributes`` 用のparserを生成する。
    """
    subcommand_name = "add_choices_to_attributes"
    subcommand_help = "既存の複数選択肢系属性に選択肢を追加します。"
    description = "既存の複数選択肢系属性（ラジオボタン/ドロップダウン）に、選択肢を追加します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
