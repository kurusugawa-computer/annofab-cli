import argparse
import json
import logging
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas
import requests
from annofabapi.models import JobType, ProjectMemberRole, Task, TaskPhase, TaskStatus
from annofabapi.utils import get_number_of_rejections

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    get_wait_options_from_args,
)
from annofabcli.common.dataclasses import WaitOptions

logger = logging.getLogger(__name__)

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)


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

    def get_number_of_inspections_for_project(self, project_id: str) -> int:
        project, _ = self.service.api.get_project(project_id)
        return project["configuration"]["number_of_inspections"]

    @staticmethod
    def get_step_for_current_phase(task: Task, number_of_inspections: int) -> int:
        current_phase = TaskPhase(task["phase"])
        current_phase_stage = task["phase_stage"]
        histories_by_phase = task["histories_by_phase"]

        number_of_rejections_by_acceptance = get_number_of_rejections(histories_by_phase, phase=TaskPhase.ACCEPTANCE)
        if current_phase == TaskPhase.ACCEPTANCE:
            return number_of_rejections_by_acceptance + 1

        elif current_phase == TaskPhase.ANNOTATION:
            number_of_rejections_by_inspection = sum(
                [
                    get_number_of_rejections(histories_by_phase, phase=TaskPhase.INSPECTION, phase_stage=phase_stage)
                    for phase_stage in range(1, number_of_inspections + 1)
                ]
            )
            return number_of_rejections_by_inspection + number_of_rejections_by_acceptance + 1

        elif current_phase == TaskPhase.INSPECTION:
            number_of_rejections_by_inspection = sum(
                [
                    get_number_of_rejections(histories_by_phase, phase=TaskPhase.INSPECTION, phase_stage=phase_stage)
                    for phase_stage in range(current_phase_stage, number_of_inspections + 1)
                ]
            )
            return number_of_rejections_by_inspection + number_of_rejections_by_acceptance + 1

        else:
            raise RuntimeError(f"フェーズ'{current_phase}'は不正な値です。")

    def create_task_count_summary(self, task_list: List[Task], number_of_inspections: int) -> pandas.DataFrame:
        """

        Args:
            task_list:
            number_of_inspections: プロジェクト設定から取得した検査フェーズの回数

        Returns:

        """
        for task in task_list:
            status = TaskStatus(task["status"])
            if status == TaskStatus.COMPLETE:
                step_for_current_phase = sys.maxsize
            else:
                step_for_current_phase = self.get_step_for_current_phase(task, number_of_inspections)
            task["step"] = step_for_current_phase
            task["simple_status"] = SimpleTaskStatus.from_task_status(status).value

        df = pandas.DataFrame(task_list)
        df["phase"] = pandas.Categorical(
            df["phase"], categories=[TaskPhase.ANNOTATION.value, TaskPhase.INSPECTION.value, TaskPhase.ACCEPTANCE.value]
        )
        df["simple_status"] = pandas.Categorical(
            df["simple_status"],
            categories=[
                SimpleTaskStatus.NOT_STARTED.value,
                SimpleTaskStatus.WORKING_BREAK_HOLD.value,
                SimpleTaskStatus.COMPLETE.value,
            ],
        )

        summary_df = df.pivot_table(
            values="task_id", index=["step", "phase", "phase_stage", "simple_status"], aggfunc="count"
        ).reset_index()
        summary_df.rename(columns={"task_id": "task_count"}, inplace=True)

        summary_df.sort_values(["step", "phase", "phase_stage"])
        summary_df.loc[summary_df["step"] == sys.maxsize, "step"] = pandas.NA
        summary_df = summary_df.astype({"task_count": "Int64", "step": "Int64", "phase_stage": "Int64"})
        return summary_df

    def update_task_json_and_wait(self, project_id: str, wait_options: WaitOptions) -> None:
        try:
            self.service.api.post_project_tasks_update(project_id)
        except requests.HTTPError as e:
            # ジョブが既に実行中ならエラーを無視する
            if e.response.status_code == requests.codes.conflict:
                logger.info(f"タスク一覧ファイルの更新処理が既に実行されています。")
            else:
                raise e

        self.service.wrapper.wait_for_completion(
            project_id,
            JobType.GEN_TASKS_LIST,
            job_access_interval=wait_options.interval,
            max_job_access=wait_options.max_tries,
        )

    def summarize_task_count(
        self, project_id: str, task_json_path: Optional[Path], is_latest: bool, wait_options: WaitOptions
    ) -> None:
        super().validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER])

        task_list = self.get_task_list(project_id, task_json_path, is_latest=is_latest, wait_options=wait_options)
        if len(task_list) == 0:
            logger.info(f"タスクが0件のため、出力しません。")
            return

        number_of_inspections = self.get_number_of_inspections_for_project(project_id)
        task_count_df = self.create_task_count_summary(task_list, number_of_inspections=number_of_inspections)
        annofabcli.utils.print_csv(task_count_df, output=self.output, to_csv_kwargs=self.csv_format)

    def get_task_list(
        self, project_id: str, task_json_path: Optional[Path], is_latest: bool, wait_options: WaitOptions
    ) -> List[Task]:
        if task_json_path is None:
            if is_latest:
                self.update_task_json_and_wait(project_id, wait_options)

            cache_dir = annofabcli.utils.get_cache_dir()
            task_json_path = cache_dir / f"task-{project_id}.json"
            logger.debug(f"タスク一覧ファイルをダウンロード中: {task_json_path}")
            try:
                self.service.wrapper.download_project_tasks_url(project_id, str(task_json_path))
            except requests.HTTPError as e:
                if e.response.status_code == requests.codes.not_found:
                    # 停止中プロジェクトのため、タスク一覧ファイルがない可能性があるので、タスク一覧ファイルの更新処理を実行する
                    logger.info(f"タスク一覧ファイルが存在しなかったので、タスク一覧ファイルの生成処理を実行します。")
                    self.update_task_json_and_wait(project_id, wait_options)
                    self.service.wrapper.download_project_tasks_url(project_id, str(task_json_path))
                else:
                    raise e

        with task_json_path.open(encoding="utf-8") as f:
            task_list = json.load(f)
            return task_list

    def main(self):
        args = self.args
        project_id = args.project_id
        wait_options = get_wait_options_from_args(get_json_from_args(args.wait_options), DEFAULT_WAIT_OPTIONS)
        task_json_path = Path(args.task_json) if args.task_json is not None else None
        self.summarize_task_count(
            project_id, task_json_path=task_json_path, is_latest=args.latest, wait_options=wait_options
        )


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    parser.add_argument(
        "--task_json",
        type=str,
        help="タスク情報が記載されたJSONファイルのパスを指定してください。JSONファイルは`$ annofabcli project download task`コマンドで取得できます。"
        "指定しない場合は、AnnoFabからタスク全件ファイルをダウンロードします。",
    )

    parser.add_argument(
        "--latest", action="store_true", help="最新のタスク一覧ファイルを参照します。このオプションを指定すると、タスク一覧ファイルを更新するのに数分待ちます。"
    )

    parser.add_argument(
        "--wait_options",
        type=str,
        help="タスク一覧ファイルの更新が完了するまで待つ際のオプションを、JSON形式で指定してください。"
        "`file://`を先頭に付けるとjsonファイルを指定できます。"
        'デフォルは`{"interval":60, "max_tries":360}` です。'
        "`interval`:完了したかを問い合わせる間隔[秒], "
        "`max_tires`:完了したかの問い合わせを最大何回行うか。",
    )

    argument_parser.add_csv_format()
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    SummarizeTaskCount(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "summarize_task_count"
    subcommand_help = "タスクのフェーズ、ステータス、ステップごとにタスク数を出力します。"
    description = "タスクのフェーズ、ステータス、ステップごとにタスク数を、CSV形式で出力します。"
    epilog = "オーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog
    )
    parse_args(parser)
