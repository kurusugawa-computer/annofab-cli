from __future__ import annotations

import argparse
import logging
import sys
from typing import Any, Collection, Optional

from more_itertools import first_true

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.enums import FormatArgument

logger = logging.getLogger(__name__)


class ListAttributeRestrictionMain:
    """
    アノテーション仕様の制約を自然言語で出力します。

    Args:
        labels: アノテーション仕様のラベル情報
        additionals: アノテーション仕様の属性情報

    """

    def __init__(self, labels: list[dict[str, Any]], additionals: list[dict[str, Any]]):
        self.attribute_dict = {e["additional_data_definition_id"]: e for e in additionals}
        self.label_dict = {e["label_id"]: e for e in labels}

    def get_labels_text(self, label_ids: Collection[str]) -> str:
        label_message_list = []
        for label_id in label_ids:
            label = self.label_dict.get(label_id)
            label_name = AnnofabApiFacade.get_label_name_en(label) if label is not None else ""
            label_message_list.append(f"'{label_name}' (id={label_id})")

        return ", ".join(label_message_list)

    def get_object_for_equals_or_notequals(self, value: str, attribute: Optional[dict[str, Any]]) -> str:
        """制約条件が `Equals` or `NotEquals`のときの目的語を生成する。
        属性の種類がドロップダウンかセレクトボックスのときは、選択肢の名前を返す。

        Args:
            value (str): _description_
            attribute (Optional[dict[str,Any]]): _description_

        Returns:
            str: _description_
        """
        if attribute is not None and attribute["type"] in ["choice", "select"]:
            # ラジオボタンかドロップダウンのとき
            choices = attribute["choices"]
            choice = first_true(choices, pred=lambda e: e["choice_id"] == value)
            if choice is not None:
                choice_name = AnnofabApiFacade.get_choice_name_en(choice)
                return f"'{choice_name}'(id={value})"
            else:
                return f"''(id={value})"
        else:
            return f"'{value}'"

    def get_restriction_text(self, attribute_id: str, condition: dict[str, Any]) -> str:
        """制約情報のテキストを返します。

        Args:
            attribute_id (str): 属性ID
            condition (dict[str, Any]): 制約条件

        Returns:
            str: 制約を表す文
        """
        type = condition["_type"]

        if type == "Imply":
            # 属性間の制約
            premise = condition["premise"]
            if_condition_text = self.get_restriction_text(
                premise["additional_data_definition_id"], premise["condition"]
            )
            then_text = self.get_restriction_text(attribute_id, condition["condition"])
            return f"{then_text} IF {if_condition_text}"

        attribute = self.attribute_dict.get(attribute_id)
        if attribute is not None:
            subject = f"'{AnnofabApiFacade.get_additional_data_definition_name_en(attribute)}' (id={attribute_id}, type={attribute['type']})"
        else:
            subject = f"''(id={attribute_id})"

        if type == "CanInput":
            verb = "can input" if condition["enable"] else "can not input"
            object = ""

        elif type == "HasLabel":
            verb = "HAS LABEL"
            object = self.get_labels_text(condition["labels"])

        elif type == "Equals":
            verb = "EQUALS"
            object = self.get_object_for_equals_or_notequals(condition["value"], attribute)

        elif type == "NotEquals":
            verb = "DOES NOT EQUAL"
            object = self.get_object_for_equals_or_notequals(condition["value"], attribute)

        elif type == "Matches":
            verb = "MATCHES"
            object = f"'{condition['value']}'"

        elif type == "NotMatches":
            verb = "DOES NOT MATCH"
            object = f"'{condition['value']}'"

        return f"{subject} {verb} {object}"


class ListAttributeRestriction(AbstractCommandLineInterface):
    """
    アノテーション仕様を出力する
    """

    def main(self):

        args = self.args

        if args.before is not None:
            history_id = self.get_history_id_from_before_index(args.project_id, args.before)
            if history_id is None:
                print(
                    f"{self.COMMON_MESSAGE} argument --before: 最新より{args.before}個前のアノテーション仕様は見つかりませんでした。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
        else:
            # args.beforeがNoneならば、必ずargs.history_idはNoneでない
            history_id = args.history_id

        self.print_annotation_specs_label(
            args.project_id, arg_format=args.format, output=args.output, history_id=history_id
        )


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    # 過去のアノテーション仕様を参照するためのオプション
    old_annotation_specs_group = parser.add_mutually_exclusive_group()
    old_annotation_specs_group.add_argument(
        "--history_id",
        type=str,
        help=(
            "出力したい過去のアノテーション仕様のhistory_idを指定してください。 "
            "history_idは`annotation_specs list_history`コマンドで確認できます。 "
            "指定しない場合は、最新のアノテーション仕様が出力されます。 "
        ),
    )

    old_annotation_specs_group.add_argument(
        "--before",
        type=int,
        help=(
            "出力したい過去のアノテーション仕様が、最新よりいくつ前のアノテーション仕様であるかを指定してください。  "
            "たとえば`1`を指定した場合、最新より1個前のアノテーション仕様を出力します。 "
            "指定しない場合は、最新のアノテーション仕様が出力されます。 "
        ),
    )

    parser.add_argument(
        "-f",
        "--format",
        type=str,
        choices=["text", FormatArgument.PRETTY_JSON.value, FormatArgument.JSON.value],
        default="text",
        help=f"出力フォーマット "
        "text: 人が見やすい形式, "
        f"{FormatArgument.PRETTY_JSON.value}: インデントされたJSON, "
        f"{FormatArgument.JSON.value}: フラットなJSON",
    )

    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAttributeRestriction(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "list_restriction"

    subcommand_help = "アノテーション仕様の属性の制約情報を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
