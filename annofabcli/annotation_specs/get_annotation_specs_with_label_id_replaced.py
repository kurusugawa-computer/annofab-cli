from __future__ import annotations
import argparse
import logging
from multiprocessing.sharedctypes import Value
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

from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    AbstractCommandLineWithConfirmInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_json_from_args,
)
from typing import Collection

logger = logging.getLogger(__name__)


class ReplacingLabelId(AbstractCommandLineWithConfirmInterface):



    def replace_label_id_of_restrictions(self, old_label_id, new_label_id, restrictions:list[dict[str,Any]]) -> None:
        """
        制約情報の中で使用されているlabel_idを置換する。
        """
        def _replace_label_id_in_condition(condition:dict[str,Any]) -> None:
            """
            制約情報の中のlabel_idを置換する

            Args:

            """
            if condition["_type"] == "Imply":
                self._replace_label_id_of_restriction(old_label_id, new_label_id, condition["premise"]["condition"])
                self._replace_label_id_of_restriction(old_label_id, new_label_id, condition["condition"])
            elif condition["_type"] == "HasLabel":
                # アノテーションリンク先であるラベルIDを置換する
                labels = condition["labels"]
                try:
                    index = labels.index(old_label_id)
                    labels[index] = new_label_id
                except ValueError:
                    # old_label_idがlabelsになければ、何もしない
                    pass

        for restriction in restrictions:
            _replace_label_id_in_condition(restriction["condition"])


    def replace_label_id(self, label:dict[str,Any]) -> None:
        label_id = label["label_id"]
        label_name_en = AnnofabApiFacade.get_label_name_en(label)

        # TODO confirm
        # TODO validate

        label["label_id"] = label_name

        # TODO
        # アノテーションリンクと属性
        # HasLabel制約

    def main(self, annotation_specs:dict[str,Any], target_label_names:Optional[Collection[str]]=None) -> dict[str, Any]:
        label_list = annotation_specs["labels"]



class GetAnnotationSpecsWithLabelIdReplaced(AbstractCommandLineInterface):

    def main(self):

        args = self.args
        project_id: str = args.project_id
        super().validate_project(project_id)

        annotation_specs = self.service.api.get_annotation_specs(project_id, query_params={"v":3})

        target_task_ids = (
            set(annofabcli.common.cli.get_list_from_args(args.task_id)) if args.task_id is not None else None
        )


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

    parser.add_argument(
        "--label_name",
        type=str,
        nargs="+",
        help="置換対象のラベルの英語名",
    )

    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PrintAnnotationSpecsLabel(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "get_with_label_id_replaced_label_name"

    subcommand_help = "label_idをUUIDから英語名に置換したアノテーション仕様のJSONを取得します。"

    description =( "label_idをUUIDから英語名に置換したアノテーション仕様のJSONを取得します。\n"
            "アノテーション仕様は変更しません。画面のインポート機能を使って、アノテーション仕様を変更することを想定しています。\n"
            "【注意】既にアノテーションが存在する状態でlabel_idを変更すると、既存のアノテーション情報が消える恐れがあります。十分注意して、label_idを変更してください。")


    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
