from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

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
from annofabcli.common.utils import print_according_to_format, print_csv

logger = logging.getLogger(__name__)


@dataclass
class LabelAndAttribute(DataClassJsonMixin):
    label_id: str
    label_name_en: Optional[str]
    label_name_ja: Optional[str]
    label_name_vi: Optional[str]
    annotation_type: str

    attribute_id: str
    """属性ID

    Notes:
        APIレスポンスの ``additional_data_definition_id`` に相当します。
        ``additional_data_definition_id`` という名前がアノテーションJSONの `attributes` と対応していることが分かりにくかったので、`attribute_id`という名前に変えました。
    """
    attribute_name_en: Optional[str]
    attribute_name_ja: Optional[str]
    attribute_name_vi: Optional[str]
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

    def print_annotation_specs_label(self, annotation_specs_v3: dict[str, Any], output_format: FormatArgument, output: Optional[str] = None) -> None:
        # アノテーション仕様のv2とv3はほとんど同じなので、`convert_annotation_specs_labels_v2_to_v1`にはV3のアノテーション仕様を渡す
        label_attribute_list = create_label_attribute_list(annotation_specs_v3["labels"], annotation_specs_v3["additionals"])

        if output_format == FormatArgument.CSV:
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

        elif output_format in [FormatArgument.JSON, FormatArgument.PRETTY_JSON]:
            print_according_to_format([e.to_dict() for e in label_attribute_list], format=output_format, output=output)

    def get_history_id_from_before_index(self, project_id: str, before: int) -> Optional[str]:
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
                # args.beforeがNoneならば、必ずargs.history_idはNoneでない
                history_id = args.history_id

            annotation_specs, _ = self.service.api.get_annotation_specs(args.project_id, query_params={"history_id": history_id, "v": "3"})

        elif args.annotation_specs_json is not None:
            with args.annotation_specs_json.open() as f:
                annotation_specs = json.load(f)

        else:
            raise RuntimeError("'--project_id'か'--annotation_specs_json'のどちらかを指定する必要があります。")

        self.print_annotation_specs_label(annotation_specs, output_format=FormatArgument(args.format), output=args.output)


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
        type=int,
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
        choices=[FormatArgument.CSV.value, FormatArgument.JSON.value, FormatArgument.PRETTY_JSON.value],
        default=FormatArgument.CSV.value,
        help="出力フォーマット ",
    )

    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PrintAnnotationSpecsLabelAndAttribute(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_label_attribute"

    subcommand_help = "アノテーション仕様のラベルとラベルに含まれている属性の一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
