from __future__ import annotations

import argparse
import logging
import re
from collections.abc import Collection
from typing import Any, Optional

import more_itertools

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class ReplacingAttributeId(CommandLineWithConfirm):
    @staticmethod
    def replace_attribute_id_of_restrictions(old_attribute_id: str, new_attribute_id: str, restriction_list: list[dict[str, Any]]) -> None:
        """
        制約情報の中で使用されている属性IDを新しい属性IDに変更する

        Args:
            new_attribute_id: 変更後の属性ID
            restriction_list: (IN/OUT) 制約情報。制約情報内の属性IDが変更される。
        """

        def _replace_attribute_id_in_condition(condition: dict[str, Any]) -> None:
            if condition["_type"] == "Imply":
                if condition["premise"]["additional_data_definition_id"] == old_attribute_id:
                    condition["premise"]["additional_data_definition_id"] = new_attribute_id

                _replace_attribute_id_in_condition(condition["premise"]["condition"])
                _replace_attribute_id_in_condition(condition["condition"])

        for restriction in restriction_list:
            if restriction["additional_data_definition_id"] == old_attribute_id:
                restriction["additional_data_definition_id"] = new_attribute_id

            _replace_attribute_id_in_condition(restriction["condition"])

    @staticmethod
    def replace_attribute_id_of_labels(old_attribute_id: str, new_attribute_id: str, label_list: list[dict[str, Any]]) -> None:
        """
        ラベル情報の中で使用されている属性IDを新しい属性IDに変更する

        Args:
            new_attribute_id: 変更後の属性ID
            label_list: (IN/OUT) ラベル情報。ラベル情報内の属性IDが変更される。
        """
        for label in label_list:
            attribute_id_list = label["additional_data_definitions"]
            try:
                index = attribute_id_list.index(old_attribute_id)
                attribute_id_list[index] = new_attribute_id
            except ValueError:
                # 変更対象の属性IDが見つかれなければ何もしない
                pass

    @staticmethod
    def exists_attribute_with_attribute_id(attribute_list: list[dict[str, Any]], attribute_id: str) -> bool:
        """指定したlabel_idを持つラベル情報が存在するか否か"""
        return more_itertools.first_true(attribute_list, pred=lambda e: e["additional_data_definition_id"] == attribute_id) is not None

    @staticmethod
    def validate_attribute_id(str_id: str) -> bool:
        """
        指定した文字列が、属性IDに利用できる文字列か否か
        """
        return re.fullmatch("[A-Za-z0-9_.\\-]+", str_id) is not None

    def main(self, annotation_specs: dict[str, Any], *, target_attribute_names: Optional[Collection[str]] = None) -> None:
        """
        アノテーション仕様内の属性IDを英語名に変更します。

        Args:
            annotation_specs: (IN/OUT) アノテーション仕様情報。中身が変更されます。
            target_attribute_names: 変更対象の属性英語名。Noneならすべての属性の属性IDを変更します。

        """
        label_list = annotation_specs["labels"]
        attribute_list = annotation_specs["additionals"]
        restriction_list = annotation_specs["restrictions"]

        replaced_count = 0
        for attribute in attribute_list:
            attribute_id = attribute["additional_data_definition_id"]
            attribute_name_en = AnnofabApiFacade.get_additional_data_definition_name_en(attribute)

            if target_attribute_names is not None:  # noqa: SIM102
                if attribute_name_en not in target_attribute_names:
                    continue

            if not self.validate_attribute_id(attribute_name_en):
                logger.warning(f"属性英語名='{attribute_name_en}'は属性IDに利用できない文字を含むため、属性ID='{attribute_id}'を'{attribute_name_en}'に変更しません。")
                continue

            if self.exists_attribute_with_attribute_id(attribute_list, attribute_id=attribute_name_en):
                logger.warning(f"属性ID='{attribute_name_en}'である属性が既に存在するため、属性ID='{attribute_id}'を'{attribute_name_en}'に変更しません。")
                continue

            if not self.confirm_processing(f"属性ID='{attribute_id}'を'{attribute_name_en}'に変更したアノテーション仕様のJSONを出力しますか？"):
                continue

            attribute["additional_data_definition_id"] = attribute_name_en
            self.replace_attribute_id_of_labels(old_attribute_id=attribute_id, new_attribute_id=attribute_name_en, label_list=label_list)
            self.replace_attribute_id_of_restrictions(old_attribute_id=attribute_id, new_attribute_id=attribute_name_en, restriction_list=restriction_list)
            replaced_count += 1

        logger.info(f"{replaced_count} 個の属性の属性IDを変更しました。")


class GetAnnotationSpecsWithAttributeIdReplaced(CommandLine):
    def main(self) -> None:
        args = self.args
        project_id: str = args.project_id
        super().validate_project(project_id)

        annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params={"v": 3})

        target_attribute_names = set(get_list_from_args(args.attribute_name)) if args.attribute_name is not None else None

        # アノテーション仕様のlabel_idを変更する
        ReplacingAttributeId(all_yes=args.yes).main(annotation_specs, target_attribute_names=target_attribute_names)

        self.print_according_to_format(annotation_specs)


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--attribute_name",
        type=str,
        nargs="+",
        help="置換対象の属性の英語名",
    )

    argument_parser.add_output()

    argument_parser.add_format(
        choices=[
            FormatArgument.JSON,
            FormatArgument.PRETTY_JSON,
        ],
        default=FormatArgument.PRETTY_JSON,
    )

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    GetAnnotationSpecsWithAttributeIdReplaced(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "get_with_attribute_id_replaced_english_name"

    subcommand_help = "属性IDをUUIDから英語名に置換したアノテーション仕様のJSONを出力します。"

    description = (
        "属性IDをUUIDから英語名に置換したアノテーション仕様のJSONを出力します。\n"
        "アノテーション仕様は変更しません。画面のインポート機能を使って、アノテーション仕様を変更することを想定しています。\n"
        "相関制約をJSONで直接設定する際などに利用すると便利です。IDをがUUID形式から分かりやすい名前になるため、JSON記述しやすくなります。\n"
        "【注意】既にアノテーションが存在する状態で属性IDを変更すると、既存のアノテーション情報が消える恐れがあります。十分注意して、属性IDを変更してください。"
    )

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
