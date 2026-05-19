from __future__ import annotations

import argparse
import json
import logging
import sys
from enum import Enum
from pathlib import Path
from typing import Any

from annofabapi.util.attribute_restrictions import Restriction

import annofabcli.common.cli
import annofabcli.common.utils
from annofabcli.annotation_specs.attribute_restriction import AttributeRestrictionMessage
from annofabcli.annotation_specs.restriction_type import RESTRICTION_TYPE_TO_CONDITION_TYPE, matches_restriction_type
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class OutputFormat(Enum):
    """`list_attribute_restriction` の出力フォーマット。"""

    TEXT = "text"
    JSON = "json"
    PRETTY_JSON = "pretty_json"


class ListAttributeRestriction(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs list_restriction: error:"

    def get_history_id_from_before_index(self, project_id: str, before: int) -> str | None:
        histories, _ = self.service.api.get_annotation_specs_histories(project_id)
        if before + 1 > len(histories):
            logger.warning(f"アノテーション仕様の履歴は{len(histories)}個のため、最新より{before}個前のアノテーション仕様は見つかりませんでした。")
            return None
        history = histories[-(before + 1)]
        return history["history_id"]

    @staticmethod
    def get_restriction_text_list(annotation_specs: dict[str, Any], restrictions: list[dict[str, Any]]) -> list[str]:
        """
        属性制約一覧を人向けの文字列へ変換する。

        Args:
            annotation_specs: アノテーション仕様
            restrictions: 出力対象の属性制約一覧

        Returns:
            人が読みやすい属性制約文字列の一覧
        """
        return [Restriction.from_dict(restriction).to_human_readable(annotation_specs) for restriction in restrictions]

    def main(self) -> None:
        args = self.args

        if args.project_id is not None:
            history_id = None
            if args.history_id is not None:
                history_id = args.history_id

            if args.before is not None:
                history_id = self.get_history_id_from_before_index(args.project_id, args.before)
                if history_id is None:
                    print(  # noqa: T201
                        f"{self.COMMON_MESSAGE} argument --before: 最新より{args.before}個前のアノテーション仕様は見つかりませんでした。",
                        file=sys.stderr,
                    )
                    sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

            query_params = {"v": "3"}
            if history_id is not None:
                query_params["history_id"] = history_id

            annotation_specs, _ = self.service.api.get_annotation_specs(args.project_id, query_params=query_params)
        elif args.annotation_specs_json is not None:
            with args.annotation_specs_json.open(encoding="utf-8") as f:
                annotation_specs = json.load(f)

        else:
            raise RuntimeError("'--project_id'か'--annotation_specs_json'のどちらかを指定する必要があります。")

        main_obj = AttributeRestrictionMessage(
            labels=annotation_specs["labels"],
            additionals=annotation_specs["additionals"],
        )
        target_attribute_names = get_list_from_args(args.attribute_name) if args.attribute_name is not None else None
        target_label_names = get_list_from_args(args.label_name) if args.label_name is not None else None
        target_restrictions = main_obj.get_target_restrictions(
            annotation_specs["restrictions"],
            target_attribute_names=target_attribute_names,
            target_label_names=target_label_names,
        )
        target_restrictions = [restriction for restriction in target_restrictions if matches_restriction_type(restriction, args.restriction_type)]
        output_format = OutputFormat(args.format)
        if output_format in {OutputFormat.JSON, OutputFormat.PRETTY_JSON}:
            annofabcli.common.utils.print_json(
                target_restrictions,
                is_pretty=output_format == OutputFormat.PRETTY_JSON,
                output=args.output,
            )
            return

        restriction_text_list = self.get_restriction_text_list(annotation_specs, target_restrictions)
        annofabcli.common.utils.output_string("\n".join(restriction_text_list), args.output)


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    required_group = parser.add_mutually_exclusive_group(required=True)
    required_group.add_argument("-p", "--project_id", help="対象のプロジェクトのproject_idを指定します。APIで取得したアノテーション仕様情報を元に出力します。")
    required_group.add_argument(
        "--annotation_specs_json",
        type=Path,
        help="指定したアノテーション仕様のJSONファイルを指定します。JSONファイルに記載された情報を元に出力します。ただしアノテーション仕様の ``format_version`` は ``3`` である必要があります。",
    )

    # 過去のアノテーション仕様を参照するためのオプション
    old_annotation_specs_group = parser.add_mutually_exclusive_group()
    old_annotation_specs_group.add_argument(
        "--history_id",
        type=str,
        help=(
            "出力したいアノテーション仕様のhistory_idを指定してください。 "
            "history_idは ``annotation_specs list_history`` コマンドで確認できます。 "
            "指定しない場合は、最新のアノテーション仕様が出力されます。 "
        ),
    )

    old_annotation_specs_group.add_argument(
        "--before",
        type=annofabcli.common.cli.non_negative_int,
        help=(
            "出力したい過去のアノテーション仕様が、最新よりいくつ前のアノテーション仕様であるかを指定してください。  "
            "たとえば ``1`` を指定した場合、最新より1個前のアノテーション仕様を出力します。 "
            "指定しない場合は、最新のアノテーション仕様が出力されます。 "
        ),
    )

    parser.add_argument("--attribute_name", type=str, nargs="+", help="指定した属性名（英語）の属性の制約を出力します。")
    parser.add_argument("--label_name", type=str, nargs="+", help="指定したラベル名（英語）のラベルに紐づく属性の制約を出力します。")
    parser.add_argument(
        "--restriction_type",
        type=str,
        choices=list(RESTRICTION_TYPE_TO_CONDITION_TYPE.keys()),
        help=(
            "出力対象の属性制約種類。\n"
            "* ``can_input`` : 入力可否制約\n"
            "* ``has_label`` : ラベル条件制約\n"
            "* ``equals`` : 等価制約\n"
            "* ``not_equals`` : 非等価制約\n"
            "* ``matches`` : 正規表現一致制約\n"
            "* ``not_matches`` : 正規表現不一致制約\n"
            "* ``imply`` : 属性間の相関制約"
        ),
    )
    argument_parser.add_output()

    parser.add_argument(
        "-f",
        "--format",
        type=str,
        choices=[e.value for e in OutputFormat],
        default=OutputFormat.TEXT.value,
        help=(
            "出力フォーマット\n\n"
            f"* {OutputFormat.TEXT.value}: 人が読みやすい形式で出力する\n"
            f"* {OutputFormat.JSON.value}: 属性制約のJSONを1行で出力する形式\n"
            f"* {OutputFormat.PRETTY_JSON.value}: 属性制約のJSONを整形して出力する形式\n"
        ),
    )

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAttributeRestriction(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_attribute_restriction"

    subcommand_help = "アノテーション仕様の属性の制約情報を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
