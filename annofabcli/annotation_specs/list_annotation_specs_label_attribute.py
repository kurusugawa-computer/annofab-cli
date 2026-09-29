from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas
from annofabapi.models import Lang
from annofabapi.util.annotation_specs import get_message_with_lang
from dataclasses_json import DataClassJsonMixin

import annofabcli.common.cli
from annofabcli.annotation_specs.history import add_history_arguments, load_annotation_specs_or_exit
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import print_according_to_format, print_csv

logger = logging.getLogger(__name__)


@dataclass
class LabelAndAttribute(DataClassJsonMixin):
    label_id: str
    label_name_en: str | None
    label_name_ja: str | None
    label_name_vi: str | None
    annotation_type: str

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


def create_label_attribute_list(labels_v3: list[dict[str, Any]], additionals_v3: list[dict[str, Any]]) -> list[LabelAndAttribute]:
    """
    APIから取得したラベル情報（v3版）から、`LabelAndAttribute`のlistを生成します。

    Args:
        labels_v3: APIから取得したラベル情報（v3版）
    """

    def to_dataclass_list(label: dict[str, Any]) -> list[LabelAndAttribute]:
        result = []
        for attribute_id in label["additional_data_definitions"]:
            attribute = dict_attributes[attribute_id]

            result.append(
                LabelAndAttribute(
                    label_id=label["label_id"],
                    label_name_en=get_message_with_lang(label["label_name"], lang=Lang.EN_US),
                    label_name_ja=get_message_with_lang(label["label_name"], lang=Lang.JA_JP),
                    label_name_vi=get_message_with_lang(label["label_name"], lang=Lang.VI_VN),
                    annotation_type=label["annotation_type"],
                    attribute_id=attribute_id,
                    attribute_name_en=get_message_with_lang(attribute["name"], lang=Lang.EN_US),
                    attribute_name_ja=get_message_with_lang(attribute["name"], lang=Lang.JA_JP),
                    attribute_name_vi=get_message_with_lang(attribute["name"], lang=Lang.VI_VN),
                    attribute_type=attribute["type"],
                )
            )
        return result

    dict_attributes = {}
    for elm in additionals_v3:
        dict_attributes[elm["additional_data_definition_id"]] = elm

    result = []
    for label in labels_v3:
        result.extend(to_dataclass_list(label))
    return result


class PrintAnnotationSpecsLabelAndAttribute(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs list_label: error:"

    def print_annotation_specs_label(self, annotation_specs_v3: dict[str, Any], output_format: OutputFormat, output: str | None = None) -> None:
        # アノテーション仕様のv2とv3はほとんど同じなので、`convert_annotation_specs_labels_v2_to_v1`にはV3のアノテーション仕様を渡す
        label_attribute_list = create_label_attribute_list(annotation_specs_v3["labels"], annotation_specs_v3["additionals"])

        if output_format == OutputFormat.CSV:
            columns = [
                "label_id",
                "label_name_en",
                "label_name_ja",
                "label_name_vi",
                "annotation_type",
                "attribute_id",
                "attribute_name_en",
                "attribute_name_ja",
                "attribute_name_vi",
                "attribute_type",
            ]

            df = pandas.DataFrame(label_attribute_list, columns=columns)
            print_csv(df, output)

        elif output_format in [OutputFormat.JSON, OutputFormat.PRETTY_JSON]:
            print_according_to_format([e.to_dict() for e in label_attribute_list], format=output_format, output=output)

    def main(self) -> None:
        args = self.args
        annotation_specs = load_annotation_specs_or_exit(
            self.service,
            project_id=args.project_id,
            annotation_specs_json_file=args.annotation_specs_json_file,
            history_id=args.history_id,
            before=args.before,
            updated_datetime=args.updated_datetime,
            common_message=self.COMMON_MESSAGE,
        )

        self.print_annotation_specs_label(annotation_specs, output_format=OutputFormat(args.format), output=args.output)


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    required_group = parser.add_mutually_exclusive_group(required=True)
    required_group.add_argument("-p", "--project_id", help="対象のプロジェクトのproject_idを指定します。APIで取得したアノテーション仕様情報を元に出力します。")
    required_group.add_argument(
        "--annotation_specs_json_file",
        type=Path,
        help="指定したアノテーション仕様のJSONファイルを指定します。JSONファイルに記載された情報を元に出力します。ただしアノテーション仕様の ``format_version`` は ``3`` である必要があります。",
    )

    add_history_arguments(parser)

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
    PrintAnnotationSpecsLabelAndAttribute(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_label_attribute"

    subcommand_help = "アノテーション仕様のラベルとラベルに含まれている属性の一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
