"""
タスクを一括で受け入れ完了にする
"""

import argparse
import json
import logging
from typing import Any, Callable, Dict, List, Optional  # pylint: disable=unused-import

import annofabapi
from annofabapi.models import Inspection, ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class PrintUnprocessedInspections(AbstractCommandLineInterface):
    """
    検査コメントIDのList(task_id, input_data_idごと)を出力する
    """

    def get_unprocessed_inspections(self, project_id: str, task_id: str, input_data_id: str,
                                    inspection_comment: Optional[str] = None,
                                    commenter_account_id: Optional[str] = None):
        """
        対象の検査コメント一覧を取得する

        Args:
            project_id:
            task_id:
            input_data_id:
            inspection_comment:
            commenter_account_id:

        Returns:
            対象の検査コメント一覧
        """

        def filter_inspection(arg_inspection: Inspection) -> bool:
            # 未処置コメントのみ、変更する
            if arg_inspection["status"] != "annotator_action_required":
                return False

            # 返信コメントを除く
            if arg_inspection["parent_inspection_id"] is not None:
                return False

            if commenter_account_id is not None:
                if arg_inspection["commenter_account_id"] != commenter_account_id:
                    return False

            if inspection_comment is not None:
                if arg_inspection["comment"] != inspection_comment:
                    return False

            return True

        inspectins, _ = self.service.api.get_inspections(project_id, task_id, input_data_id)
        return [i for i in inspectins if filter_inspection(i)]

    def print_unprocessed_inspections(self, project_id: str, task_id_list: List[str],
                                      inspection_comment: Optional[str] = None,
                                      commenter_user_id: Optional[str] = None):
        """
        未処置の検査コメントを出力する。

        Args:
            project_id: 対象のproject_id
            task_id_list: 受け入れ完了にするタスクのtask_idのList
            inspection_comment: 絞り込み条件となる、検査コメントの中身
            commenter_user_id: 絞り込み条件となる、検査コメントを付与したユーザのuser_id

        Returns:

        """

        commenter_account_id = self.facade.get_account_id_from_user_id(
            project_id, commenter_user_id) if (commenter_user_id is not None) else None

        task_dict = {}

        for task_id in task_id_list:
            task, _ = self.service.api.get_task(project_id, task_id)

            input_data_dict = {}
            for input_data_id in task["input_data_id_list"]:

                inspections = self.get_unprocessed_inspections(project_id, task_id, input_data_id,
                                                               inspection_comment=inspection_comment,
                                                               commenter_account_id=commenter_account_id)

                input_data_dict[input_data_id] = inspections

            task_dict[task_id] = input_data_dict

        # 出力
        print(json.dumps(task_dict, indent=2, ensure_ascii=False))

    def main(self, args):
        super().process_common_args(args, __file__, logger)

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

        self.print_unprocessed_inspections(args.project_id, task_id_list, args.inspection_comment,
                                           args.commenter_user_id)


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument('-p', '--project_id', type=str, required=True, help='対象のプロジェクトのproject_idを指定します。')

    parser.add_argument('-t', '--task_id', type=str, required=True, nargs='+',
                        help='対象のタスクのtask_idを指定します。`file://`を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。')

    parser.add_argument('-c', '--inspection_comment', type=str, help='絞り込み条件となる、検査コメントの中身。指定しない場合は絞り込まない。')

    parser.add_argument('-u', '--commenter_user_id', type=str, help='絞り込み条件となる、検査コメントを付与したユーザのuser_id。 指定しない場合は絞り込まない。')

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    PrintUnprocessedInspections(service, facade).main(args)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "print_unprocessed_inspections"

    subcommand_help = "未処置の検査コメントList(task_id, input_data_idごと)をJSONとして出力する。出力された内容は、`complete_tasks`ツールに利用する。"

    description = ("未処置の検査コメントList(task_id, input_data_idごと)をJSONとして出力する。"
                   "出力された内容は、`complete_tasks`ツールに利用する。"
                   "出力内容は`Dict[TaskId, Dict[InputDatId, List[Inspection]]]`である.")

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
