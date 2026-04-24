from __future__ import annotations

import argparse
import copy
import json
import logging
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import annofabapi
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor

import annofabcli.common.cli
from annofabcli.annotation_specs.add_choice_attribute import (
    ChoiceAttributeInput,
    build_choices,
    create_name,
    get_label_name_en,
    get_target_labels,
    read_choices_csv,
    read_choices_json,
    validate_new_attribute,
)
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)

CHOICE_ATTRIBUTE_TYPES = {"choice", "select"}
ATTRIBUTE_TYPES = ["comment", "choice", "flag", "integer", "link", "select", "text", "tracking"]


def get_default_value(attribute_type: str) -> str | bool | None:
    """
    属性種類ごとのデフォルト値を返す。

    Args:
        attribute_type: 属性の種類

    Returns:
        属性のデフォルト値
    """
    if attribute_type == "flag":
        return False
    return ""


def get_choice_inputs_from_args(
    *,
    attribute_type: str,
    choices_json: str | None,
    choices_csv: Path | None,
) -> list[ChoiceAttributeInput]:
    """
    属性種類に応じて選択肢入力を読み込む。

    Args:
        attribute_type: 属性の種類
        choices_json: ``--choices_json`` の値
        choices_csv: ``--choices_csv`` の値

    Returns:
        選択肢入力の一覧。選択肢系属性以外では空配列

    Raises:
        ValueError: 属性種類と選択肢関連引数の組み合わせが不正な場合
    """
    if attribute_type in CHOICE_ATTRIBUTE_TYPES:
        if choices_json is None and choices_csv is None:
            raise ValueError("属性種類が `choice` または `select` の場合は、`--choices_json` または `--choices_csv` のいずれかを指定してください。")
        if choices_json is not None and choices_csv is not None:
            raise ValueError("`--choices_json` と `--choices_csv` は同時に指定できません。")

        if choices_json is not None:
            return read_choices_json(choices_json)

        assert choices_csv is not None
        if not choices_csv.exists():
            raise ValueError(f"`--choices_csv` に指定されたファイルが存在しません。 :: {choices_csv}")
        return read_choices_csv(choices_csv)

    if choices_json is not None or choices_csv is not None:
        raise ValueError("属性種類が `choice` または `select` 以外の場合、`--choices_json` と `--choices_csv` は指定できません。")

    return []


def create_comment_from_attribute(attribute_name_en: str, attribute_type: str, label_names: Sequence[str]) -> str:
    """
    属性追加時のデフォルトコメントを生成する。

    Args:
        attribute_name_en: 属性の英語名
        attribute_type: 属性の種類
        label_names: 追加先ラベルの英語名一覧

    Returns:
        アノテーション仕様変更コメント
    """
    labels_text = ", ".join(label_names)
    return f"以下の属性を追加しました。\n属性名(英語): {attribute_name_en}\n属性種類: {attribute_type}\n対象ラベル: {labels_text}"


def create_attribute(
    *,
    attribute_type: str,
    attribute_name_en: str,
    attribute_name_ja: str | None,
    attribute_id: str | None,
    choice_inputs: Sequence[ChoiceAttributeInput],
) -> dict[str, Any]:
    """
    属性1件分のAnnofab API向けオブジェクトを生成する。

    Args:
        attribute_type: 属性型
        attribute_name_en: 属性英語名
        attribute_name_ja: 属性日本語名
        attribute_id: 属性ID。未指定ならUUIDv4を自動生成
        choice_inputs: 選択肢入力一覧

    Returns:
        Annofab API向けの属性オブジェクト
    """
    default_value: str | bool | None
    if attribute_type in CHOICE_ATTRIBUTE_TYPES:
        choices, default_value = build_choices(choice_inputs)
    else:
        choices = []
        default_value = get_default_value(attribute_type)

    return {
        "additional_data_definition_id": attribute_id if attribute_id is not None else str(uuid.uuid4()),
        "name": create_name(attribute_name_en, attribute_name_ja),
        "type": attribute_type,
        "default": default_value,
        "choices": choices,
    }


class AddAttributeMain(CommandLineWithConfirm):
    """
    属性をアノテーション仕様へ追加する本体処理。
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

    def add_attribute(
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
        属性を追加し、指定ラベルへ紐付けてアノテーション仕様を更新する。

        Args:
            attribute_type: 属性型
            attribute_name_en: 属性英語名
            attribute_name_ja: 属性日本語名
            attribute_id: 属性ID。未指定ならUUIDv4を自動生成
            choice_inputs: 選択肢入力一覧
            label_ids: 追加先ラベルID一覧
            label_name_ens: 追加先ラベル英語名一覧
            comment: 変更コメント

        Returns:
            追加を実行した場合はTrue、確認で中断した場合はFalse
        """
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        annotation_specs_accessor = AnnotationSpecsAccessor(old_annotation_specs)
        additionals = old_annotation_specs["additionals"]
        target_labels = get_target_labels(annotation_specs_accessor, label_ids=label_ids, label_name_ens=label_name_ens)
        new_attribute = create_attribute(
            attribute_type=attribute_type,
            attribute_name_en=attribute_name_en,
            attribute_name_ja=attribute_name_ja,
            attribute_id=attribute_id,
            choice_inputs=choice_inputs,
        )

        duplicated_name_attribute_ids = validate_new_attribute(
            additionals,
            attribute_id=new_attribute["additional_data_definition_id"],
            attribute_name_en=attribute_name_en,
        )

        label_names = [get_label_name_en(label) for label in target_labels]
        confirm_message = f"属性名(英語)='{attribute_name_en}', 属性種類='{attribute_type}', 対象ラベル={label_names} を追加します。よろしいですか？"
        if attribute_type in CHOICE_ATTRIBUTE_TYPES:
            confirm_message = f"属性名(英語)='{attribute_name_en}', 属性種類='{attribute_type}', 選択肢数={len(new_attribute['choices'])}, 対象ラベル={label_names} を追加します。よろしいですか？"
        if duplicated_name_attribute_ids:
            duplicated_text = ", ".join(duplicated_name_attribute_ids)
            confirm_message = f"{confirm_message} なお、同じ属性名(英語)を持つ既存属性があります。既存の属性ID: {duplicated_text}"
        if not self.confirm_processing(confirm_message):
            return False

        request_body = copy.deepcopy(old_annotation_specs)
        request_body["additionals"].append(new_attribute)
        target_label_id_set = {label["label_id"] for label in target_labels}
        for label in request_body["labels"]:
            if label["label_id"] in target_label_id_set:
                label["additional_data_definitions"].append(new_attribute["additional_data_definition_id"])

        if comment is None:
            comment = create_comment_from_attribute(attribute_name_en, attribute_type, label_names)
        request_body["comment"] = comment
        request_body["last_updated_datetime"] = old_annotation_specs["updated_datetime"]
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"属性名(英語)='{attribute_name_en}', 属性ID='{new_attribute['additional_data_definition_id']}' の属性を追加しました。")
        return True


class AddAttribute(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs add_attribute: error:"

    def main(self) -> None:
        """
        コマンドライン引数を解釈し、属性追加処理を実行する。
        """
        args = self.args

        choice_inputs = get_choice_inputs_from_args(
            attribute_type=args.attribute_type,
            choices_json=args.choices_json,
            choices_csv=args.choices_csv,
        )
        label_ids = get_list_from_args(args.label_id)
        label_name_ens = get_list_from_args(args.label_name_en)

        obj = AddAttributeMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.add_attribute(
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
    ``add_attribute`` サブコマンドの引数を定義する。

    Args:
        parser: 引数を追加するArgumentParser
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    parser.add_argument(
        "--attribute_type",
        type=str,
        required=True,
        choices=ATTRIBUTE_TYPES,
        help=(
            "追加する属性の種類。 "
            "``flag`` はチェックボックス、``integer`` は整数、``text`` は自由記述（1行）、"
            "``comment`` は自由記述（複数行）、``choice`` はラジオボタン、``select`` はドロップダウン、"
            "``tracking`` はトラッキングID、``link`` はアノテーションリンクです。"
        ),
    )
    parser.add_argument("--attribute_name_en", type=str, required=True, help="追加する属性の英語名。")
    parser.add_argument("--attribute_id", type=str, help="追加する属性の属性ID。未指定の場合はUUIDv4を自動生成します。")
    parser.add_argument("--attribute_name_ja", type=str, help="追加する属性の日本語名。")

    sample_json = [
        {"choice_id": "front", "choice_name_en": "front", "choice_name_ja": "前", "is_default": True},
        {"choice_name_en": "rear"},
    ]
    choice_group = parser.add_mutually_exclusive_group()
    choice_group.add_argument(
        "--choices_json",
        type=str,
        help=(
            "属性種類が ``choice`` または ``select`` の場合に、追加する選択肢情報のJSON配列を指定します。 "
            "``file://`` を先頭に付けるとJSON形式のファイルを指定できます。\n"
            f"(例) ``{json.dumps(sample_json, ensure_ascii=False)}``"
        ),
    )
    choice_group.add_argument(
        "--choices_csv",
        type=Path,
        help=(
            "属性種類が ``choice`` または ``select`` の場合に、追加する選択肢情報のCSVファイルを指定します。 "
            "CSVには ``choice_name_en`` 列が必要です。 任意で ``choice_id`` , ``choice_name_ja`` , "
            "``is_default`` 列を指定できます。"
        ),
    )

    label_group = parser.add_mutually_exclusive_group(required=True)
    label_group.add_argument(
        "--label_name_en",
        type=str,
        nargs="+",
        help="属性を追加する対象ラベルの英語名。複数指定できます。 ``file://`` を先頭に付けると一覧ファイルを指定できます。",
    )
    label_group.add_argument(
        "--label_id",
        type=str,
        nargs="+",
        help="属性を追加する対象ラベルのlabel_id。複数指定できます。 ``file://`` を先頭に付けると一覧ファイルを指定できます。",
    )
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更時に指定できるコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``add_attribute`` コマンドのエントリポイント。

    Args:
        args: コマンドライン引数
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    AddAttribute(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs add_attribute`` 用のparserを生成する。

    Args:
        subparsers: 親parserのsubparsers

    Returns:
        生成したArgumentParser
    """
    subcommand_name = "add_attribute"
    subcommand_help = "アノテーション仕様に属性を追加します。"
    description = "アノテーション仕様に属性を追加し、指定ラベルへ紐付けます。 ``choice`` と ``select`` では選択肢も同時に追加します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
