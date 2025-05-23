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


class ReplacingChoiceId(CommandLineWithConfirm):
    @staticmethod
    def exists_choice_with_choice_id(choice_list: list[dict[str, Any]], choice_id: str) -> bool:
        """指定した選択肢IDを持つ選択肢情報が存在するか否か"""
        return more_itertools.first_true(choice_list, pred=lambda e: e["choice_id"] == choice_id) is not None

    @staticmethod
    def validate_choice_id(str_id: str) -> bool:
        """
        指定した文字列が、属性IDに利用できる文字列か否か
        """
        return re.fullmatch("[A-Za-z0-9_.\\-]+", str_id) is not None

    def main(self, annotation_specs: dict[str, Any], *, target_attribute_names: Optional[Collection[str]] = None) -> None:
        """
        アノテーション仕様内の選択肢IDを英語名に変更します。

        Args:
            annotation_specs: (IN/OUT) アノテーション仕様情報。中身が変更されます。
            target_attribute_names: 変更対象のラジオボタン/ドロップダウン属性の英語名。Noneならすべてのラジオボタン/ドロップダウン属性の選択肢IDを変更します。

        """
        attribute_list = annotation_specs["additionals"]

        replaced_count = 0
        attribute_count = 0
        for attribute in attribute_list:
            attribute_name_en = AnnofabApiFacade.get_additional_data_definition_name_en(attribute)

            if target_attribute_names is not None:  # noqa: SIM102
                if attribute_name_en not in target_attribute_names:
                    continue

            if attribute["type"] not in ["choice", "select"]:
                # ラジオボタン/ドロップダウン以外はスキップ
                continue

            choice_list = attribute["choices"]

            if not self.confirm_processing(f"属性英語名='{attribute_name_en}'の{len(choice_list)}個の選択肢IDを、選択肢英語名に変更したアノテーション仕様のJSONを出力しますか？"):
                continue

            replaced_choice_id_count = 0
            for choice in choice_list:
                choice_name_en = AnnofabApiFacade.get_choice_name_en(choice)
                choice_id = choice["choice_id"]

                if not self.validate_choice_id(choice_name_en):
                    logger.warning(
                        f"属性英語名='{attribute_name_en}', 選択肢英語名='{choice_name_en}'は選択肢IDに利用できない文字を含むため、選択肢ID='{choice_id}'を'{choice_name_en}'に変更しません。"
                    )
                    continue

                if self.exists_choice_with_choice_id(choice_list, choice_id=choice_name_en):
                    logger.warning(f"属性英語名='{attribute_name_en}', 選択肢ID='{choice_name_en}'である選択肢が既に存在するため、選択肢ID='{choice_id}'を'{choice_name_en}'に変更しません。")
                    continue

                choice["choice_id"] = choice_name_en
                if attribute["default"] == choice_id:
                    attribute["default"] = choice_name_en

                replaced_choice_id_count += 1

            logger.info(f"{replaced_choice_id_count} / {len(choice_list)} 個の選択肢IDを変更しました。")
            attribute_count += 1
            replaced_count += replaced_choice_id_count

        logger.info(f"{attribute_count} 個のラジオボタン/ドロップ属性の選択肢IDを、{replaced_count} 件変更しました。")


class GetAnnotationSpecsWithAttributeIdReplaced(CommandLine):
    def main(self) -> None:
        args = self.args
        project_id: str = args.project_id
        super().validate_project(project_id)

        annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params={"v": 3})

        target_attribute_names = set(get_list_from_args(args.attribute_name)) if args.attribute_name is not None else None

        # アノテーション仕様のlabel_idを変更する
        ReplacingChoiceId(all_yes=args.yes).main(annotation_specs, target_attribute_names=target_attribute_names)

        self.print_according_to_format(annotation_specs)


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--attribute_name",
        type=str,
        nargs="+",
        help="置換対象のラジオボタン/ドロップダウン属性の英語名",
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
    subcommand_name = "get_with_choice_id_replaced_english_name"

    subcommand_help = "選択肢IDをUUIDから英語名に置換したアノテーション仕様のJSONを出力します。"

    description = (
        "選択肢IDをUUIDから英語名に置換したアノテーション仕様のJSONを出力します。\n"
        "アノテーション仕様は変更しません。画面のインポート機能を使って、アノテーション仕様を変更することを想定しています。\n"
        "相関制約をJSONで直接設定する際などに利用すると便利です。IDをがUUID形式から分かりやすい名前になるため、JSON記述しやすくなります。\n"
        "【注意】既にアノテーションが存在する状態で選択肢IDを変更すると、既存のアノテーション情報が消える恐れがあります。十分注意して、選択肢IDを変更してください。"
    )

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
