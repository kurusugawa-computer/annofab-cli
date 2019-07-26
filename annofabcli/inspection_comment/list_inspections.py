"""
検査コメント一覧を出力する。
"""

import argparse
import logging
from typing import Any, Callable, Dict, List, Optional  # pylint: disable=unused-import

import annofabapi
import requests
from annofabapi.models import Inspection

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)

FilterInspectionFunc = Callable[[Inspection], bool]


class PrintInspections(AbstractCommandLineInterface):
    """
    検査コメント一覧を出力する。
    """
    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)

    def print_inspections(self, project_id: str, task_id_list: List[str], arg_format: str, output: Optional[str] = None,
                          csv_format: Optional[Dict[str, Any]] = None,
                          filter_inspection: Optional[FilterInspectionFunc] = None):
        """
        検査コメントを出力する

        Args:
            project_id: 対象のproject_id
            task_id_list: 受け入れ完了にするタスクのtask_idのList
            inspection_comment: 絞り込み条件となる、検査コメントの中身
            commenter_user_id: 絞り込み条件となる、検査コメントを付与したユーザのuser_id
            filter_inspection: 検索コメントを絞り込むための関数

        Returns:

        """

        inspections = self.get_inspections(project_id, task_id_list, filter_inspection=filter_inspection)
        inspections = self.search_with_jmespath_expression(inspections)

        logger.info(f"検査コメントの件数: {len(inspections)}")

        annofabcli.utils.print_according_to_format(target=inspections, arg_format=FormatArgument(arg_format),
                                                   output=output, csv_format=csv_format)

    def get_inspections_by_input_data(self, project_id: str, task_id: str, input_data_id: str, input_data_index: int):
        """入力データごとに検査コメント一覧を取得する。

        Args:
            project_id:
            task_id:
            input_data_id:
            input_data_index: タスク内のinput_dataの番号

        Returns:
            対象の検査コメント一覧
        """

        detail = {"input_data_index": input_data_index}
        inspectins, _ = self.service.api.get_inspections(project_id, task_id, input_data_id)
        return [self.visualize.add_properties_to_inspection(e, detail) for e in inspectins]

    def get_inspections(self, project_id: str, task_id_list: List[str],
                        filter_inspection: Optional[FilterInspectionFunc] = None) -> List[Inspection]:
        """検査コメント一覧を取得する。

        Args:
            project_id:
            task_id_list:

        Returns:
            対象の検査コメント一覧
        """

        all_inspections: List[Inspection] = []
        for task_id in task_id_list:
            try:
                task, _ = self.service.api.get_task(project_id, task_id)

                for input_data_index, input_data_id in enumerate(task["input_data_id_list"]):

                    inspections = self.get_inspections_by_input_data(project_id, task_id, input_data_id,
                                                                     input_data_index)

                    if filter_inspection is not None:
                        inspections = [e for e in inspections if filter_inspection(e)]

                    all_inspections.extend(inspections)

            except requests.HTTPError as e:
                logger.warning(e)
                logger.warning(f"タスク task_id = {task_id} の検査コメントを取得できなかった。")

        return all_inspections

    def main(self):
        args = self.args
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        csv_format = annofabcli.common.cli.get_csv_format_from_args(args.csv_format)

        self.print_inspections(args.project_id, task_id_list, arg_format=args.format, output=args.output,
                               csv_format=csv_format)


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()
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
    PrintInspections(service, facade, args).main()


def add_parser_deprecated(subparsers: argparse._SubParsersAction):
    subcommand_name = "print_inspections"

    subcommand_help = "検査コメント一覧を出力します。"

    description = "検査コメント一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list"

    subcommand_help = "検査コメント一覧を出力します。"

    description = "検査コメント一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
