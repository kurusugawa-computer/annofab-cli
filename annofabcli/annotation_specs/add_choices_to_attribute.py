from __future__ import annotations

import argparse
import copy
import json
import logging
from pathlib import Path
from typing import Any

import annofabapi
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor

import annofabcli.common.cli
from annofabcli.annotation_specs.add_choice_attribute import build_choices, read_choices_csv, read_choices_json
from annofabcli.annotation_specs.utils import get_attribute_name_en
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


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


def get_target_attribute(
    annotation_specs_accessor: AnnotationSpecsAccessor,
    *,
    attribute_id: str | None,
    attribute_name_en: str | None,
) -> dict[str, Any]:
    """
    CLI引数で指定された属性IDまたは属性名から追加対象属性を取得する。

    Args:
        annotation_specs_accessor: アノテーション仕様アクセサ
        attribute_id: 指定された属性ID
        attribute_name_en: 指定された属性英語名

    Returns:
        追加対象の属性

    Raises:
        ValueError: 属性指定が不正、属性が見つからない、属性名が曖昧、または選択肢系属性でない場合
    """
    if (attribute_id is None) == (attribute_name_en is None):
        raise ValueError("追加先の属性は `attribute_id` または `attribute_name_en` のどちらか一方だけ指定してください。")

    if attribute_id is not None:
        attribute = annotation_specs_accessor.get_attribute(attribute_id=attribute_id)
    else:
        assert attribute_name_en is not None
        attribute = annotation_specs_accessor.get_attribute(attribute_name=attribute_name_en)

    if attribute["type"] not in ["choice", "select"]:
        raise ValueError(f"属性ID='{attribute['additional_data_definition_id']}' は選択肢系属性ではありません。")

    return attribute


def validate_added_choices(
    target_attribute: dict[str, Any],
    *,
    added_choices: list[dict[str, Any]],
    added_default_choice_id: str | None,
) -> None:
    """
    追加する選択肢が既存の選択肢と衝突しないか検証する。

    Args:
        target_attribute: 追加先の属性
        added_choices: 追加予定の選択肢一覧
        added_default_choice_id: 追加予定のデフォルト選択肢ID

    Raises:
        ValueError: 選択肢ID・選択肢名・デフォルト値が既存の属性情報と衝突する場合
    """
    existing_choices = target_attribute["choices"]
    existing_choice_ids = {choice["choice_id"] for choice in existing_choices}
    duplicated_choice_ids = existing_choice_ids & {choice["choice_id"] for choice in added_choices}
    if duplicated_choice_ids:
        duplicated_text = ", ".join(sorted(duplicated_choice_ids))
        raise ValueError(f"追加先の属性に既に存在する `choice_id` が指定されています。 :: {duplicated_text}")

    existing_choice_name_ens = {AnnofabApiFacade.get_choice_name_en(choice) for choice in existing_choices}
    duplicated_choice_name_ens = existing_choice_name_ens & {AnnofabApiFacade.get_choice_name_en(choice) for choice in added_choices}
    if duplicated_choice_name_ens:
        duplicated_text = ", ".join(sorted(duplicated_choice_name_ens))
        raise ValueError(f"追加先の属性に既に存在する `choice_name_en` が指定されています。 :: {duplicated_text}")

    existing_default_choice_id = target_attribute.get("default")
    if added_default_choice_id is not None and existing_default_choice_id not in ["", None]:
        raise ValueError(f"追加先の属性には既にデフォルト選択肢が設定されています。 :: {existing_default_choice_id}")


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
        choices_json: str | None,
        choices_csv: Path | None,
        comment: str | None = None,
    ) -> bool:
        """
        既存の選択肢系属性へ選択肢を追加して、アノテーション仕様を更新する。

        Args:
            attribute_id: 追加先属性ID
            attribute_name_en: 追加先属性英語名
            choices_json: 追加する選択肢JSON
            choices_csv: 追加する選択肢CSV
            comment: 変更コメント

        Returns:
            追加を実行した場合はTrue、確認で中断した場合はFalse

        Raises:
            ValueError: 入力値や既存アノテーション仕様との整合性が不正な場合
        """
        if choices_json is not None:
            choice_inputs = read_choices_json(choices_json)
        elif choices_csv is not None:
            if not choices_csv.exists():
                raise ValueError(f"`--choices_csv` に指定されたファイルが存在しません。 :: {choices_csv}")
            choice_inputs = read_choices_csv(choices_csv)
        else:
            raise ValueError("`--choices_json` または `--choices_csv` のいずれかを指定してください。")

        added_choices, added_default_choice_id = build_choices(choice_inputs, min_count=1)

        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        annotation_specs_accessor = AnnotationSpecsAccessor(old_annotation_specs)
        target_attribute = get_target_attribute(
            annotation_specs_accessor,
            attribute_id=attribute_id,
            attribute_name_en=attribute_name_en,
        )
        validate_added_choices(
            target_attribute,
            added_choices=added_choices,
            added_default_choice_id=added_default_choice_id,
        )

        resolved_attribute_id = target_attribute["additional_data_definition_id"]
        resolved_attribute_name_en = get_attribute_name_en(target_attribute)
        added_choice_name_ens = [AnnofabApiFacade.get_choice_name_en(choice) for choice in added_choices]
        confirm_message = f"属性名(英語)='{resolved_attribute_name_en}', 属性ID='{resolved_attribute_id}' に {len(added_choices)} 件の選択肢 {added_choice_name_ens} を追加します。よろしいですか？"
        if added_default_choice_id is not None:
            confirm_message += f" 追加する選択肢のうち `choice_id`='{added_default_choice_id}' をデフォルト値に設定します。"
        if not self.confirm_processing(confirm_message):
            return False

        request_body = copy.deepcopy(old_annotation_specs)
        for attribute in request_body["additionals"]:
            if attribute["additional_data_definition_id"] != resolved_attribute_id:
                continue
            attribute["choices"].extend(added_choices)
            if added_default_choice_id is not None:
                attribute["default"] = added_default_choice_id
            break

        if comment is None:
            comment = create_comment_from_attribute(resolved_attribute_name_en, added_choice_name_ens)
        request_body["comment"] = comment
        request_body["last_updated_datetime"] = old_annotation_specs["updated_datetime"]
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"属性名(英語)='{resolved_attribute_name_en}', 属性ID='{resolved_attribute_id}' に {len(added_choices)} 件の選択肢を追加しました。")
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
            choices_json=args.choices_json,
            choices_csv=args.choices_csv,
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
        {"choice_id": "xlarge", "choice_name_en": "xlarge", "choice_name_ja": "特大"},
        {"choice_id": "tiny", "choice_name_en": "tiny", "choice_name_ja": "極小"},
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
        help=(
            "追加する選択肢情報のCSVファイルを指定します。 "
            "CSVには ``choice_name_en`` 列が必要です。 "
            "``choice_id`` と ``choice_name_en`` はユニークになるように指定してください。 "
            "任意で ``choice_id`` , ``choice_name_ja`` , ``is_default`` 列を指定できます。"
        ),
    )

    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更時に指定できるコメント。未指定の場合、自動でコメントが生成されます。")

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
    description = "既存の ``choice`` （ラジオボタン）または ``select`` （ドロップダウン）の属性に、選択肢を追加します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
