import argparse
import logging
from typing import Any, Dict, List
import json
import pandas

from enum import Enum
from typing import Optional
from pathlib import Path
from annofabapi.models import ProjectMemberRole, Task, TaskPhase, TaskHistoryShort, TaskStatus
import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class SimpleTaskStatus(Enum):
    """
    TaskStatusの作業中、休憩中、保留を簡易化したもの
    """
    NOT_STARTED = "not_started"
    WORKING_BREAK_HOLD = "working_break_hold"
    COMPLETE = "complete"

    @staticmethod
    def from_task_status(status: TaskStatus) -> "SimpleTaskStatus":
        if status in [TaskStatus.WORKING, TaskStatus.BREAK, TaskStatus.ON_HOLD]:
            return SimpleTaskStatus.WORKING_BREAK_HOLD
        elif status == TaskStatus.NOT_STARTED:
            return SimpleTaskStatus.NOT_STARTED
        elif status == TaskStatus.COMPLETE:
            return SimpleTaskStatus.COMPLETE
        else:
            raise ValueError(f"'{status}'は対象外です。")




def get_number_of_rejections(task_histories: List[TaskHistoryShort], phase: TaskPhase, phase_stage: int = 1) -> int:
    """
    タスク履歴から、指定されたタスクフェーズでの差し戻し回数を取得する。

    Args:
        task_histories: タスク履歴
        phase: どのフェーズで差し戻されたか(TaskPhase.INSPECTIONかTaskPhase.ACCEPTANCE)
        phase_stage: どのフェーズステージで差し戻されたか。デフォルトは1。

    Returns:
        差し戻し回数
    """
    if phase not in [TaskPhase.INSPECTION, TaskPhase.ACCEPTANCE]:
        raise ValueError("引数'phase'には、'TaskPhase.INSPECTION'か'TaskPhase.ACCEPTANCE'を指定してください。")

    rejections_by_phase = 0
    for i, history in enumerate(task_histories):
        if not (history["phase"] == phase.value and history["phase_stage"] == phase_stage and history["worked"]):
            continue

        if i + 1 < len(task_histories) and task_histories[i + 1]["phase"] == TaskPhase.ANNOTATION.value:
            rejections_by_phase += 1

    return rejections_by_phase

class SummarizeTaskCount(AbstractCommandLineInterface):
    """
    タスク数を集計する。
    """


    def get_task_statistics(self, project_id: str) -> List[Dict[str, Any]]:
        """
        タスクの進捗状況をCSVに出力するための dict 配列を作成する。

        Args:
            project_id:

        Returns:
            タスクの進捗状況に対応するdict配列

        """
        task_statistics, _ = self.service.api.get_task_statistics(project_id)
        row_list: List[Dict[str, Any]] = []
        for stat_by_date in task_statistics:
            date = stat_by_date["date"]
            task_stat_list = stat_by_date["tasks"]
            for task_stat in task_stat_list:
                task_stat["date"] = date
            row_list.extend(task_stat_list)
        return row_list

    def get_number_of_inspections_for_project(self, project_id:str) -> int:
        project,_ = self.service.api.get_project(project_id)
        return project["configuration"]["number_of_inspections"]

    @staticmethod
    def get_step_for_current_phase(task: Task, number_of_inspections: int) -> int:
        current_phase = TaskPhase(task["phase"])
        current_phase_stage = task["phase_stage"]
        histories_by_phase = task["histories_by_phase"]

        number_of_rejections_by_acceptance = get_number_of_rejections(histories_by_phase, phase=current_phase)
        if current_phase == TaskPhase.ACCEPTANCE:
            return number_of_rejections_by_acceptance + 1

        elif current_phase == TaskPhase.ANNOTATION:
            number_of_rejections_by_inspection = sum([get_number_of_rejections(histories_by_phase, phase=current_phase, phase_stage=phase_stage) for phase_stage in range(1, number_of_inspections+1)])
            return number_of_rejections_by_inspection + number_of_rejections_by_acceptance + 1

        elif current_phase == TaskPhase.INSPECTION:
            number_of_rejections_by_inspection = sum([get_number_of_rejections(histories_by_phase, phase=current_phase, phase_stage=phase_stage) for phase_stage in range(current_phase_stage, number_of_inspections+1)])
            return number_of_rejections_by_inspection + number_of_rejections_by_acceptance + 1

        else:
            raise RuntimeError(f"フェーズ'{current_phase}'は不正な値です。")


    def create_task_count_summary2(self, task_list: List[Task]) -> pandas.DataFrame:
        pass

    def create_task_count_summary(self, task_list: List[Task], number_of_inspections: int) -> pandas.DataFrame:
        for task in task_list:
            step_for_current_phase = self.get_step_for_current_phase(task, number_of_inspections)
            task["step"] = step_for_current_phase
            task["status"] = self.get_task_simple_status
        df = pandas.DataFrame(task_list)



        return df


    def summarize_task_count(self, project_id: Optional[str], task_json_path: Optional[Path], output: str) -> None:
        super().validate_project(project_id, project_member_roles= [ProjectMemberRole.OWNER])

        task_list = self.get_task_list(project_id, task_json_path)
        if len(task_list) == 0:
            logger.info(f"タスクが0件のため、出力しません。")
            return

        df = pandas.DataFrame(task_list)

        task_count_df = self.create_task_count_summary(df)
        annofabcli.utils.print_csv(task_count_df, output=self.output, to_csv_kwargs=self.csv_format)

    def get_task_list(self, project_id: str, task_json_path: Optional[Path]) -> List[Task]:
        if task_json_path is None:
            cache_dir = annofabcli.utils.get_cache_dir()
            task_json_path = cache_dir / "task-${project_id}.json"
            logger.debug(f"タスク全件ファイルをダウンロード中: {task_json_path}")
            self.service.wrapper.download_project_tasks_url(project_id, str(task_json_path))

        with task_json_path.open(encoding="utf-8") as f:
            task_list = json.load(f)
            return task_list

    def main(self):
        args = self.args
        project_id = args.project_id
        self.summarize_task_count(project_id, Path(args.task_json), args.output)


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    parser.add_argument(
        "--task_json",
        type=str,
        help="タスク情報が記載されたJSONファイルのパスを指定してください。JSONファイルは`$ annofabcli project download task`コマンドで取得できます。"
             "指定しない場合は、ダウンロードします。"
    )

    argument_parser.add_project_id()
    argument_parser.add_csv_format()
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    SummarizeTaskCount(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "summarize_task_count"
    subcommand_help = "タスクのフェーズ、ステータス、差し戻し回数ごとにタスク数を出力します。"
    description = "タスクのフェーズ、ステータス、差し戻し回数ごとにタスク数を、CSV形式で出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
