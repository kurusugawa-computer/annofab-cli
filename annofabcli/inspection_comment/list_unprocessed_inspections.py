"""
タスクを一括で受け入れ完了にする
"""

import argparse
import logging
from typing import Any, Callable, Dict, List, Optional  # pylint: disable=unused-import

from annofabapi.models import Inspection

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import ArgumentParser, FormatArgument, build_annofabapi_resource_and_login
from annofabcli.inspection_comment.list_inspections import PrintInspections

logger = logging.getLogger(__name__)


def create_filter_func(commenter_user_id: str, inspection_comment: str) -> Callable[[Inspection], bool]:
    def filter_inspection(arg_inspection: Inspection) -> bool:
        # 未処置コメントのみ、変更する
        if arg_inspection["status"] != "annotator_action_required":
            return False

        # 返信コメントを除く
        if arg_inspection["parent_inspection_id"] is not None:
            return False

        if commenter_user_id is not None:
            if arg_inspection["commenter_user_id"] != commenter_user_id:
                return False

        if inspection_comment is not None:
            if arg_inspection["comment"] != inspection_comment:
                return False

        return True

    return filter_inspection


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    parser.add_argument('--inspection_comment', type=str, help='絞り込み条件となる、検査コメントの中身。指定しない場合は絞り込まない。')

    parser.add_argument('--commenter_user_id', type=str, help='絞り込み条件となる、検査コメントを付与したユーザのuser_id。 指定しない場合は絞り込まない。')

    argument_parser.add_format(
        choices=[
            FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON, FormatArgument.INSPECTION_ID_LIST
        ], default=FormatArgument.CSV)
    argument_parser.add_output()
    argument_parser.add_csv_format()
    argument_parser.add_query()

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)

    task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
    csv_format = annofabcli.common.cli.get_csv_format_from_args(args.csv_format)

    filter_inspection = create_filter_func(args.commenter_user_id, args.inspection_comment)

    PrintInspections(service, facade, args).print_inspections(project_id=args.project_id, task_id_list=task_id_list,
                                                              arg_format=args.format, csv_format=csv_format,
                                                              output=args.output, filter_inspection=filter_inspection)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_unprocessed"

    subcommand_help = "未処置の検査コメント一覧を出力する。`task complete` コマンドに渡すデータを取得するのに利用する。"

    description = ("未処置の検査コメント一覧を出力する。`task complete` コマンドに渡すデータを取得するのに利用する。")

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)


def add_parser_deprecated(subparsers: argparse._SubParsersAction):
    subcommand_name = "print_unprocessed_inspections"

    subcommand_help = "未処置の検査コメントList(task_id, input_data_idごと)をJSONとして出力する。出力された内容は、`complete_tasks`ツールに利用する。"

    description = ("未処置の検査コメントList(task_id, input_data_idごと)をJSONとして出力する。"
                   "出力された内容は、`complete_tasks`ツールに利用する。"
                   "出力内容は`Dict[TaskId, Dict[InputDatId, List[Inspection]]]`である.")

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
