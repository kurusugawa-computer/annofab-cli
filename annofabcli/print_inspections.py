"""
検査コメント一覧を出力する。
"""

import argparse
import json
import logging
from typing import Any, Callable, Dict, List, Optional  # pylint: disable=unused-import

import annofabapi
from annofabapi.models import Inspection
import json
import pandas

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.utils import build_annofabapi_resource_and_login
from annofabcli.common.cli import AbstractCommandLineInterface
from annofabcli.common.visualize import AddProps


logger = logging.getLogger(__name__)


class PrintInspections(AbstractCommandLineInterface):
    """
    検査コメント一覧を出力する。
    """


    def print_inspections(self, project_id: str, task_id_list: List[str], format: str, output: Optional[str]=None, csv_format: Optional[str] = None):
        """
        検査コメントを出力する

        Args:
            project_id: 対象のproject_id
            task_id_list: 受け入れ完了にするタスクのtask_idのList
            inspection_comment: 絞り込み条件となる、検査コメントの中身
            commenter_user_id: 絞り込み条件となる、検査コメントを付与したユーザのuser_id

        Returns:

        """

        inspections = self.get_inspections(project_id, task_id_list)

        if format == "json":
            annofabcli.utils.print_json(inspections, output)

        elif format == "csv":
            df = pandas.DataFrame(inspections)
            annofabcli.utils.print_csv(df, output, csv_format)


    def get_inspections_by_input_data(self, project_id: str, task_id: str, input_data_id: str):
        """
        入力データごとに検査コメント一覧を取得する。

        Args:
            project_id:
            task_id:
            input_data_id:

        Returns:
            対象の検査コメント一覧
        """

        inspectins, _ = self.service.api.get_inspections(project_id, task_id, input_data_id)
        return [self.visualize.add_properties_to_inspection(e) for e in inspectins]


    def get_inspections(self, project_id: str, task_id_list: List[str]) -> List[Inspection]:
        """
        検査コメント一覧を取得する。

        Args:
            project_id:
            task_id_list:

        Returns:
            対象の検査コメント一覧
        """

        all_inspections = []
        for task_id in task_id_list:
            try:
                task, _ = self.service.api.get_task(project_id, task_id)

                for input_data_id in task["input_data_id_list"]:

                    inspections = self.get_inspections_by_input_data(project_id, task_id, input_data_id)
                    all_inspections.extend(inspections)

            except Exception as e:
                logger.warning(e)
                logger.warning(f"タスク task_id = {task_id} の検査コメントが出力できなかった。")

        return all_inspections


    def main(self, args:argparse.Namespace):
        super().process_common_args(args, __file__, logger)
        task_id_list = annofabcli.utils.get_list_from_args(args.task_id)
        csv_format = annofabcli.utils.get_json_from_args(args.csv_format)

        self.visualize = AddProps(self.service, args.project_id)


        self.print_inspections(args.project_id, task_id_list, format=args.format, output=args.output, csv_format=csv_format)




def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument('-p', '--project_id', type=str, required=True, help='対象のプロジェクトのproject_idを指定します。')

    parser.add_argument('-t', '--task_id', type=str, required=True, nargs='+',
                        help='対象のタスクのtask_idを指定します。`file://`を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。')

    parser.add_argument('-f', '--format', type=str, choices=['csv','json'], default='csv', help='出力フォーマットを指定します。指定しない場合は、"csv"フォーマットになります。')

    parser.add_argument('-o', '--output', type=str, help='出力先のファイルパスを指定します。指定しない場合は、標準出力に出力されます。')

    parser.add_argument('--csv_format', type=str, default='{"encoding": "utf_8_sig", "index": true}',
                        help='CSVのフォーマットをJSON形式で指定します。`--format`が`csv`でないときは、このオプションは無視されます。'
                             '`file://`を先頭に付けると、JSON形式のファイルを指定できます。'
                             '指定した値は、[pandas.DataFrame.to_csv](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.to_csv.html) の引数として渡されます。'
                             )


    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    PrintInspections(service, facade).main(args)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "print_inspections"

    subcommand_help = "検査コメントを出力する。"

    description = "検査コメントを出力する。"

    parser = annofabcli.utils.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)


