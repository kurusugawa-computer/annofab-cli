"""
検査コメント一覧を出力する。
"""

import argparse
import json
import logging
import sys
from typing import Callable, List, Optional

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

    def filter_inspection_list(
        self,
        inspection_list: List[Inspection],
        task_id_list: Optional[List[str]] = None,
        arg_filter_inspection: Optional[FilterInspectionFunc] = None,
    ) -> List[Inspection]:
        """
        引数の検査コメント一覧に`commenter_username`など、ユーザが知りたい情報を追加する。

        Args:
            inspection_list: 検査コメント一覧
            filter_inspection: 検索コメントを絞り込むための関数

        Returns:
            情報が追加された検査コメント一覧
        """

        def filter_task_id(e):
            if task_id_list is None or len(task_id_list) == 0:
                return True
            return e["task_id"] in task_id_list

        def filter_inspection(e):
            if arg_filter_inspection is None:
                return True
            return arg_filter_inspection(e)

        inspection_list = [e for e in inspection_list if filter_inspection(e) and filter_task_id(e)]
        return [self.visualize.add_properties_to_inspection(e) for e in inspection_list]

    def print_inspections(
        self,
        project_id: str,
        task_id_list: List[str],
        filter_inspection: Optional[FilterInspectionFunc] = None,
        inspection_list_from_json: Optional[List[Inspection]] = None,
    ):
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

        if inspection_list_from_json is None:
            inspection_list = self.get_inspections(
                project_id, task_id_list=task_id_list, filter_inspection=filter_inspection
            )

        else:
            inspection_list = self.filter_inspection_list(
                inspection_list_from_json, task_id_list=task_id_list, arg_filter_inspection=filter_inspection
            )

        logger.info(f"検査コメントの件数: {len(inspection_list)}")

        self.print_according_to_format(inspection_list)

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

    def get_inspections(
        self, project_id: str, task_id_list: List[str], filter_inspection: Optional[FilterInspectionFunc] = None
    ) -> List[Inspection]:
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
                input_data_id_list = task["input_data_id_list"]
                logger.info(f"タスク '{task_id}' に紐づく検査コメントを取得します。input_dataの個数 = {len(input_data_id_list)}")
                for input_data_index, input_data_id in enumerate(input_data_id_list):

                    inspections = self.get_inspections_by_input_data(
                        project_id, task_id, input_data_id, input_data_index
                    )

                    if filter_inspection is not None:
                        inspections = [e for e in inspections if filter_inspection(e)]

                    all_inspections.extend(inspections)

            except requests.HTTPError as e:
                logger.warning(e)
                logger.warning(f"タスク task_id = {task_id} の検査コメントを取得できなかった。")

        return all_inspections

    @staticmethod
    def validate(args: argparse.Namespace):
        if args.inspection_comment_json is None and args.task_id is None:
            print(
                "annofabcli inspection_comment list: error: argument -t/--task_id: "
                "`--inspection_comment_json`を指定しないときは、必須です。",
                file=sys.stderr,
            )
            return False
        else:
            return True

    def main(self):
        args = self.args
        if not self.validate(args):
            return

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        if args.inspection_comment_json is not None:
            with open(args.inspection_comment_json, encoding="utf-8") as f:
                inspection_list = json.load(f)
        else:
            inspection_list = None

        self.print_inspections(args.project_id, task_id_list, inspection_list_from_json=inspection_list)


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id(
        required=False,
        help_message="対象のタスクのtask_idを指定します。　"
        "`--inspection_comment_json`を指定しないときは、必須です。"
        "`file://`を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "--inspection_comment_json",
        type=str,
        help="検査コメント情報が記載されたJSONファイルのパスを指定すると、JSONに記載された情報を元に検査コメント一覧を出力します。AnnoFabから検査コメント情報を取得しません。"
        "JSONには記載されていない、`commenter_username	`や`phrase_names_ja`などの情報も追加します。"
        "JSONファイルは`$ annofabcli project download inspection_comment`コマンドで取得できます。",
    )

    argument_parser.add_format(
        choices=[
            FormatArgument.CSV,
            FormatArgument.JSON,
            FormatArgument.PRETTY_JSON,
            FormatArgument.INSPECTION_ID_LIST,
        ],
        default=FormatArgument.CSV,
    )
    argument_parser.add_output()
    argument_parser.add_csv_format()
    argument_parser.add_query()

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PrintInspections(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list"

    subcommand_help = "検査コメント一覧を出力します。"

    description = "検査コメント一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
