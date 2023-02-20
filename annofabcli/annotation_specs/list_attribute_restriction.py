from __future__ import annotations

import argparse
import logging
import sys
from enum import Enum
from typing import Any, Collection, Optional

from more_itertools import first_true

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class FormatArgument(Enum):
    """
    表示するフォーマット ``--format`` で指定できる値

    Attributes:
        TEXT: 属性IDや種類を隠したシンプルなテキスト
        DETAILED_TEXT: 属性IDや属性種類などの詳細情報を表示したテキスト
    """

    TEXT = "text"
    DETAILED_TEXT = "detailed_text"


class ListAttributeRestrictionMain:
    """
    アノテーション仕様の制約から自然言語で書かれたメッセージを生成します。

    Args:
        labels: アノテーション仕様のラベル情報
        additionals: アノテーション仕様の属性情報

    """

    def __init__(
        self,
        labels: list[dict[str, Any]],
        additionals: list[dict[str, Any]],
        format: FormatArgument = FormatArgument.DETAILED_TEXT,  # pylint: disable=redefined-builtin
    ):
        self.attribute_dict = {e["additional_data_definition_id"]: e for e in additionals}
        self.label_dict = {e["label_id"]: e for e in labels}
        self.format = format

    def get_labels_text(self, label_ids: Collection[str]) -> str:
        label_message_list = []
        for label_id in label_ids:
            label = self.label_dict.get(label_id)
            label_name = AnnofabApiFacade.get_label_name_en(label) if label is not None else ""

            label_message = f"'{label_name}'"
            if self.format == FormatArgument.DETAILED_TEXT:
                label_message = f"{label_message} (id='{label_id}')"
            label_message_list.append(label_message)

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
                tmp = f"'{value}'"
                if self.format == FormatArgument.DETAILED_TEXT:
                    tmp = f"{tmp} (name='{choice_name}')"
                return tmp

            else:
                return f"'{value}'"
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
        str_type = condition["_type"]

        if str_type == "Imply":
            # 属性間の制約
            premise = condition["premise"]
            if_condition_text = self.get_restriction_text(
                premise["additional_data_definition_id"], premise["condition"]
            )
            then_text = self.get_restriction_text(attribute_id, condition["condition"])
            return f"{then_text} IF {if_condition_text}"

        attribute = self.attribute_dict.get(attribute_id)
        if attribute is not None:
            subject = f"'{AnnofabApiFacade.get_additional_data_definition_name_en(attribute)}'"
            if self.format == FormatArgument.DETAILED_TEXT:
                subject = f"{subject} (id='{attribute_id}', type='{attribute['type']}')"
        else:
            logger.warning(f"属性IDが'{attribute_id}'の属性は存在しません。")
            subject = "''"
            if self.format == FormatArgument.DETAILED_TEXT:
                subject = f"{subject} (id='{attribute_id}')"

        if str_type == "CanInput":
            verb = "CAN INPUT" if condition["enable"] else "CAN NOT INPUT"
            str_object = ""

        elif str_type == "HasLabel":
            verb = "HAS LABEL"
            str_object = self.get_labels_text(condition["labels"])

        elif str_type == "Equals":
            verb = "EQUALS"
            str_object = self.get_object_for_equals_or_notequals(condition["value"], attribute)

        elif str_type == "NotEquals":
            verb = "DOES NOT EQUAL"
            str_object = self.get_object_for_equals_or_notequals(condition["value"], attribute)

        elif str_type == "Matches":
            verb = "MATCHES"
            str_object = f"'{condition['value']}'"

        elif str_type == "NotMatches":
            verb = "DOES NOT MATCH"
            str_object = f"'{condition['value']}'"

        tmp = f"{subject} {verb}"
        if str_object != "":
            tmp = f"{tmp} {str_object}"
        return tmp

    def get_attribute_from_name(self, attribute_name: str) -> Optional[dict[str, Any]]:
        tmp = [
            attribute
            for attribute in self.attribute_dict.values()
            if AnnofabApiFacade.get_additional_data_definition_name_en(attribute) == attribute_name
        ]
        if len(tmp) == 1:
            return tmp[0]
        elif len(tmp) == 0:
            logger.warning(f"属性名(英語)が'{attribute_name}'の属性は存在しません。")
            return None
        else:
            logger.warning(f"属性名(英語)が'{attribute_name}'の属性は複数存在します。")
            return None

    def get_label_from_name(self, label_name: str) -> Optional[dict[str, Any]]:
        tmp = [label for label in self.label_dict.values() if AnnofabApiFacade.get_label_name_en(label) == label_name]
        if len(tmp) == 1:
            return tmp[0]
        elif len(tmp) == 0:
            logger.warning(f"ラベル名(英語)が'{label_name}'のラベルは存在しません。")
            return None
        else:
            logger.warning(f"ラベル名(英語)が'{label_name}'のラベルは複数存在します。")
            return None

    def get_target_attribute_ids(
        self,
        target_attribute_names: Optional[Collection[str]] = None,
        target_label_names: Optional[Collection[str]] = None,
    ) -> set[str]:
        result: set[str] = set()

        if target_attribute_names is not None:
            tmp_attribute_list = [
                self.get_attribute_from_name(attribute_name) for attribute_name in target_attribute_names
            ]
            tmp_ids = {
                attribute["additional_data_definition_id"] for attribute in tmp_attribute_list if attribute is not None
            }
            result = result | tmp_ids

        if target_label_names is not None:
            tmp_label_list = [self.get_label_from_name(label_name) for label_name in target_label_names]
            tmp_ids_list = [label["additional_data_definitions"] for label in tmp_label_list if label is not None]
            for attribute_ids in tmp_ids_list:
                result = result | set(attribute_ids)

        return result

    def get_restriction_text_list(
        self,
        restrictions: list[dict[str, Any]],
        *,
        target_attribute_names: Optional[Collection[str]] = None,
        target_label_names: Optional[Collection[str]] = None,
    ) -> list[str]:
        if target_attribute_names is not None or target_label_names is not None:
            target_attribute_ids = self.get_target_attribute_ids(
                target_attribute_names=target_attribute_names, target_label_names=target_label_names
            )
            return [
                self.get_restriction_text(e["additional_data_definition_id"], e["condition"])
                for e in restrictions
                if e["additional_data_definition_id"] in target_attribute_ids
            ]
        else:
            return [self.get_restriction_text(e["additional_data_definition_id"], e["condition"]) for e in restrictions]


class ListAttributeRestriction(AbstractCommandLineInterface):
    COMMON_MESSAGE = "annofabcli annotation_specs list_restriction: error:"

    def get_history_id_from_before_index(self, project_id: str, before: int) -> Optional[str]:
        histories, _ = self.service.api.get_annotation_specs_histories(project_id)
        if before + 1 > len(histories):
            logger.warning(f"アノテーション仕様の履歴は{len(histories)}個のため、最新より{before}個前のアノテーション仕様は見つかりませんでした。")
            return None
        history = histories[-(before + 1)]
        return history["history_id"]

    def main(self):
        args = self.args

        history_id = None
        if args.history_id is not None:
            history_id = args.history_id

        if args.before is not None:
            history_id = self.get_history_id_from_before_index(args.project_id, args.before)
            if history_id is None:
                print(
                    f"{self.COMMON_MESSAGE} argument --before: 最新より{args.before}個前のアノテーション仕様は見つかりませんでした。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        query_params = {"v": "2"}
        if history_id is not None:
            query_params["history_id"] = history_id

        annotation_specs, _ = self.service.api.get_annotation_specs(args.project_id, query_params=query_params)
        main_obj = ListAttributeRestrictionMain(
            labels=annotation_specs["labels"],
            additionals=annotation_specs["additionals"],
            format=FormatArgument(args.format),
        )
        target_attribute_names = get_list_from_args(args.attribute_name) if args.attribute_name is not None else None
        target_label_names = get_list_from_args(args.label_name) if args.label_name is not None else None
        restriction_text_list = main_obj.get_restriction_text_list(
            annotation_specs["restrictions"],
            target_attribute_names=target_attribute_names,
            target_label_names=target_label_names,
        )

        annofabcli.common.utils.output_string("\n".join(restriction_text_list), args.output)


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

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
        type=int,
        help=(
            "出力したい過去のアノテーション仕様が、最新よりいくつ前のアノテーション仕様であるかを指定してください。  "
            "たとえば ``1`` を指定した場合、最新より1個前のアノテーション仕様を出力します。 "
            "指定しない場合は、最新のアノテーション仕様が出力されます。 "
        ),
    )

    parser.add_argument("--attribute_name", type=str, nargs="+", help="指定した属性名（英語）の属性の制約を出力します。")
    parser.add_argument("--label_name", type=str, nargs="+", help="指定したラベル名（英語）のラベルに紐づく属性の制約を出力します。")
    argument_parser.add_output()

    parser.add_argument(
        "-f",
        "--format",
        type=str,
        choices=[e.value for e in FormatArgument],
        default=FormatArgument.TEXT.value,
        help=f"出力フォーマット\n"
        "\n"
        f"* {FormatArgument.TEXT.value}: 英語名のみ出力する形式\n"
        f"* {FormatArgument.DETAILED_TEXT.value}: 属性IDや属性種類などの詳細情報を出力する形式\n",
    )

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAttributeRestriction(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "list_attribute_restriction"

    subcommand_help = "アノテーション仕様の属性の制約情報を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
