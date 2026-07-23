from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas
from annofabapi.models import Lang
from annofabapi.util.annotation_specs import get_message_with_lang
from dataclasses_json import DataClassJsonMixin

import annofabcli.common.cli
from annofabcli.common.annofab.annotation_specs import api_keybind_to_keybind, keybind_to_api_keybind, keybind_to_text
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import print_according_to_format, print_csv

logger = logging.getLogger(__name__)


@dataclass
class ReferenceLabel:
    """属性を参照しているラベル情報。"""

    label_id: str
    """ラベルID"""
    label_name_en: str | None
    """ラベルの英語名"""


@dataclass
class FlattenAttribute(DataClassJsonMixin):
    """
    ネストされていないフラットな属性情報を格納するクラスです。
    選択肢の一覧などは格納できません。
    """

    attribute_id: str
    """属性ID

    Notes:
        APIレスポンスの ``additional_data_definition_id`` に相当します。
        ``additional_data_definition_id`` という名前がアノテーションJSONの `attributes` と対応していることが分かりにくかったので、`attribute_id`という名前に変えました。
    """
    attribute_name_en: str | None
    attribute_name_ja: str | None
    attribute_name_vi: str | None
    attribute_type: str
    """属性の種類"""
    default: str | bool | int | None
    """デフォルト値"""
    read_only: bool
    """読み込み専用の属性か否か"""
    choice_count: int
    """
    選択肢の個数
    ドロップダウン属性またはラジオボタン属性以外では0個です。
    """
    restriction_count: int
    """制約の個数"""
    reference_label_count: int
    """参照されているラベルの個数"""
    label_ids: list[str]
    """この属性を参照しているラベルのID一覧"""
    label_name_ens: list[str | None]
    """この属性を参照しているラベルの英語名一覧"""
    keybind: dict[str, Any] | None
    """CLIで指定できる形式のキーバインド"""
    keybind_text: str
    """人が読める形式のキーバインド"""


def create_relationship_between_attribute_and_label(labels_v3: list[dict[str, Any]]) -> dict[str, list[ReferenceLabel]]:
    """
    属性IDとラベル情報の関係を表したdictを生成します。

    * key: 属性ID
    * value: 属性を参照しているラベル情報のlist
    """
    result = defaultdict(list)
    for label in labels_v3:
        label_id = label["label_id"]
        label_name_en = get_message_with_lang(label["label_name"], lang=Lang.EN_US)
        attribute_id_list = label["additional_data_definitions"]
        for attribute_id in attribute_id_list:
            result[attribute_id].append(ReferenceLabel(label_id=label_id, label_name_en=label_name_en))
    return result


def create_flatten_attribute_list_from_additionals(additionals_v3: list[dict[str, Any]], labels_v3: list[dict[str, Any]], restrictions: list[dict[str, Any]]) -> list[FlattenAttribute]:
    """
    APIから取得した属性情報（v3版）から、属性情報の一覧を生成します。

    Args:
        additionals_v3: APIから取得した属性情報（v3版）
        labels_v3: APIから取得したラベル情報（v3版）
        restrictions: APIから取得した制約情報
    """
    # 属性IDごとの制約数をカウントする
    dict_restriction_count: dict[str, int] = defaultdict(int)
    for restriction in restrictions:
        dict_restriction_count[restriction["additional_data_definition_id"]] += 1

    # 属性IDとラベル情報の関係を表したdictを生成する。
    # keyが属性ID、valueが属性に紐づくラベル情報のlistであるdict。
    dict_label_info_list = create_relationship_between_attribute_and_label(labels_v3)

    def dict_additional_to_dataclass(additional: dict[str, Any]) -> FlattenAttribute:
        """
        辞書の属性情報をDataClassのラベル情報に変換します。
        """
        attribute_id = additional["additional_data_definition_id"]
        additional_name = additional["name"]
        label_info_list = dict_label_info_list[attribute_id]
        keybind = api_keybind_to_keybind(additional.get("keybind", []))
        return FlattenAttribute(
            attribute_id=attribute_id,
            attribute_name_en=get_message_with_lang(additional_name, lang=Lang.EN_US),
            attribute_name_ja=get_message_with_lang(additional_name, lang=Lang.JA_JP),
            attribute_name_vi=get_message_with_lang(additional_name, lang=Lang.VI_VN),
            attribute_type=additional["type"],
            default=additional["default"],
            read_only=additional["read_only"],
            choice_count=len(additional["choices"]),
            restriction_count=dict_restriction_count[attribute_id],
            reference_label_count=len(label_info_list),
            label_ids=[e.label_id for e in label_info_list],
            label_name_ens=[e.label_name_en for e in label_info_list],
            keybind=keybind,
            keybind_text=keybind_to_text(keybind_to_api_keybind(keybind)),
        )

    return [dict_additional_to_dataclass(e) for e in additionals_v3]


class PrintAnnotationSpecsAttribute(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs list_attribute: error:"

    def print_annotation_specs_attribute(self, annotation_specs_v3: dict[str, Any], output_format: OutputFormat, output: str | None = None) -> None:
        attribute_list = create_flatten_attribute_list_from_additionals(annotation_specs_v3["additionals"], annotation_specs_v3["labels"], annotation_specs_v3["restrictions"])
        logger.info(f"{len(attribute_list)} 件の属性情報を出力します。")
        if output_format == OutputFormat.CSV:
            columns = [
                "attribute_id",
                "attribute_name_en",
                "attribute_name_ja",
                "attribute_name_vi",
                "type",
                "default",
                "read_only",
                "choice_count",
                "restriction_count",
                "reference_label_count",
                "label_ids",
                "label_name_ens",
                "keybind",
                "keybind_text",
            ]

            records = []
            for attribute in attribute_list:
                record = attribute.to_dict()
                record["type"] = attribute.attribute_type
                record["label_ids"] = json.dumps(attribute.label_ids, ensure_ascii=False)
                record["label_name_ens"] = json.dumps(attribute.label_name_ens, ensure_ascii=False)
                record["keybind"] = "" if attribute.keybind is None else json.dumps(attribute.keybind, ensure_ascii=False)
                records.append(record)
            df = pandas.DataFrame(records, columns=columns)
            print_csv(df, output)

        elif output_format in [OutputFormat.JSON, OutputFormat.PRETTY_JSON]:
            print_according_to_format([e.to_dict() for e in attribute_list], format=output_format, output=output)

    def get_history_id_from_before_index(self, project_id: str, before: int) -> str | None:
        histories, _ = self.service.api.get_annotation_specs_histories(project_id)
        if before + 1 > len(histories):
            logger.warning(f"アノテーション仕様の履歴は{len(histories)}個のため、最新より{before}個前のアノテーション仕様は見つかりませんでした。")
            return None
        history = histories[-(before + 1)]
        logger.info(f"{history['updated_datetime']}のアノテーション仕様を出力します。 :: history_id='{history['history_id']}', comment='{history['comment']}'")
        return history["history_id"]

    def main(self) -> None:
        args = self.args

        if args.project_id is not None:
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

            annotation_specs, _ = self.service.api.get_annotation_specs(args.project_id, query_params={"history_id": history_id, "v": "3"})
        elif args.annotation_specs_json_file is not None:
            with args.annotation_specs_json_file.open() as f:
                annotation_specs = json.load(f)
        else:
            raise RuntimeError("'--project_id'か'--annotation_specs_json_file'のどちらかを指定する必要があります。")

        self.print_annotation_specs_attribute(annotation_specs, output_format=OutputFormat(args.format), output=args.output)


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    required_group = parser.add_mutually_exclusive_group(required=True)
    required_group.add_argument("-p", "--project_id", help="対象のプロジェクトのproject_idを指定します。APIで取得したアノテーション仕様情報を元に出力します。")
    required_group.add_argument(
        "--annotation_specs_json_file",
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

    parser.add_argument(
        "-f",
        "--format",
        type=str,
        choices=[OutputFormat.CSV.value, OutputFormat.JSON.value, OutputFormat.PRETTY_JSON.value],
        default=OutputFormat.CSV.value,
        help="出力フォーマット ",
    )

    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PrintAnnotationSpecsAttribute(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_attribute"

    subcommand_help = "アノテーション仕様の属性情報を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
