from __future__ import annotations

import argparse
import copy
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import annofabapi
import pandas
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor, get_attribute_name_en, get_english_message

import annofabcli.common.cli
from annofabcli.annotation_specs.add_choice_attribute import ChoiceAttributeInput, build_choices, parse_keybind_in_csv, read_choices_json
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedAddedChoicesInput:
    """
    既存属性への選択肢追加を解決した結果。
    """

    target_attribute: dict[str, Any]
    """選択肢を追加する対象属性。"""

    added_choices: list[dict[str, Any]]
    """追加する選択肢一覧。"""


def create_comment_from_attribute(attribute_name_en: str, choice_name_ens: list[str]) -> str:
    """
    既存の選択肢系属性に選択肢を追加したときのデフォルトコメントを生成する。

    Args:
        attribute_name_en: 属性の英語名
        choice_name_ens: 追加する選択肢の英語名一覧

    Returns:
        アノテーション仕様変更コメント
    """
    choices_text = ", ".join(choice_name_ens)
    return f"以下の選択肢を属性に追加しました。\n属性名(英語): {attribute_name_en}\n追加した選択肢: {choices_text}"


def read_choices_csv(csv_path: Path) -> list[ChoiceAttributeInput]:
    """
    ``--choice_csv`` で指定されたCSVから選択肢一覧を読み込む。

    ``add_choices_to_attribute`` ではデフォルト値を変更しないため、 ``is_default`` 列は読み込まない。

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
                "keybind": "string",
            },
        )
    except Exception as e:
        raise ValueError(f"`--choice_csv` の読み込みに失敗しました。 :: {e}") from e

    required_columns = {"choice_name_en"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"`--choice_csv` に不足している必須列があります。 :: {sorted(missing_columns)}")

    return [
        ChoiceAttributeInput(
            choice_name_en=row["choice_name_en"],
            choice_name_ja=row.get("choice_name_ja"),
            choice_id=row.get("choice_id"),
            is_default=False,
            keybind=parse_keybind_in_csv(row.get("keybind")),
        )
        for row in df.to_dict(orient="records")
    ]


def validate_added_choices(
    target_attribute: Mapping[str, Any],
    *,
    added_choices: Sequence[Mapping[str, Any]],
) -> None:
    """
    追加する選択肢が既存の選択肢と衝突しないか検証する。

    Args:
        target_attribute: 追加先の属性
        added_choices: 追加予定の選択肢一覧

    Raises:
        ValueError: 選択肢ID・選択肢名が既存の属性情報と衝突する場合
    """
    existing_choices = target_attribute["choices"]
    existing_choice_ids = {choice["choice_id"] for choice in existing_choices}
    duplicated_choice_ids = existing_choice_ids & {choice["choice_id"] for choice in added_choices}
    if duplicated_choice_ids:
        duplicated_text = ", ".join(sorted(duplicated_choice_ids))
        raise ValueError(f"追加先の属性に既に存在する `choice_id` が指定されています。 :: {duplicated_text}")

    existing_choice_name_ens = {get_english_message(choice["name"]) for choice in existing_choices}
    duplicated_choice_name_ens = existing_choice_name_ens & {get_english_message(choice["name"]) for choice in added_choices}
    if duplicated_choice_name_ens:
        duplicated_text = ", ".join(sorted(duplicated_choice_name_ens))
        raise ValueError(f"追加先の属性に既に存在する `choice_name_en` が指定されています。 :: {duplicated_text}")


def ignore_default_choice_inputs(choice_inputs: Sequence[ChoiceAttributeInput]) -> list[ChoiceAttributeInput]:
    """
    選択肢追加コマンドではデフォルト値を変更しないため、is_defaultを無視する。

    Args:
        choice_inputs: コマンドラインから受け取った選択肢一覧

    Returns:
        ``is_default`` をFalseにした選択肢一覧
    """
    return [replace(choice_input, is_default=False) for choice_input in choice_inputs]


def resolve_added_choices_input(
    annotation_specs: dict[str, Any],
    *,
    attribute_id: str | None,
    attribute_name_en: str | None,
    choice_inputs: Sequence[ChoiceAttributeInput],
) -> ResolvedAddedChoicesInput:
    """
    既存属性への追加選択肢を既存アノテーション仕様に対して解決する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        attribute_id: 追加先属性ID
        attribute_name_en: 追加先属性英語名
        choice_inputs: 追加する選択肢一覧

    Returns:
        解決済み追加選択肢入力
    """
    added_choices, _ = build_choices(ignore_default_choice_inputs(choice_inputs), min_count=1)

    annotation_specs_accessor = AnnotationSpecsAccessor(annotation_specs)
    target_attribute = annotation_specs_accessor.get_attribute(
        attribute_id=attribute_id,
        attribute_name=attribute_name_en,
    )
    if target_attribute["type"] not in ["choice", "select"]:
        raise ValueError(f"属性ID='{target_attribute['additional_data_definition_id']}' は選択肢系属性ではありません。")

    validate_added_choices(
        target_attribute,
        added_choices=added_choices,
    )
    return ResolvedAddedChoicesInput(target_attribute=dict(target_attribute), added_choices=added_choices)


def build_request_body_for_add_choices_to_attribute(
    annotation_specs: dict[str, Any],
    *,
    resolved_added_choices_input: ResolvedAddedChoicesInput,
    comment: str | None,
) -> dict[str, Any]:
    """
    既存属性への選択肢追加用の request body を生成する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        resolved_added_choices_input: 解決済み追加選択肢入力
        comment: 変更コメント

    Returns:
        Annofab API に渡す request body
    """
    request_body = copy.deepcopy(annotation_specs)
    resolved_attribute_id = resolved_added_choices_input.target_attribute["additional_data_definition_id"]
    resolved_attribute_name_en = get_attribute_name_en(resolved_added_choices_input.target_attribute)
    added_choice_name_ens = [get_english_message(choice["name"]) for choice in resolved_added_choices_input.added_choices]

    for attribute in request_body["additionals"]:
        if attribute["additional_data_definition_id"] != resolved_attribute_id:
            continue
        attribute["choices"].extend(resolved_added_choices_input.added_choices)
        break

    if comment is None:
        comment = create_comment_from_attribute(resolved_attribute_name_en, added_choice_name_ens)
    request_body["comment"] = comment
    request_body["last_updated_datetime"] = annotation_specs["updated_datetime"]
    return request_body


class AddChoicesToAttributeMain(CommandLineWithConfirm):
    """
    既存の選択肢系属性へ選択肢を追加する本体処理。
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

    def add_choices_to_attribute(
        self,
        *,
        attribute_id: str | None,
        attribute_name_en: str | None,
        choice_json: str | None,
        choice_csv: Path | None,
        comment: str | None = None,
    ) -> bool:
        """
        既存の選択肢系属性へ選択肢を追加して、アノテーション仕様を更新する。

        Args:
            attribute_id: 追加先属性ID
            attribute_name_en: 追加先属性英語名
            choice_json: 追加する選択肢JSON
            choice_csv: 追加する選択肢CSV
            comment: 変更コメント

        Returns:
            追加を実行した場合はTrue、確認で中断した場合はFalse

        Raises:
            ValueError: 入力値や既存アノテーション仕様との整合性が不正な場合
        """
        if choice_json is not None:
            choice_inputs = read_choices_json(choice_json)
        elif choice_csv is not None:
            if not choice_csv.exists():
                raise ValueError(f"`--choice_csv` に指定されたファイルが存在しません。 :: {choice_csv}")
            choice_inputs = read_choices_csv(choice_csv)
        else:
            raise ValueError("`--choice_json` または `--choice_csv` のいずれかを指定してください。")

        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        resolved_added_choices_input = resolve_added_choices_input(
            old_annotation_specs,
            attribute_id=attribute_id,
            attribute_name_en=attribute_name_en,
            choice_inputs=choice_inputs,
        )

        resolved_attribute_id = resolved_added_choices_input.target_attribute["additional_data_definition_id"]
        resolved_attribute_name_en = get_attribute_name_en(resolved_added_choices_input.target_attribute)
        added_choice_name_ens = [get_english_message(choice["name"]) for choice in resolved_added_choices_input.added_choices]
        confirm_message = (
            f"属性名(英語)='{resolved_attribute_name_en}', 属性ID='{resolved_attribute_id}' に "
            f"{len(resolved_added_choices_input.added_choices)} 件の選択肢 {added_choice_name_ens} を追加します。よろしいですか？"
        )
        if not self.confirm_processing(confirm_message):
            return False

        request_body = build_request_body_for_add_choices_to_attribute(
            old_annotation_specs,
            resolved_added_choices_input=resolved_added_choices_input,
            comment=comment,
        )
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"属性名(英語)='{resolved_attribute_name_en}', 属性ID='{resolved_attribute_id}' に {len(resolved_added_choices_input.added_choices)} 件の選択肢を追加しました。")
        return True


class AddChoicesToAttribute(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs add_choices_to_attribute: error:"

    def main(self) -> None:
        """
        コマンドライン引数を解釈し、既存属性への選択肢追加処理を実行する。
        """
        args = self.args

        obj = AddChoicesToAttributeMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.add_choices_to_attribute(
            attribute_id=args.attribute_id,
            attribute_name_en=args.attribute_name_en,
            choice_json=args.choice_json,
            choice_csv=args.choice_csv,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    ``add_choices_to_attribute`` サブコマンドの引数を定義する。

    Args:
        parser: 引数を追加するArgumentParser
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    attribute_group = parser.add_mutually_exclusive_group(required=True)
    attribute_group.add_argument("--attribute_id", type=str, help="選択肢を追加する対象属性の属性ID。")
    attribute_group.add_argument("--attribute_name_en", type=str, help="選択肢を追加する対象属性の英語名。")

    sample_json = [
        {
            "choice_id": "xlarge",
            "choice_name_en": "xlarge",
            "choice_name_ja": "特大",
            "keybind": {"alt": False, "code": "Digit1", "ctrl": True, "shift": False},
        },
        {"choice_id": "tiny", "choice_name_en": "tiny", "choice_name_ja": "極小"},
    ]
    choice_group = parser.add_mutually_exclusive_group(required=True)
    choice_group.add_argument(
        "--choice_json",
        type=str,
        help=(
            "追加する選択肢情報のJSON配列を指定します。 ``file://`` を先頭に付けるとJSON形式のファイルを指定できます。"
            " 任意で ``keybind`` を指定できます。 ``keybind`` にはJSONオブジェクトを指定してください。"
            f"\n(例) ``{json.dumps(sample_json, ensure_ascii=False)}``"
        ),
    )
    choice_group.add_argument(
        "--choice_csv",
        type=Path,
        help=(
            "追加する選択肢情報のCSVファイルを指定します。 "
            "CSVには ``choice_name_en`` 列が必要です。 "
            "``choice_id`` と ``choice_name_en`` はユニークになるように指定してください。 "
            "任意で ``choice_id`` , ``choice_name_ja`` , ``keybind`` 列を指定できます。"
            " ``keybind`` 列にはJSONオブジェクト文字列を指定してください。 ``is_default`` 列が存在する場合は無視されます。"
        ),
    )

    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``add_choices_to_attribute`` コマンドのエントリポイント。

    Args:
        args: コマンドライン引数
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    AddChoicesToAttribute(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs add_choices_to_attribute`` 用のparserを生成する。

    Args:
        subparsers: 親parserのsubparsers

    Returns:
        生成したArgumentParser
    """
    subcommand_name = "add_choices_to_attribute"
    subcommand_help = "既存の選択肢系属性に選択肢を追加します。"
    description = "既存の選択肢系属性（ラジオボタン/ドロップダウン）に、選択肢を追加します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
