from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

import annofabcli
import annofabcli.common.cli
from annofabcli.annotation_specs.attribute_restriction import AttributeRestrictionMessage, OutputFormat
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class ListAttributeRestriction(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs list_restriction: error:"

    def get_history_id_from_before_index(self, project_id: str, before: int) -> Optional[str]:
        histories, _ = self.service.api.get_annotation_specs_histories(project_id)
        if before + 1 > len(histories):
            logger.warning(f"アノテーション仕様の履歴は{len(histories)}個のため、最新より{before}個前のアノテーション仕様は見つかりませんでした。")
            return None
        history = histories[-(before + 1)]
        return history["history_id"]

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
        elif args.annotation_json_path is not None:
            with args.annotation_json_path.open() as f:
                annotation_specs = json.load(f)

        else:
            raise RuntimeError("'--project_id'か'--annotation_specs_json'のどちらかを指定する必要があります。")

        main_obj = AttributeRestrictionMessage(
            labels=annotation_specs["labels"],
            additionals=annotation_specs["additionals"],
            output_format=OutputFormat(args.format),
        )
        target_attribute_names = get_list_from_args(args.attribute_name) if args.attribute_name is not None else None
        target_label_names = get_list_from_args(args.label_name) if args.label_name is not None else None
        restriction_text_list = main_obj.get_restriction_text_list(
            annotation_specs["restrictions"],
            target_attribute_names=target_attribute_names,
            target_label_names=target_label_names,
        )

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
        choices=[e.value for e in OutputFormat],
        default=OutputFormat.TEXT.value,
        help=f"出力フォーマット\n\n* {OutputFormat.TEXT.value}: 英語名のみ出力する形式\n* {OutputFormat.DETAILED_TEXT.value}: 属性IDや属性種類などの詳細情報を出力する形式\n",
    )

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAttributeRestriction(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_attribute_restriction"

    subcommand_help = "アノテーション仕様の属性の制約情報を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
