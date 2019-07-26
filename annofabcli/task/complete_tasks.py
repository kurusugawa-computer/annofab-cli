import argparse
import logging
import time
from typing import Any, Callable, Dict, List, Optional  # pylint: disable=unused-import

import requests
from annofabapi.models import InputDataId, Inspection, ProjectMemberRole, Task, TaskId

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)

InspectionJson = Dict[TaskId, Dict[InputDataId, List[Inspection]]]


class ComleteTasks(AbstractCommandLineInterface):
    """
    タスクを受け入れ完了にする
    """
    @staticmethod
    def inspection_list_to_dict(inspection_list: List[Inspection]) -> InspectionJson:
        """
        検査コメントのListを、Dict[TaskId, Dict[InputDataId, List[Inspection]]] の形式に変換する。

        """
        task_dict = {}
        for inspection in inspection_list:
            task_id = inspection['task_id']
            input_data_dict = task_dict.get(task_id, default={})

            input_data_id = inspection['input_data_id']
            l = input_data_dict.get(input_data_id, default=[])
            l.append(inspection)
            input_data_dict[input_data_id] = l

            task_dict[task_id] = input_data_dict

        return task_dict

    def complete_tasks_with_changing_inspection_status(self, project_id: str, task_id_list: List[str],
                                                       inspection_status: str, inspection_list: List[Inspection]):
        """
        検査コメントのstatusを変更（対応完了 or 対応不要）にした上で、タスクを受け入れ完了状態にする
        Args:
            project_id: 対象のproject_id
            task_id_list: 受け入れ完了にするタスクのtask_idのList
            inspection_status: 変更後の検査コメントの状態
            inspection_json: 変更対象の検査コメントのJSON情報

        """

        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])

        account_id = self.facade.get_my_account_id()

        inspection_json = self.inspection_list_to_dict(inspection_list)

        for task_id in task_id_list:
            task, _ = self.service.api.get_task(project_id, task_id)
            if task["phase"] != "acceptance":
                logger.warning(f"task_id: {task_id}, phase: {task['phase']} ")
                continue

            # 担当者変更
            try:
                self.facade.change_operator_of_task(project_id, task_id, account_id)
                self.facade.change_to_working_phase(project_id, task_id, account_id)
                logger.debug(f"{task_id}: 担当者を変更した")

            except requests.HTTPError as e:
                logger.warning(e)
                logger.warning(f"{task_id} の担当者変更に失敗")

            # 担当者変更してから数秒待たないと、検査コメントの付与に失敗する(「検査コメントの作成日時が不正です」と言われる）
            time.sleep(3)

            # 検査コメントを付与して、タスクを受け入れ完了にする
            try:
                self.complete_acceptance_task(project_id, task, inspection_status, inspection_json, account_id)
            except requests.HTTPError as e:
                logger.warning(e)
                logger.warning(f"{task_id} の受入完了に失敗")

                self.facade.change_to_break_phase(project_id, task_id, account_id)
                continue

    def update_status_of_inspections(self, project_id: str, task_id: str, input_data_id: str,
                                     inspection_json: InspectionJson, inspection_status: str):
        target_insepctions = inspection_json.get(task_id, {}).get(input_data_id)

        if target_insepctions is None or len(target_insepctions) == 0:
            logger.warning(f"変更対象の検査コメントはなかった。task_id = {task_id}, input_data_id = {input_data_id}")
            return

        target_inspection_id_list = [inspection["inspection_id"] for inspection in target_insepctions]

        def filter_inspection(arg_inspection: Inspection) -> bool:
            """
            statusを変更する検査コメントの条件。
            """

            return arg_inspection["inspection_id"] in target_inspection_id_list

        self.service.wrapper.update_status_of_inspections(project_id, task_id, input_data_id, filter_inspection,
                                                          inspection_status)
        logger.debug(f"{task_id}, {input_data_id}, {len(target_insepctions)}件 検査コメントの状態を変更")

    def complete_acceptance_task(self, project_id: str, task: Task, inspection_status: str,
                                 inspection_json: InspectionJson, account_id: str):
        """
        検査コメントのstatusを変更（対応完了 or 対応不要）にした上で、タスクを受け入れ完了状態にする
        """

        task_id = task["task_id"]

        # 検査コメントの状態を変更する
        for input_data_id in task["input_data_id_list"]:
            self.update_status_of_inspections(project_id, task_id, input_data_id, inspection_json, inspection_status)

        # タスクの状態を検査する
        if self.validate_task(project_id, task_id):
            self.facade.complete_task(project_id, task_id, account_id)
            logger.info(f"{task_id}: タスクを受入完了にした")
        else:
            logger.warning(f"{task_id}, タスク検査で警告/エラーがあったので、タスクを受入完了できなかった")
            self.facade.change_to_break_phase(project_id, task_id, account_id)

    def validate_task(self, project_id: str, task_id: str) -> bool:
        # Validation
        validation, _ = self.service.api.get_task_validation(project_id, task_id)
        validation_inputs = validation["inputs"]
        is_valid = True
        for validation in validation_inputs:
            input_data_id = validation["input_data_id"]
            inspection_summary = validation["inspection_summary"]
            if inspection_summary in ["unprocessed", "new_unprocessed_inspection"]:
                logger.warning(f"{task_id}, {input_data_id}, {inspection_summary}, 未処置の検査コメントがある。")
                is_valid = False

            annotation_summaries = validation["annotation_summaries"]
            if len(annotation_summaries) > 0:
                logger.warning(
                    f"{task_id}, {input_data_id}, {inspection_summary}, アノテーションにエラーがある。{annotation_summaries}")
                is_valid = False

        return is_valid

    def main(self):
        args = self.args
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

        inspection_list = annofabcli.common.cli.get_json_from_args(args.inspection_list)

        self.complete_tasks_with_changing_inspection_status(args.project_id, task_id_list, args.inspection_status,
                                                            inspection_list)


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    parser.add_argument(
        '--inspection_list', type=str, required=True, help='未処置の検査コメントの一覧を指定してください。指定された検査コメントの状態が変更されます。'
        '検査コメントの一覧は `inspection_comment list_unprocessed` コマンドで出力できます。')

    parser.add_argument('--inspection_status', type=str, required=True,
                        choices=["error_corrected", "no_correction_required"], help='未処置の検査コメントをどの状態に変更するか。'
                        'error_corrected: 対応完了,'
                        'no_correction_required: 対応不要')

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    ComleteTasks(service, facade, args).main()


def add_parser_deprecated(subparsers: argparse._SubParsersAction):
    subcommand_name = "complete_tasks"
    subcommand_help = "未処置の検査コメントを適切な状態に変更して、タスクを受け入れ完了にする。"
    description = ("未処置の検査コメントを適切な状態に変更して、タスクを受け入れ完了にする。" "オーナ権限を持つユーザで実行すること。")
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "complete"
    subcommand_help = "未処置の検査コメントを適切な状態に変更して、タスクを受け入れ完了にする。"
    description = ("未処置の検査コメントを適切な状態に変更して、タスクを受け入れ完了にする。" "オーナ権限を持つユーザで実行すること。")
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
