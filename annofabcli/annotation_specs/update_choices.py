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
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor, get_attribute_name_en, get_choice_name_en

import annofabcli.common.cli
from annofabcli.annotation_specs.add_labels import parse_keybind_in_csv
from annofabcli.common.annofab.annotation_specs import keybind_to_api_keybind, validate_keybind_input
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login, get_json_from_args
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import duplicated_set

logger = logging.getLogger(__name__)

CHOICE_JSON_KEYS = {
    "choice_id",
    "choice_name_en",
    "choice_name_ja",
    "keybind",
}
"""``--choice_json`` の各要素に指定できるキー。"""


@dataclass(frozen=True)
class ChoiceUpdateInput:
    """
    コマンドラインから受け取った選択肢1件分の更新情報。
    """

    choice_id: str | None = None
    """更新対象選択肢ID。"""

    choice_name_en: str | None = None
    """更新対象選択肢の英語名。"""

    choice_name_ja: str | None = None
    """更新後の選択肢日本語名。"""

    keybind: dict[str, Any] | None = None
    """更新後のkeybind。"""

    has_keybind: bool = False
    """``keybind`` が明示的に指定されたか。"""


@dataclass(frozen=True)
class ResolvedChoiceUpdateInput:
    """
    既存アノテーション仕様に対して解決済みの選択肢更新情報。
    """

    target_attribute: Mapping[str, Any]
    """更新対象選択肢が属する属性。"""

    target_choice: Mapping[str, Any]
    """更新対象選択肢。"""

    choice_update_input: ChoiceUpdateInput
    """更新情報。"""


def validate_choice_update_input(choice_update_input: ChoiceUpdateInput, *, index: int) -> None:
    """
    選択肢更新入力を検証する。
    """
    if (choice_update_input.choice_id is None) == (choice_update_input.choice_name_en is None):
        raise ValueError(f"{index}件目の選択肢は `choice_id` または `choice_name_en` のどちらか一方だけ指定してください。")

    if choice_update_input.choice_name_ja is None and not choice_update_input.has_keybind:
        raise ValueError(f"{index}件目の選択肢に更新するフィールドが指定されていません。")


def parse_choice_update_input_from_dict(data: dict[str, Any], *, index: int) -> ChoiceUpdateInput:
    """
    JSONオブジェクト1件を選択肢更新入力に変換する。
    """
    unexpected_keys = set(data) - CHOICE_JSON_KEYS
    if unexpected_keys:
        raise ValueError(f"{index}件目の選択肢に指定できないキーがあります。 :: {sorted(unexpected_keys)}")

    keybind = data.get("keybind")
    choice_update_input = ChoiceUpdateInput(
        choice_id=data.get("choice_id"),
        choice_name_en=data.get("choice_name_en"),
        choice_name_ja=data.get("choice_name_ja"),
        keybind=None if keybind is None else validate_keybind_input(keybind),
        has_keybind="keybind" in data,
    )
    validate_choice_update_input(choice_update_input, index=index)
    return choice_update_input


def read_choices_json(target: str) -> list[ChoiceUpdateInput]:
    """
    ``--choice_json`` で指定されたJSONから選択肢更新一覧を読み込む。
    """
    raw_data = get_json_from_args(target)
    if not isinstance(raw_data, list):
        raise TypeError("`--choice_json` には選択肢更新情報の配列を指定してください。")

    result = []
    for index, choice_data in enumerate(raw_data, start=1):
        if not isinstance(choice_data, dict):
            raise TypeError(f"{index}件目の選択肢がオブジェクト形式ではありません。")
        result.append(parse_choice_update_input_from_dict(choice_data, index=index))
    return result


def read_choices_csv(csv_path: Path) -> list[ChoiceUpdateInput]:
    """
    ``--choice_csv`` で指定されたCSVから選択肢更新一覧を読み込む。
    """
    try:
        df = pandas.read_csv(
            csv_path,
            dtype={
                "choice_id": "string",
                "choice_name_en": "string",
                "choice_name_ja": "string",
                "keybind": "string",
            },
        )
    except Exception as e:
        raise ValueError(f"`--choice_csv` の読み込みに失敗しました。 :: {e}") from e

    unexpected_columns = set(df.columns) - CHOICE_JSON_KEYS
    if unexpected_columns:
        raise ValueError(f"`--choice_csv` に指定できない列があります。 :: {sorted(unexpected_columns)}")

    result = []
    for index, row in enumerate(df.to_dict(orient="records"), start=1):
        keybind = parse_keybind_in_csv(row.get("keybind"), index=index)
        choice_update_input = ChoiceUpdateInput(
            choice_id=row.get("choice_id"),
            choice_name_en=row.get("choice_name_en"),
            choice_name_ja=row.get("choice_name_ja"),
            keybind=keybind,
            has_keybind=keybind is not None,
        )
        validate_choice_update_input(choice_update_input, index=index)
        result.append(choice_update_input)
    return result


def validate_choice_update_inputs(choice_update_inputs: Sequence[ChoiceUpdateInput]) -> None:
    """
    選択肢更新入力一覧を検証する。
    """
    if len(choice_update_inputs) == 0:
        raise ValueError("更新する選択肢を1件以上指定してください。")

    duplicated_choice_ids = duplicated_set([choice.choice_id for choice in choice_update_inputs if choice.choice_id is not None])
    if duplicated_choice_ids:
        duplicated_text = ", ".join(sorted(duplicated_choice_ids))
        raise ValueError(f"入力された選択肢に重複した `choice_id` があります。 :: {duplicated_text}")

    duplicated_choice_names = duplicated_set([choice.choice_name_en for choice in choice_update_inputs if choice.choice_name_en is not None])
    if duplicated_choice_names:
        duplicated_text = ", ".join(sorted(duplicated_choice_names))
        raise ValueError(f"入力された選択肢名(英語)に重複があります。 :: {duplicated_text}")


def get_target_choice(target_attribute: Mapping[str, Any], choice_update_input: ChoiceUpdateInput) -> Mapping[str, Any]:
    """
    選択肢更新入力から更新対象選択肢を取得する。
    """
    choices = target_attribute["choices"]
    if choice_update_input.choice_id is not None:
        matched_choices = [choice for choice in choices if choice["choice_id"] == choice_update_input.choice_id]
        if len(matched_choices) == 0:
            raise ValueError(f"選択肢情報が見つかりませんでした。 :: choice_id='{choice_update_input.choice_id}'")
        return matched_choices[0]

    assert choice_update_input.choice_name_en is not None
    matched_choices = [choice for choice in choices if get_choice_name_en(choice) == choice_update_input.choice_name_en]
    if len(matched_choices) == 0:
        raise ValueError(f"選択肢情報が見つかりませんでした。 :: choice_name_en='{choice_update_input.choice_name_en}'")
    if len(matched_choices) > 1:
        raise ValueError(f"選択肢情報が複数（{len(matched_choices)}件）見つかりました。 :: choice_name_en='{choice_update_input.choice_name_en}'")
    return matched_choices[0]


def resolve_choice_update_inputs(
    annotation_specs: dict[str, Any],
    *,
    attribute_id: str | None,
    attribute_name_en: str | None,
    choice_update_inputs: Sequence[ChoiceUpdateInput],
) -> list[ResolvedChoiceUpdateInput]:
    """
    選択肢更新入力一覧を既存アノテーション仕様に対して解決する。
    """
    validate_choice_update_inputs(choice_update_inputs)
    annotation_specs_accessor = AnnotationSpecsAccessor(annotation_specs)
    target_attribute = annotation_specs_accessor.get_attribute(attribute_id=attribute_id, attribute_name=attribute_name_en)
    if target_attribute["type"] not in ["choice", "select"]:
        raise ValueError(f"属性ID='{target_attribute['additional_data_definition_id']}' は選択肢系属性ではありません。")

    result = []
    resolved_choice_ids: set[str] = set()
    for choice_update_input in choice_update_inputs:
        target_choice = get_target_choice(target_attribute, choice_update_input)
        target_choice_id = target_choice["choice_id"]
        if target_choice_id in resolved_choice_ids:
            raise ValueError(f"同じ選択肢を複数回更新しようとしています。 :: choice_id='{target_choice_id}'")
        resolved_choice_ids.add(target_choice_id)
        result.append(
            ResolvedChoiceUpdateInput(
                target_attribute=target_attribute,
                target_choice=target_choice,
                choice_update_input=choice_update_input,
            )
        )

    return result


def update_choice_name_ja(choice: dict[str, Any], choice_name_ja: str) -> None:
    """
    選択肢日本語名を更新する。
    """
    messages = choice["name"]["messages"]
    for message in messages:
        if message["lang"] == "ja-JP":
            message["message"] = choice_name_ja
            return

    messages.append({"lang": "ja-JP", "message": choice_name_ja})


def create_comment_for_update_choices(resolved_choice_update_inputs: Sequence[ResolvedChoiceUpdateInput]) -> str:
    """
    選択肢更新時のデフォルトコメントを生成する。
    """
    target_attribute = resolved_choice_update_inputs[0].target_attribute
    choice_names = [get_choice_name_en(choice_input.target_choice) for choice_input in resolved_choice_update_inputs]
    return f"以下の選択肢情報を更新しました。\n対象属性: {get_attribute_name_en(target_attribute)}\n対象選択肢: {', '.join(choice_names)}"


def build_request_body_for_update_choices(
    annotation_specs: dict[str, Any],
    *,
    resolved_choice_update_inputs: Sequence[ResolvedChoiceUpdateInput],
    comment: str | None,
) -> dict[str, Any]:
    """
    複数選択肢更新用の request body を生成する。
    """
    request_body = copy.deepcopy(annotation_specs)
    target_attribute_id = resolved_choice_update_inputs[0].target_attribute["additional_data_definition_id"]
    choice_input_dict = {choice_input.target_choice["choice_id"]: choice_input.choice_update_input for choice_input in resolved_choice_update_inputs}

    for attribute in request_body["additionals"]:
        if attribute["additional_data_definition_id"] != target_attribute_id:
            continue
        for choice in attribute["choices"]:
            choice_update_input = choice_input_dict.get(choice["choice_id"])
            if choice_update_input is None:
                continue
            if choice_update_input.choice_name_ja is not None:
                update_choice_name_ja(choice, choice_update_input.choice_name_ja)
            if choice_update_input.has_keybind:
                choice["keybind"] = keybind_to_api_keybind(copy.deepcopy(choice_update_input.keybind))
        break

    if comment is None:
        comment = create_comment_for_update_choices(resolved_choice_update_inputs)
    request_body["comment"] = comment
    request_body["last_updated_datetime"] = annotation_specs["updated_datetime"]
    return request_body


class UpdateChoicesMain(CommandLineWithConfirm):
    """
    既存選択肢の情報を更新する本体処理。
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

    def update_choices(
        self,
        *,
        attribute_id: str | None,
        attribute_name_en: str | None,
        choice_update_inputs: Sequence[ChoiceUpdateInput],
        comment: str | None = None,
    ) -> bool:
        """
        複数選択肢の情報を更新して、アノテーション仕様を更新する。
        """
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        resolved_choice_update_inputs = resolve_choice_update_inputs(
            old_annotation_specs,
            attribute_id=attribute_id,
            attribute_name_en=attribute_name_en,
            choice_update_inputs=choice_update_inputs,
        )
        target_attribute = resolved_choice_update_inputs[0].target_attribute
        choice_names = [get_choice_name_en(choice_input.target_choice) for choice_input in resolved_choice_update_inputs]

        confirm_message = f"属性 '{get_attribute_name_en(target_attribute)}' の選択肢 {len(resolved_choice_update_inputs)} 件を更新します。対象選択肢={choice_names}。よろしいですか？"
        if not self.confirm_processing(confirm_message):
            return False

        request_body = build_request_body_for_update_choices(
            old_annotation_specs,
            resolved_choice_update_inputs=resolved_choice_update_inputs,
            comment=comment,
        )
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"属性 '{get_attribute_name_en(target_attribute)}' の選択肢 {len(resolved_choice_update_inputs)} 件を更新しました。")
        return True


class UpdateChoices(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs update_choices: error:"

    def main(self) -> None:
        """
        コマンドライン引数を解釈し、複数選択肢更新処理を実行する。
        """
        args = self.args
        if args.choice_json is not None:
            choice_update_inputs = read_choices_json(args.choice_json)
        elif args.choice_csv is not None:
            if not args.choice_csv.exists():
                raise ValueError(f"`--choice_csv` に指定されたファイルが存在しません。 :: {args.choice_csv}")
            choice_update_inputs = read_choices_csv(args.choice_csv)
        else:
            raise ValueError("`--choice_json` , `--choice_csv` のいずれかを指定してください。")

        obj = UpdateChoicesMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.update_choices(
            attribute_id=args.attribute_id,
            attribute_name_en=args.attribute_name_en,
            choice_update_inputs=choice_update_inputs,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    ``update_choices`` サブコマンドの引数を定義する。
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    attribute_group = parser.add_mutually_exclusive_group(required=True)
    attribute_group.add_argument("--attribute_id", type=str, help="選択肢を更新する対象属性の属性ID。")
    attribute_group.add_argument("--attribute_name_en", type=str, help="選択肢を更新する対象属性の英語名。")

    sample_json = [
        {
            "choice_name_en": "large",
            "choice_name_ja": "大",
            "keybind": {"alt": False, "code": "Digit1", "ctrl": True, "shift": False},
        },
        {"choice_id": "74691a87-7962-4fa9-ba52-7cc466ecd982", "keybind": None},
    ]
    choice_group = parser.add_mutually_exclusive_group(required=True)
    choice_group.add_argument(
        "--choice_json",
        type=str,
        help=(
            "更新する選択肢情報のJSON配列を指定します。 ``file://`` を先頭に付けるとJSON形式のファイルを指定できます。"
            " 各要素には ``choice_id`` または ``choice_name_en`` のどちらか一方が必要です。"
            " 任意で ``choice_name_ja`` , ``keybind`` を指定できます。 ``keybind`` に ``null`` を指定するとショートカットキーを解除します。"
            f"\n(例) ``{json.dumps(sample_json, ensure_ascii=False)}``"
        ),
    )
    choice_group.add_argument(
        "--choice_csv",
        type=Path,
        help=(
            "更新する選択肢情報のCSVファイルを指定します。 CSVには ``choice_id`` または ``choice_name_en`` 列のどちらか一方が必要です。"
            " 任意で ``choice_name_ja`` , ``keybind`` 列を指定できます。"
            " ``keybind`` 列にはJSONオブジェクト文字列を指定してください。空欄の場合はショートカットキーを変更しません。"
        ),
    )
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``update_choices`` コマンドのエントリポイント。
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateChoices(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs update_choices`` 用のparserを生成する。
    """
    subcommand_name = "update_choices"
    subcommand_help = "アノテーション仕様の既存選択肢情報を更新します。"
    description = "アノテーション仕様の既存選択肢に設定された日本語名、ショートカットキーを更新します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
