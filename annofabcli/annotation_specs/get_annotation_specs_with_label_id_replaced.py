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


class ReplacingLabelId(CommandLineWithConfirm):
    @staticmethod
    def replace_label_id_of_restrictions(old_label_id: str, new_label_id: str, restriction_list: list[dict[str, Any]]) -> None:
        """
        制約情報の中で使用されているlabel_idを新しいlabel_idに変更する

        Args:
            old_label_id: 変更前のlabel_id
            new_label_id: 変更後のlabel_id
            restriction_list: (IN/OUT) 制約情報。制約情報のlabel_idが変更される。
        """

        def _replace_label_id_in_condition(condition: dict[str, Any]) -> None:
            if condition["_type"] == "Imply":
                _replace_label_id_in_condition(condition["premise"]["condition"])
                _replace_label_id_in_condition(condition["condition"])
            elif condition["_type"] == "HasLabel":
                # アノテーションリンク先であるラベルIDを置換する
                labels = condition["labels"]
                try:
                    index = labels.index(old_label_id)
                    labels[index] = new_label_id
                except ValueError:
                    # old_label_idがlabelsになければ、何もしない
                    pass

        for restriction in restriction_list:
            _replace_label_id_in_condition(restriction["condition"])

    @staticmethod
    def exists_label_with_label_id(label_list: list[dict[str, Any]], label_id: str) -> bool:
        """指定したlabel_idを持つラベル情報が存在するか否か"""
        return more_itertools.first_true(label_list, pred=lambda e: e["label_id"] == label_id) is not None

    @staticmethod
    def validate_label_id(str_id: str) -> bool:
        """
        指定した文字列が、label_idに利用できる文字列か否か
        """
        return re.fullmatch("[A-Za-z0-9_.\\-]+", str_id) is not None

    def main(self, annotation_specs: dict[str, Any], *, target_label_names: Optional[Collection[str]] = None) -> None:
        """
        アノテーション仕様内のlabel_idをラベル英語名に変更します。

        Args:
            annotation_specs: (IN/OUT) アノテーション仕様情報。中身が変更されます。
            target_label_names: 変更対象のラベル英語名。Noneならすべてのラベルのlabel_idを変更します。

        """
        label_list = annotation_specs["labels"]
        restriction_list = annotation_specs["restrictions"]

        replaced_count = 0
        for label in label_list:
            label_id = label["label_id"]
            label_name_en = AnnofabApiFacade.get_label_name_en(label)

            if target_label_names is not None:  # noqa: SIM102
                if label_name_en not in target_label_names:
                    continue

            if not self.validate_label_id(label_name_en):
                logger.warning(f"label_name_en='{label_name_en}'はlabel_idにできない文字を含むため、label_id='{label_id}'を'{label_name_en}'に変更しません。")
                continue

            if self.exists_label_with_label_id(label_list, label_id=label_name_en):
                logger.warning(f"label_id='{label_name_en}'であるラベルが既に存在するため、label_id='{label_id}'を'{label_name_en}'に変更しません。")
                continue

            if not self.confirm_processing(f"label_id='{label_id}'を'{label_name_en}'に変更したアノテーション仕様のJSONを出力しますか？"):
                continue

            # ラベル内のlabel_idを変更する
            label["label_id"] = label_name_en
            self.replace_label_id_of_restrictions(old_label_id=label_id, new_label_id=label_name_en, restriction_list=restriction_list)
            replaced_count += 1

        logger.info(f"{replaced_count} 個のラベルのlabel_idを変更しました。")


class GetAnnotationSpecsWithLabelIdReplaced(CommandLine):
    def main(self) -> None:
        args = self.args
        project_id: str = args.project_id
        super().validate_project(project_id)

        annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params={"v": 3})

        target_label_names = set(get_list_from_args(args.label_name)) if args.label_name is not None else None

        # アノテーション仕様のlabel_idを変更する
        ReplacingLabelId(all_yes=args.yes).main(annotation_specs, target_label_names=target_label_names)

        self.print_according_to_format(annotation_specs)


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--label_name",
        type=str,
        nargs="+",
        help="置換対象のラベルの英語名",
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
    GetAnnotationSpecsWithLabelIdReplaced(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "get_with_label_id_replaced_english_name"

    subcommand_help = "label_idをUUIDから英語名に置換したアノテーション仕様のJSONを出力します。"

    description = (
        "ラベルIDをUUIDから英語名に置換したアノテーション仕様のJSONを出力します。\n"
        "アノテーション仕様は変更しません。画面のインポート機能を使って、アノテーション仕様を変更することを想定しています。\n"
        "相関制約をJSONで直接設定する際などに利用すると便利です。IDをがUUID形式から分かりやすい名前になるため、JSON記述しやすくなります。\n"
        "【注意】既にアノテーションが存在する状態でラベルIDを変更すると、既存のアノテーション情報が消える恐れがあります。十分注意して、IDを変更してください。"
    )

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
