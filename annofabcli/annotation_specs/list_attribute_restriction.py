"""
アノテーション仕様を出力する
"""

import argparse
import logging
import sys
from typing import Any, Collection, Dict, List, Optional

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
from annofabcli.common.facade import convert_annotation_specs_labels_v2_to_v1
import annofabapi
from more_itertools import first_true
logger = logging.getLogger(__name__)


class ListAttributeRestrictionMain:
    """
    アノテーション仕様の制約を自然言語で出力します。

    Args:
        labels: アノテーション仕様のラベル情報
        additionals: アノテーション仕様の属性情報

    """
    def __init__(self, labels:list[dict[str,Any]], additionals:list[dict[str,Any]]):
        self.attribute_dict = {e["additional_data_definition_id"]:e for e in additionals}
        self.label_dict = {e["label_id"]:e for e in labels}


    def get_labels_text(self, label_ids:Collection[str]) -> str:
        label_message_list = []
        for label_id in label_ids:
            label = self.label_dict.get(label_id)
            label_name = AnnofabApiFacade.get_label_name_en(label) if label is not None else ""
            label_message_list.append(f"'{label_name}'(id='{label_id}')")

        return ", ".join(label_message_list)

    def get_object_for_equals_or_notequals(self, value:str, attribute:Optional[dict[str,Any]]) -> str:
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
            choice = first_true(choices, pred=lambda e:e["choice_id"] == value)
            if choice is not None:
                choice_name = AnnofabApiFacade.get_choice_name_en(choice)
                return f"'{choice_name}'(id='{value}')"
            else:
                return f"''(id='{value}')"
        else:
            return f"'{value}'"

    def get_restriction_text(self, attribute_id:str, condition:dict[str,Any]) -> str:
        attribute = self.attribute_dict.get(attribute_id)

        if attribute is not None:
            subject = f"'{AnnofabApiFacade.get_additional_data_definition_name_en(attribute)}'(id='{attribute_id}',type='{attribute['type']}')"
        else:
            subject = f"''(id='{attribute_id}')"

        type = condition["_type"]

        if type == "CanInput":
            verb = "can input" if condition["enable"] else "can not input"
            object = ""

        elif type == "HasLabel":
            verb = "has label"
            object = self.get_labels_text(condition["labels"])

        elif type == "Equals":
            verb = "equals"
            object = self.get_object_for_equals_or_notequals(condition["value"], attribute)

        elif type == "NotEquals":
            verb = "does not equal"
            object = self.get_object_for_equals_or_notequals(condition["value"], attribute)

        elif type == "Matches":
            verb = "matches"
            object = condition["value"]

        elif type == "NotMatches":
            verb = "does not match"
            object = condition["value"]

        else:
            pass
            # 相関制約の話
        # {
        #     "additional_data_definition_id": "26874d1a-1017-46e4-bf22-131a733c7233",
        #     "condition": {
        #         "_type": "Imply",
        #         "premise": {
        #             "additional_data_definition_id": "a85ea588-fc48-48d3-a597-e97df919ab3c",
        #             "condition": {
        #                 "_type": "Equals",
        #                 "value": "true"
        #             }
        #         },
        #         "condition": {
        #             "_type": "NotEquals",
        #             "value": "true"
        #         }
        #     }
        # }

        return f"{subject} {verb} {object}"



class ListAttributeRestriction(AbstractCommandLineInterface):
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
            annofabcli.utils.print_according_to_format(
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

        annofabcli.utils.output_string("\n".join(output_lines), output)

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
    PrintAnnotationSpecsLabel(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "list_restriction"

    subcommand_help = "アノテーション仕様の属性の制約情報を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
