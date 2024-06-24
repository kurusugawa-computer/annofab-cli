"""
アノテーション仕様を出力する
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Optional, Union

import pandas
from annofabapi.models import Lang
from annofabapi.util.annotation_specs import get_message_with_lang
from dataclasses_json import DataClassJsonMixin

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import print_csv

logger = logging.getLogger(__name__)


@dataclass
class AttributeForCsv(DataClassJsonMixin):
    """
    CSV用の属性情報を格納するクラスです。
    """

    attribute_id: str
    """属性ID

    Notes:
        APIレスポンスの ``additional_data_definition_id`` に相当します。
        ``additional_data_definition_id`` という名前がアノテーションJSONの `attributes` と対応していることが分かりにくかったので、`attribute_id`という名前に変えました。
    """  # noqa: E501
    attribute_name_en: Optional[str]
    attribute_name_ja: Optional[str]
    attribute_name_vi: Optional[str]
    type: str
    """属性の種類"""
    default: Optional[Union[str, bool, int]]
    """デフォルト値"""
    read_only: bool
    """読み込み専用の属性か否か"""
    choice_count: int
    """
    選択肢の個数
    ドロップダウン属性またはラジオボタン属性以外では0個です。
    """
    reference_label_count: int
    """参照されているラベルの個数"""


def create_relationship_between_attribute_and_label(labels_v3: list[dict[str, Any]]) -> dict[str, set[str]]:
    """
    属性IDとラベルIDの関係を表したdictを生成します。

    * key: 属性ID
    * value: 属性を参照しているラベルのlabel_idのset
    """
    result = defaultdict(set)
    for label in labels_v3:
        label_id = label["label_id"]
        attribute_id_list = label["additional_data_definitions"]
        for attribute_id in attribute_id_list:
            result[attribute_id].add(label_id)
    return result


def create_df_from_additionals(additionals_v3: list[dict[str, Any]], dict_label_ids: dict[str, set[str]]) -> pandas.DataFrame:
    """
    APIから取得した属性情報（v3版）から、pandas.DataFrameを生成します。

    Args:
        additionals_v3: APIから取得した属性情報（v3版）
        dict_label_ids: keyが属性ID、valueが属性に紐づくラベルのIDのsetであるdict
    """

    def dict_additional_to_dataclass(additional: dict[str, Any]) -> AttributeForCsv:
        """
        辞書の属性情報をDataClassのラベル情報に変換します。
        """
        attribute_id = additional["additional_data_definition_id"]
        additional_name = additional["name"]
        return AttributeForCsv(
            attribute_id=attribute_id,
            attribute_name_en=get_message_with_lang(additional_name, lang=Lang.EN_US),
            attribute_name_ja=get_message_with_lang(additional_name, lang=Lang.JA_JP),
            attribute_name_vi=get_message_with_lang(additional_name, lang=Lang.VI_VN),
            type=additional["type"],
            default=additional["default"],
            read_only=additional["read_only"],
            choice_count=len(additional["choices"]),
            reference_label_count=len(dict_label_ids[attribute_id]),
        )

    new_labels = [dict_additional_to_dataclass(e) for e in additionals_v3]

    columns = [
        "attribute_id",
        "attribute_name_en",
        "attribute_name_ja",
        "attribute_name_vi",
        "type",
        "default",
        "read_only",
        "choice_count",
        "reference_label_count",
    ]

    df = pandas.DataFrame(new_labels, columns=columns)
    return df


class PrintAnnotationSpecsAttribute(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs list_attribute: error:"

    def print_annotation_specs_attribute(self, project_id: str, arg_format: str, output: Optional[str] = None, history_id: Optional[str] = None):  # noqa: ANN201
        annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params={"history_id": history_id, "v": "3"})

        if arg_format == FormatArgument.CSV.value:
            dict_label_ids = create_relationship_between_attribute_and_label(annotation_specs["labels"])
            df = create_df_from_additionals(annotation_specs["additionals"], dict_label_ids)
            print_csv(df, output)

    def get_history_id_from_before_index(self, project_id: str, before: int) -> Optional[str]:
        histories, _ = self.service.api.get_annotation_specs_histories(project_id)
        if before + 1 > len(histories):
            logger.warning(f"アノテーション仕様の履歴は{len(histories)}個のため、最新より{before}個前のアノテーション仕様は見つかりませんでした。")
            return None
        history = histories[-(before + 1)]
        logger.info(
            f"{history['updated_datetime']}のアノテーション仕様を出力します。history_id={history['history_id']}, comment={history['comment']}"
        )
        return history["history_id"]

    def main(self) -> None:
        args = self.args

        if args.before is not None:
            history_id = self.get_history_id_from_before_index(args.project_id, args.before)
            if history_id is None:
                print(  # noqa: T201
                    f"{self.COMMON_MESSAGE} argument --before: 最新より{args.before}個前のアノテーション仕様は見つかりませんでした。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
        else:
            history_id = args.history_id

        self.print_annotation_specs_attribute(args.project_id, arg_format=args.format, output=args.output, history_id=history_id)


def parse_args(parser: argparse.ArgumentParser) -> None:
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

    parser.add_argument("-f", "--format", type=str, choices=[FormatArgument.CSV.value], default=FormatArgument.CSV.value, help="出力フォーマット ")

    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PrintAnnotationSpecsAttribute(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_attribute"

    subcommand_help = "アノテーション仕様の属性情報を出力する"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
