import argparse
import logging
import time
from typing import Dict, List

import requests
from annofabapi.models import InputDataId, Inspection, InspectionStatus, ProjectMemberRole, Task, TaskId, TaskPhase

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
    def inspection_list_to_dict(all_inspection_list: List[Inspection]) -> InspectionJson:
        """
        検査コメントのListを、Dict[TaskId, Dict[InputDataId, List[Inspection]]] の形式に変換する。

        """
        task_dict: InspectionJson = {}
        for inspection in all_inspection_list:
            task_id = inspection["task_id"]
            input_data_dict: Dict[InputDataId, List[Inspection]] = task_dict.get(task_id, {})

            input_data_id = inspection["input_data_id"]
            inspection_list = input_data_dict.get(input_data_id, [])
            inspection_list.append(inspection)
            input_data_dict[input_data_id] = inspection_list

            task_dict[task_id] = input_data_dict

        return task_dict

    def complete_tasks_with_changing_inspection_status(
        self, project_id: str, inspection_status: InspectionStatus, inspection_list: List[Inspection]
    ):
        """
        検査コメントのstatusを変更（対応完了 or 対応不要）にした上で、タスクを受け入れ完了状態にする
        Args:
            project_id: 対象のproject_id
            inspection_status: 変更後の検査コメントの状態
            inspection_json: 変更対象の検査コメントのJSON情報

        """

        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])

        account_id = self.facade.get_my_account_id()

        inspection_json = self.inspection_list_to_dict(inspection_list)

        project_title = self.facade.get_project_title(project_id)
        logger.info(f"{project_title} のタスク{len(inspection_json)} 件を、受入完了状態にします。")
        for task_id, input_data_dict in inspection_json.items():
            try:
                task, _ = self.service.api.get_task(project_id, task_id)
                logger.info(f"タスク情報 task_id: {task_id}, phase: {task['phase']}, status: {task['status']}")

                if task["phase"] != TaskPhase.ACCEPTANCE.value:
                    logger.warning(f"task_id: {task_id} のタスクのphaseがacceptanceでない（ {task['phase']} ）ので、スキップします。")
                    continue

            except requests.HTTPError as e:
                logger.warning(e)
                logger.warning(f"{task_id} のタスクを取得できませんでした。")
                continue

            if not self.confirm_processing(f"タスク'{task_id}'の検査コメントを'{inspection_status.value}'状態にして、" f"受入完了状態にしますか？"):
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
                self.complete_acceptance_task(
                    project_id, task, inspection_status, input_data_dict=input_data_dict, account_id=account_id
                )
            except requests.HTTPError as e:
                logger.warning(e)
                logger.warning(f"{task_id} の受入完了に失敗")

                self.facade.change_to_break_phase(project_id, task_id, account_id)
                continue

    def update_status_of_inspections(
        self,
        project_id: str,
        task_id: str,
        input_data_id: str,
        inspection_list: List[Inspection],
        inspection_status: InspectionStatus,
    ):

        if inspection_list is None or len(inspection_list) == 0:
            logger.warning(f"変更対象の検査コメントはなかった。task_id = {task_id}, input_data_id = {input_data_id}")
            return

        target_inspection_id_list = [inspection["inspection_id"] for inspection in inspection_list]

        def filter_inspection(arg_inspection: Inspection) -> bool:
            """
            statusを変更する検査コメントの条件。
            """

            return arg_inspection["inspection_id"] in target_inspection_id_list

        self.service.wrapper.update_status_of_inspections(
            project_id, task_id, input_data_id, filter_inspection, inspection_status
        )
        logger.debug(f"{task_id}, {input_data_id}, {len(inspection_list)}件 検査コメントの状態を変更")

    def complete_acceptance_task(
        self,
        project_id: str,
        task: Task,
        inspection_status: InspectionStatus,
        input_data_dict: Dict[InputDataId, List[Inspection]],
        account_id: str,
    ):
        """
        検査コメントのstatusを変更（対応完了 or 対応不要）にした上で、タスクを受け入れ完了状態にする
        """

        task_id = task["task_id"]

        # 検査コメントの状態を変更する
        for input_data_id, inspection_list in input_data_dict.items():
            self.update_status_of_inspections(
                project_id, task_id, input_data_id, inspection_list=inspection_list, inspection_status=inspection_status
            )

        # タスクの状態を検査する
        self.facade.complete_task(project_id, task_id, account_id)
        logger.info(f"{task_id}: タスクを受入完了にした")

    def main(self):
        args = self.args

        inspection_list = annofabcli.common.cli.get_json_from_args(args.inspection_list)
        inspection_status = InspectionStatus(args.inspection_status)
        self.complete_tasks_with_changing_inspection_status(
            args.project_id, inspection_status=inspection_status, inspection_list=inspection_list
        )


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--inspection_list",
        type=str,
        required=True,
        help=(
            "未処置の検査コメントの一覧をJSON形式で指定します。指定された検査コメントの状態が変更されます。"
            "検査コメントの一覧は `annofabcli inspection_comment list_unprocessed` コマンドで出力できます。"
            "`file://`を先頭に付けると、JSON形式のファイルを指定できます。"
            "実際に参照する値は `task_id`, `input_data_id`, `inspection_id` です。"
        ),
    )

    parser.add_argument(
        "--inspection_status",
        type=str,
        required=True,
        choices=[InspectionStatus.ERROR_CORRECTED.value, InspectionStatus.NO_CORRECTION_REQUIRED.value],
        help=(
            "未処置の検査コメントをどの状態に変更するかを指定します。"
            f"{InspectionStatus.ERROR_CORRECTED.value}: 対応完了,"
            f"{InspectionStatus.NO_CORRECTION_REQUIRED.value}: 対応不要"
        ),
    )

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    ComleteTasks(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "complete"
    subcommand_help = "未処置の検査コメントを適切な状態に変更して、タスクを受け入れ完了にする。"
    description = "未処置の検査コメントを適切な状態に変更して、タスクを受け入れ完了にする。" "オーナ権限を持つユーザで実行すること。"
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
