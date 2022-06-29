"""
アノテーション仕様を出力する
"""

import argparse
import logging
import sys
from typing import Any, Dict, List, Optional

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade, convert_annotation_specs_labels_v2_to_v1

logger = logging.getLogger(__name__)


class PrintAnnotationSpecsLabel(AbstractCommandLineInterface):
    """
    アノテーション仕様を出力する
    """

    COMMON_MESSAGE = "annofabcli annotation_specs list_label: error:"

    def print_annotation_specs_label(
        self, project_id: str, arg_format: str, output: Optional[str] = None, history_id: Optional[str] = None
    ):
        # [REMOVE_V2_PARAM]
        annotation_specs, _ = self.service.api.get_annotation_specs(
            project_id, query_params={"history_id": history_id, "v": "2"}
        )
        labels_v1 = convert_annotation_specs_labels_v2_to_v1(
            labels_v2=annotation_specs["labels"], additionals_v2=annotation_specs["additionals"]
        )
        if arg_format == "text":
            self._print_text_format_labels(labels_v1, output=output)

        elif arg_format in [FormatArgument.JSON.value, FormatArgument.PRETTY_JSON.value]:
            annofabcli.common.utils.print_according_to_format(
                target=labels_v1, arg_format=FormatArgument(arg_format), output=output
            )

    @staticmethod
    def _get_name_list(messages: List[Dict[str, Any]]):
        """
        日本語名、英語名のリスト（サイズ2）を取得する。日本語名が先頭に格納されている。
        """
        ja_name = [e["message"] for e in messages if e["lang"] == "ja-JP"][0]
        en_name = [e["message"] for e in messages if e["lang"] == "en-US"][0]
        return [ja_name, en_name]

    @staticmethod
    def _print_text_format_labels(labels, output: Optional[str] = None):
        output_lines = []
        for label in labels:
            output_lines.append(
                "\t".join(
                    [label["label_id"], label["annotation_type"]]
                    + PrintAnnotationSpecsLabel._get_name_list(label["label_name"]["messages"])
                )
            )
            for additional_data_definition in label["additional_data_definitions"]:
                output_lines.append(
                    "\t".join(
                        [
                            "",
                            additional_data_definition["additional_data_definition_id"],
                            additional_data_definition["type"],
                        ]
                        + PrintAnnotationSpecsLabel._get_name_list(additional_data_definition["name"]["messages"])
                    )
                )
                if additional_data_definition["type"] in ["choice", "select"]:
                    for choice in additional_data_definition["choices"]:
                        output_lines.append(
                            "\t".join(
                                ["", "", choice["choice_id"], ""]
                                + PrintAnnotationSpecsLabel._get_name_list(choice["name"]["messages"])
                            )
                        )

        annofabcli.common.utils.output_string("\n".join(output_lines), output)

    def get_history_id_from_before_index(self, project_id: str, before: int) -> Optional[str]:
        histories, _ = self.service.api.get_annotation_specs_histories(project_id)
        if before + 1 > len(histories):
            logger.warning(f"アノテーション仕様の履歴は{len(histories)}個のため、最新より{before}個前のアノテーション仕様は見つかりませんでした。")
            return None
        history = histories[-(before + 1)]
        logger.info(
            f"{history['updated_datetime']}のアノテーション仕様を出力します。"
            f"history_id={history['history_id']}, comment={history['comment']}"
        )
        return history["history_id"]

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
    PrintAnnotationSpecsLabel(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "list_label"

    subcommand_help = "アノテーション仕様のラベル情報を出力する"

    description = "アノテーション仕様のラベル情報を出力する"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
