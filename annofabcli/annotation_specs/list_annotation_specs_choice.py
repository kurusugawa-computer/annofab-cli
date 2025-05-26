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
from annofabapi.util.annotation_specs import get_english_message, get_message_with_lang
from dataclasses_json import DataClassJsonMixin

import annofabcli
import annofabcli.common.cli
from annofabcli.common.annofab.annotation_specs import keybind_to_text
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
class FlattenChoice(DataClassJsonMixin):
    """
    CSV用の選択肢情報を格納するクラスです。
    """

    attribute_id: str
    """
    属性ID
    どの属性に属しているか分かるようにするため追加した。
    """

    attribute_name_en: Optional[str]
    """
    属性名（英語）
    どの属性に属しているか分かるようにするため追加した。
    """

    attribute_type: str
    """属性の種類"""
    choice_id: str
    choice_name_en: Optional[str]
    choice_name_ja: Optional[str]
    choice_name_vi: Optional[str]
    is_default: bool
    """初期値として設定されているかどうか"""
    keybind: Optional[str]
    """キーバインド"""


def create_flatten_choice_list_from_additionals(additionals_v3: list[dict[str, Any]]) -> list[FlattenChoice]:
    """
    APIから取得した属性情報（v3版）から、選択肢情報の一覧を生成します。

    Args:
        additionals_v3: APIから取得した属性情報（v3版）
    """

    def dict_choice_to_dataclass(
        choice: dict[str, Any],
        additional: dict[str, Any],
    ) -> FlattenChoice:
        """
        辞書の選択肢情報をDataClassの選択肢情報に変換します。
        """
        attribute_id = additional["additional_data_definition_id"]
        additional_name = additional["name"]

        choice_id = choice["choice_id"]
        choice_name = choice["name"]
        is_default = additional["default"] == choice_id
        return FlattenChoice(
            attribute_id=attribute_id,
            attribute_name_en=get_english_message(additional_name),
            attribute_type=additional["type"],
            choice_id=choice_id,
            choice_name_en=get_message_with_lang(choice_name, lang=Lang.EN_US),
            choice_name_ja=get_message_with_lang(choice_name, lang=Lang.JA_JP),
            choice_name_vi=get_message_with_lang(choice_name, lang=Lang.VI_VN),
            is_default=is_default,
            keybind=keybind_to_text(choice["keybind"]),
        )

    tmp_list = []
    for additional in additionals_v3:
        choices = additional["choices"]
        if len(choices) == 0:
            continue
        for choice in choices:
            tmp_list.append(dict_choice_to_dataclass(choice, additional))  # noqa: PERF401
    return tmp_list


class PrintAnnotationSpecsAttribute(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs list_choice: error:"

    def print_annotation_specs_choice(self, annotation_specs_v3: dict[str, Any], output_format: FormatArgument, output: Optional[str] = None) -> None:
        choice_list = create_flatten_choice_list_from_additionals(annotation_specs_v3["additionals"])
        logger.info(f"{len(choice_list)} 件の選択肢情報を出力します。")

        if output_format == FormatArgument.CSV:
            df = pandas.DataFrame(choice_list)
            columns = [
                "attribute_id",
                "attribute_name_en",
                "attribute_type",
                "choice_id",
                "choice_name_en",
                "choice_name_ja",
                "choice_name_vi",
                "is_default",
                "keybind",
            ]
            print_csv(df[columns], output)

        elif output_format in [FormatArgument.JSON, FormatArgument.PRETTY_JSON]:
            print_according_to_format([e.to_dict() for e in choice_list], format=output_format, output=output)

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
                history_id = args.history_id

            annotation_specs, _ = self.service.api.get_annotation_specs(args.project_id, query_params={"history_id": history_id, "v": "3"})

        elif args.annotation_specs_json is not None:
            with args.annotation_specs_json.open() as f:
                annotation_specs = json.load(f)

        else:
            raise RuntimeError("'--project_id'か'--annotation_specs_json'のどちらかを指定する必要があります。")

        self.print_annotation_specs_choice(annotation_specs, output_format=FormatArgument(args.format), output=args.output)


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
    PrintAnnotationSpecsAttribute(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_choice"

    subcommand_help = "アノテーション仕様のドロップダウンまたはラジオボタン属性の選択肢情報を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
