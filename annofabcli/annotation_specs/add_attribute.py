from __future__ import annotations

import argparse
import copy
import logging
import uuid
from collections.abc import Sequence
from typing import Any

import annofabapi
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor

import annofabcli.common.cli
from annofabcli.annotation_specs.add_choice_attribute import validate_new_attribute
from annofabcli.annotation_specs.utils import create_name, get_label_name_en, get_target_labels
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)

ATTRIBUTE_TYPES = ["comment", "flag", "integer", "link", "text", "tracking"]


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


def create_comment_from_attribute(attribute_name_en: str, label_names: Sequence[str]) -> str:
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
    return f"以下の属性を追加しました。\n属性名(英語): {attribute_name_en}\n対象ラベル: {labels_text}"


def create_attribute(
    *,
    attribute_type: str,
    attribute_name_en: str,
    attribute_name_ja: str | None,
    attribute_id: str | None,
) -> dict[str, Any]:
    """
    属性1件分のAnnofab API向けオブジェクトを生成する。

    Args:
        attribute_type: 属性型
        attribute_name_en: 属性英語名
        attribute_name_ja: 属性日本語名
        attribute_id: 属性ID。未指定ならUUIDv4を自動生成
    Returns:
        Annofab API向けの属性オブジェクト
    """
    return {
        "additional_data_definition_id": attribute_id if attribute_id is not None else str(uuid.uuid4()),
        "name": create_name(attribute_name_en, attribute_name_ja),
        "type": attribute_type,
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
        label_ids: Sequence[str] | None,
        label_name_ens: Sequence[str] | None,
        comment: str | None = None,
    ) -> bool:
        """
        属性を追加し、指定ラベルへ紐付けてアノテーション仕様を更新する。

        Args:
            attribute_type: 属性型
            attribute_name_en: 属性英語名
            attribute_name_ja: 属性日本語名
            attribute_id: 属性ID。未指定ならUUIDv4を自動生成
            label_ids: 追加先ラベルID一覧。未指定時はNone
            label_name_ens: 追加先ラベル英語名一覧。未指定時はNone
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
        )

        duplicated_name_attribute_ids = validate_new_attribute(
            additionals,
            attribute_id=new_attribute["additional_data_definition_id"],
            attribute_name_en=attribute_name_en,
        )

        label_names = [get_label_name_en(label) for label in target_labels]
        confirm_message = f"属性名(英語)='{attribute_name_en}', 属性種類='{attribute_type}', 対象ラベル={label_names} を追加します。よろしいですか？"
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
            comment = create_comment_from_attribute(attribute_name_en, label_names)
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

        label_ids = get_list_from_args(args.label_id)
        label_name_ens = get_list_from_args(args.label_name_en)

        obj = AddAttributeMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.add_attribute(
            attribute_type=args.attribute_type,
            attribute_name_en=args.attribute_name_en,
            attribute_name_ja=args.attribute_name_ja,
            attribute_id=args.attribute_id,
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
            "追加する属性の種類。\n"
            "* ``flag`` : チェックボックス\n"
            "* ``integer`` : 整数\n"
            "* ``text`` : 自由記述（1行）\n"
            "* ``comment`` : 自由記述（複数行）\n"
            "* ``tracking`` : トラッキングID\n"
            "* ``link`` : アノテーションリンク"
        ),
    )
    parser.add_argument("--attribute_name_en", type=str, required=True, help="追加する属性の英語名。")
    parser.add_argument("--attribute_id", type=str, help="追加する属性の属性ID。未指定の場合はUUIDv4を自動生成します。")
    parser.add_argument("--attribute_name_ja", type=str, help="追加する属性の日本語名。")

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
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")

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
    subcommand_help = "アノテーション仕様に非選択肢系の属性を追加します。"
    description = "アノテーション仕様に非選択肢系の属性を追加します。選択肢系属性の追加は ``add_choice_attribute`` コマンドを使用してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
