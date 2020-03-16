import argparse
import logging
import time
from typing import Dict, List, Optional

import requests
from annofabapi.dataclass.task import Task
from annofabapi.models import InputDataId, Inspection, InspectionStatus, ProjectMemberRole, TaskId, TaskPhase

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
    def inspection_list_to_input_data_dict(inspection_list: List[Inspection]) -> Dict[InputDataId, List[Inspection]]:
        """
        検査コメントのListを、Dict[InputDataId, List[Inspection]]] の形式に変換する。

        """
        input_data_dict: Dict[InputDataId, List[Inspection]] = {}
        for inspection in inspection_list:
            input_data_id = inspection["input_data_id"]
            inspection_list = input_data_dict.get(input_data_id, [])
            inspection_list.append(inspection)
            input_data_dict[input_data_id] = inspection_list
        return input_data_dict

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
        logger.info(f"{task_id}: 検査/受入フェーズを完了状態にしました。")

    def get_unprocessed_inspection_list_by_task_id(self, project_id: str, task: Task) -> List[Inspection]:
        all_inspection_list = []
        for input_data_id in task.input_data_id_list:
            inspectins, _ = self.service.api.get_inspections(project_id, task.task_id, input_data_id)
            all_inspection_list.extend(
                [e for e in inspectins if e["status"] == InspectionStatus.ANNOTATOR_ACTION_REQUIRED.value]
            )

        return all_inspection_list

    def complete_task(
        self,
        project_id: str,
        account_id: str,
        change_inspection_status: Optional[InspectionStatus],
        target_inspections_dict: Optional[InspectionJson],
        task: Task,
        unprocessed_inspection_list: List[Inspection],
    ):
        if task.phase == TaskPhase.ANNOTATION or len(unprocessed_inspection_list) == 0:
            self.facade.complete_task(project_id, task.task_id, account_id)
            logger.info(f"{task.task_id}: {task.phase} フェーズを完了状態にしました。")
            return

        if change_inspection_status is None:
            logger.info(f"{task.task_id}: 未処置の検査コメントがあるためスキップします。")

        if target_inspections_dict is None:
            input_data_dict = self.inspection_list_to_input_data_dict(unprocessed_inspection_list)
        else:
            input_data_dict = target_inspections_dict[task.task_id]

        self.complete_acceptance_task(
            project_id,
            task,
            inspection_status=change_inspection_status,
            input_data_dict=input_data_dict,
            account_id=account_id,
        )

    def complete_tasks_with_changing_inspection_status(
        self,
        project_id: str,
        task_id_list: List[str],
        change_inspection_status: Optional[InspectionStatus] = None,
        target_inspection_list: Optional[List[Inspection]] = None,
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
        target_inspections_dict = (
            self.inspection_list_to_dict(target_inspection_list) if target_inspection_list is not None else None
        )
        project_title = self.facade.get_project_title(project_id)
        logger.info(f"{project_title} のタスク {len(task_id_list)} 件に対して、今のフェーズを完了状態にします。")

        for task_id in task_id_list:
            dict_task = self.service.wrapper.get_task_or_none(project_id, task_id)
            if dict_task is None:
                logger.warning(f"{task_id} のタスクを取得できませんでした。")
                continue

            task = Task.from_dict(dict_task)
            logger.info(f"タスク情報 task_id: {task_id}, phase: {task.phase.value}, status: {task.status.value}")

            unprocessed_inspection_list = self.get_unprocessed_inspection_list_by_task_id(project_id, task)
            logger.debug(f"未処置の検査コメントが {len(unprocessed_inspection_list)} 件あります。")
            if len(unprocessed_inspection_list) > 0 and change_inspection_status is None:
                logger.debug(f"{task_id}: 未処置の検査コメントがあるためスキップします。")
                continue

            if not self.confirm_processing(f"タスク'{task_id}'の {task.phase.value} フェーズを、完了状態にしますか？"):
                continue

            # 担当者変更
            try:
                self.facade.change_operator_of_task(project_id, task_id, account_id)
                self.facade.change_to_working_phase(project_id, task_id, account_id)
                logger.debug(f"{task_id}: 担当者を変更しました。")

            except requests.HTTPError as e:
                logger.warning(e)
                logger.warning(f"{task_id}: 担当者の変更に失敗しました。")
                continue

            # 担当者変更してから数秒待たないと、検査コメントの付与に失敗する(「検査コメントの作成日時が不正です」と言われる）
            time.sleep(3)

            try:
                self.complete_task(
                    project_id=project_id,
                    account_id=account_id,
                    change_inspection_status=change_inspection_status,
                    target_inspections_dict=target_inspections_dict,
                    task=task,
                    unprocessed_inspection_list=unprocessed_inspection_list,
                )
            except requests.HTTPError as e:
                logger.warning(e)
                logger.warning(f"{task_id}: {task.phase} フェーズを完了状態にするのに失敗しました。")
                self.facade.change_to_break_phase(project_id, task_id, account_id)
                continue

    def main(self):
        args = self.args
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        inspection_list = annofabcli.common.cli.get_json_from_args(args.inspection_list)
        inspection_status = InspectionStatus(args.change_inspection_status)
        self.complete_tasks_with_changing_inspection_status(
            args.project_id,
            task_id_list=task_id_list,
            change_inspection_status=inspection_status,
            target_inspection_list=inspection_list,
        )


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id(required=True)

    parser.add_argument(
        "--change_inspection_status",
        type=str,
        choices=[InspectionStatus.ERROR_CORRECTED.value, InspectionStatus.NO_CORRECTION_REQUIRED.value],
        help=(
            "未処置の検査コメントをどの状態に変更するかを指定します。指定しない場合、未処置の検査コメントが含まれるタスクはスキップします。"
            f"{InspectionStatus.ERROR_CORRECTED.value}: 対応完了,"
            f"{InspectionStatus.NO_CORRECTION_REQUIRED.value}: 対応不要"
        ),
    )

    parser.add_argument(
        "--inspection_list",
        type=str,
        help=(
            "未処置の検査コメントの一覧をJSON形式で指定します。指定された検査コメントの状態が変更されます。"
            "検査コメントの一覧は `annofabcli inspection_comment list_unprocessed` コマンドで出力できます。"
            "`file://`を先頭に付けると、JSON形式のファイルを指定できます。"
            "実際に参照する値は `task_id`, `input_data_id`, `inspection_id` です。"
        ),
    )

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ComleteTasks(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "complete"
    subcommand_help = "タスクの今のフェーズを完了状態（教師付の提出、検査/受入の合格）にします。"
    description = "タスクの今のフェーズを完了状態（教師付の提出、検査/受入の合格）にします。" "未処置の検査コメントがある場合、適切な状態に変更できます。" "オーナ権限を持つユーザで実行すること。"
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
