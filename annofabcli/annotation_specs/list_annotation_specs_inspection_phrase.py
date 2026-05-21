from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas
from annofabapi.models import Lang
from annofabapi.util.annotation_specs import get_message_with_lang
from dataclasses_json import DataClassJsonMixin

import annofabcli.common.cli
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
class FlattenInspectionPhrase(DataClassJsonMixin):
    """
    定型指摘情報を格納するクラスです。
    """

    inspection_phrase_id: str
    """定型指摘ID"""
    inspection_phrase_text_en: str | None
    """定型指摘の本文（英語）"""
    inspection_phrase_text_ja: str | None
    """定型指摘の本文（日本語）"""
    inspection_phrase_text_vi: str | None
    """定型指摘の本文（ベトナム語）"""


def create_inspection_phrase_list(inspection_phrases_v3: list[dict[str, Any]]) -> list[FlattenInspectionPhrase]:
    """
    APIから取得した定型指摘情報（v3版）から、`FlattenInspectionPhrase`のlistを生成します。

    Args:
        inspection_phrases_v3: APIから取得した定型指摘情報（v3版）
    """

    def dict_inspection_phrase_to_dataclass(inspection_phrase: dict[str, Any]) -> FlattenInspectionPhrase:
        """
        辞書の定型指摘情報をDataClassの定型指摘情報に変換します。
        """
        text = inspection_phrase["text"]
        return FlattenInspectionPhrase(
            inspection_phrase_id=inspection_phrase["id"],
            inspection_phrase_text_en=get_message_with_lang(text, lang=Lang.EN_US),
            inspection_phrase_text_ja=get_message_with_lang(text, lang=Lang.JA_JP),
            inspection_phrase_text_vi=get_message_with_lang(text, lang=Lang.VI_VN),
        )

    return [dict_inspection_phrase_to_dataclass(e) for e in inspection_phrases_v3]


class PrintAnnotationSpecsInspectionPhrase(CommandLine):
    """
    アノテーション仕様の定型指摘情報を出力する。
    """

    COMMON_MESSAGE = "annofabcli annotation_specs list_inspection_phrase: error:"

    def print_annotation_specs_inspection_phrase(self, annotation_specs_v3: dict[str, Any], output_format: OutputFormat, output: str | None = None) -> None:
        inspection_phrase_list = create_inspection_phrase_list(annotation_specs_v3["inspection_phrases"])
        logger.info(f"{len(inspection_phrase_list)} 件の定型指摘情報を出力します。")

        if output_format == OutputFormat.CSV:
            columns = [
                "inspection_phrase_id",
                "inspection_phrase_text_en",
                "inspection_phrase_text_ja",
                "inspection_phrase_text_vi",
            ]
            df = pandas.DataFrame(inspection_phrase_list, columns=columns)
            print_csv(df, output)

        elif output_format in [OutputFormat.JSON, OutputFormat.PRETTY_JSON]:
            print_according_to_format([e.to_dict() for e in inspection_phrase_list], format=output_format, output=output)

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

        elif args.annotation_specs_json is not None:
            with args.annotation_specs_json.open() as f:
                annotation_specs = json.load(f)

        else:
            raise RuntimeError("'--project_id'か'--annotation_specs_json'のどちらかを指定する必要があります。")

        self.print_annotation_specs_inspection_phrase(annotation_specs, output_format=OutputFormat(args.format), output=args.output)


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    required_group = parser.add_mutually_exclusive_group(required=True)
    required_group.add_argument("-p", "--project_id", help="対象のプロジェクトのproject_idを指定します。APIで取得したアノテーション仕様情報を元に出力します。")
    required_group.add_argument(
        "--annotation_specs_json",
        type=Path,
        help="指定したアノテーション仕様のJSONファイルを指定します。JSONファイルに記載された情報を元に出力します。ただしアノテーション仕様の ``format_version`` は ``3`` である必要があります。",
    )

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
    PrintAnnotationSpecsInspectionPhrase(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_inspection_phrase"

    subcommand_help = "アノテーション仕様の定型指摘情報を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
