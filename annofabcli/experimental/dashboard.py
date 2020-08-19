import argparse
import datetime
import itertools
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import annofabapi
import dateutil
import pandas
from annofabapi.models import ProjectMemberRole, Task
from annofabapi.utils import str_now
from dataclasses_json import dataclass_json
from dateutil.parser import parse
from more_itertools import first_true

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
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.utils import isoduration_to_hour
from annofabcli.statistics.summarize_task_count_by_task_id import TaskStatusForSummary

logger = logging.getLogger(__name__)

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)


@dataclass_json
@dataclass
class TaskPhaseStatistics:
    date: str
    annotation_worktime: float = 0
    inspection_worktime: float = 0
    acceptance_worktime: float = 0

    def sum_worktime(self) -> float:
        return self.annotation_worktime + self.inspection_worktime + self.acceptance_worktime


@dataclass_json
@dataclass
class MonitoredWorktime:
    """AnnoFab計測時間の詳細情報"""

    sum: float
    """合計時間[hour]"""
    annotation: float
    inspection: float
    acceptance: float


@dataclass_json
@dataclass
class RemainingTaskCount:
    """
    フェーズごとのタスク数
    """

    complete: int = 0
    """完了状態のタスク数"""

    annotation_not_started: int = 0
    """一度も教師付作業されていないタスク数"""

    inspection_not_started: int = 0
    """一度も検査作業されていないタスク数"""

    acceptance_not_started: int = 0
    """一度も受入作業されていないタスク数"""

    on_hold: int = 0
    """保留状態のタスク数"""

    other: int = 0
    """休憩中/作業中/2回目以降の各フェーズの未着手状態のタスク数"""


@dataclass_json
@dataclass
class ProgressData:
    # task_count: TaskCount
    # """タスク数情報"""

    actual_worktime: float
    """実績作業時間[hour]"""

    task_count: int
    """完了したタスク数"""

    input_data_count: int
    """完了したタスク配下の入力データ数"""

    velocity_per_task: Optional[float]
    """acutal_worktime/task_count"""

    velocity_per_input_data: Optional[float]
    """acutal_worktime/input_data_count"""

    monitored_worktime: Optional[float] = None
    """AnnoFabの計測作業時間[hour]"""

    annotation_monitored_worktime: Optional[float] = None
    """AnnoFabのannotation計測作業時間[hour]"""

    inspection_monitored_worktime: Optional[float] = None
    """AnnoFabのinspection計測作業時間[hour]"""

    acceptance_monitored_worktime: Optional[float] = None
    """AnnoFabのacceptance計測作業時間[hour]"""


@dataclass_json
@dataclass
class ResultValues:

    cumulation: ProgressData
    """累計情報"""
    today: ProgressData
    """対象日当日の情報"""
    week: ProgressData
    """対象日から1週間（直前7日間）の情報"""


@dataclass_json
@dataclass
class Planvalues:
    plan_worktime: float
    """予定作業時間"""
    task_count: Optional[int]
    """予定の完了タスク数"""


@dataclass_json
@dataclass
class DashboardData:
    project_id: str
    project_title: str
    date: str
    """対象日（YYYY-MM-DD）"""
    measurement_datetime: str
    """計測日時。（2004-04-01T12:00+09:00形式）"""

    remaining_task_count: RemainingTaskCount
    """残りのタスク数"""
    result: ResultValues
    plan: Dict[int, Planvalues]
    task_exhaustation_date: Optional[str]
    """タスク枯渇予定日"""


def add_info_to_task(task: Task):
    task["status_for_summary"] = TaskStatusForSummary.from_task(task).value


def get_remaining_task_count_info_from_task_list(task_list: List[Task]) -> RemainingTaskCount:
    """
    状態ごとのタスク数を取得する。

    Args:
        task_list:

    Returns:

    """
    status_list: List[str] = [e["status_for_summary"] for e in task_list]
    tmp = pandas.Series.value_counts(status_list)
    task_count = RemainingTaskCount.from_dict(tmp.to_dict())  # type: ignore
    return task_count


def get_completed_task_count_and_input_data_count(task_list: List[Task]) -> Tuple[int, int]:
    """
    完了したタスク数と入力データ数を求める

    Args:
        task_list:

    Returns:
        Tuple[task_count, input_data_count]
    """
    task_list = [e for e in task_list if e["status_for_summary"] == TaskStatusForSummary.COMPLETE.value]
    input_data_count = len(list(itertools.chain.from_iterable([e["input_data_id_list"] for e in task_list])))
    task_count = len(task_list)
    return task_count, input_data_count


def _to_datetime_from_date(date: datetime.date) -> datetime.datetime:
    dt = datetime.datetime.combine(date, datetime.datetime.min.time())
    return dt.replace(tzinfo=dateutil.tz.tzlocal())


def millisecond_to_hour(millisecond: int):
    return millisecond / 1000 / 3600


def get_task_list_where_updated_datetime(
    task_list: List[Task], lower_date: datetime.date, upper_date: datetime.date
) -> List[Task]:
    """
    タスクの更新日が、対象期間内であるタスク一覧を取得する。

    Args:
        task_list:
        lower_date:
        upper_date:

    Returns:

    """

    def pred(task):
        updated_datetime = parse(task["updated_datetime"])
        return lower_datetime <= updated_datetime < upper_datetime

    lower_datetime = _to_datetime_from_date(lower_date)
    upper_datetime = _to_datetime_from_date(upper_date + datetime.timedelta(days=1))
    return [t for t in task_list if pred(t)]


def _get_actual_worktime_hour_from_labor(labor: Dict[str, Any]) -> float:
    working_time_by_user = labor["values"]["working_time_by_user"]
    if working_time_by_user is None:
        return 0

    actual_worktime = working_time_by_user.get("results")
    if actual_worktime is None:
        return 0
    else:
        return actual_worktime / 3600 / 1000


def _get_plan_worktime_hour_from_labor(labor: Dict[str, Any]) -> float:
    working_time_by_user = labor["values"]["working_time_by_user"]
    if working_time_by_user is None:
        return 0

    actual_worktime = working_time_by_user.get("plans")
    if actual_worktime is None:
        return 0
    else:
        return actual_worktime / 3600 / 1000


def _get_today_info(
    today: str,
    task_list: List[Task],
    actual_worktime_dict: Dict[str, float],
    task_phase_statistics: List[TaskPhaseStatistics],
) -> ProgressData:
    dt_today = datetime.datetime.strptime(today, "%Y-%m-%d").date()
    task_list_for_day = get_task_list_where_updated_datetime(task_list, lower_date=dt_today, upper_date=dt_today)
    today_monitor_worktime_info = get_monitored_worktime(
        task_phase_statistics, lower_date=dt_today, upper_date=dt_today
    )
    task_count, input_data_count = get_completed_task_count_and_input_data_count(task_list_for_day)
    actual_worktime = actual_worktime_dict.get(today, 0)
    today_info = ProgressData(
        task_count=task_count,
        input_data_count=input_data_count,
        actual_worktime=actual_worktime,
        velocity_per_task=actual_worktime / task_count if task_count > 0 else None,
        velocity_per_input_data=actual_worktime / input_data_count if input_data_count > 0 else None,
    )
    if today_monitor_worktime_info is not None:
        today_info.monitored_worktime = today_monitor_worktime_info.sum
        today_info.annotation_monitored_worktime = today_monitor_worktime_info.annotation
        today_info.inspection_monitored_worktime = today_monitor_worktime_info.inspection
        today_info.acceptance_monitored_worktime = today_monitor_worktime_info.acceptance
    return today_info


def _get_week_info(
    today: str,
    task_list: List[Task],
    actual_worktime_dict: Dict[str, float],
    task_phase_statistics: List[TaskPhaseStatistics],
) -> ProgressData:
    dt_today = datetime.datetime.strptime(today, "%Y-%m-%d").date()
    week_ago = dt_today - datetime.timedelta(days=6)
    task_list_for_week = get_task_list_where_updated_datetime(task_list, lower_date=week_ago, upper_date=dt_today)
    week_monitor_worktime_info = get_monitored_worktime(task_phase_statistics, lower_date=week_ago, upper_date=dt_today)
    task_count, input_data_count = get_completed_task_count_and_input_data_count(task_list_for_week)
    actual_worktime = get_worktime_for_period(actual_worktime_dict, lower_date=week_ago, upper_date=dt_today)

    seven_days_info = ProgressData(
        task_count=task_count,
        input_data_count=input_data_count,
        actual_worktime=actual_worktime,
        velocity_per_task=actual_worktime / task_count if task_count > 0 else None,
        velocity_per_input_data=actual_worktime / input_data_count if input_data_count > 0 else None,
    )
    if week_monitor_worktime_info is not None:
        seven_days_info.monitored_worktime = week_monitor_worktime_info.sum
        seven_days_info.annotation_monitored_worktime = week_monitor_worktime_info.annotation
        seven_days_info.inspection_monitored_worktime = week_monitor_worktime_info.inspection
        seven_days_info.acceptance_monitored_worktime = week_monitor_worktime_info.acceptance
    return seven_days_info


def get_worktime_for_period(worktime_dict: Dict[str, float], lower_date: datetime.date, upper_date: datetime.date):
    sum_worktime = 0.0
    for dt in pandas.date_range(start=lower_date, end=upper_date):
        str_date = str(dt.date())
        sum_worktime += worktime_dict.get(str_date, 0.0)
    return sum_worktime


def get_monitored_worktime(
    task_phase_statistics: List[TaskPhaseStatistics], lower_date: datetime.date, upper_date: datetime.date
) -> Optional[MonitoredWorktime]:
    upper_stat = first_true(task_phase_statistics, pred=lambda e: e.date == str(upper_date))
    lower_stat = first_true(
        task_phase_statistics, pred=lambda e: e.date == str(lower_date - datetime.timedelta(days=1))
    )
    if upper_stat is None or lower_stat is None:
        logger.debug(f"{lower_date} 〜 {upper_date} 期間のmonitor_worktimeを算出できませんでした。")
        return None

    return MonitoredWorktime(
        sum=upper_stat.sum_worktime() - lower_stat.sum_worktime(),
        annotation=upper_stat.annotation_worktime - lower_stat.annotation_worktime,
        inspection=upper_stat.inspection_worktime - lower_stat.inspection_worktime,
        acceptance=upper_stat.acceptance_worktime - lower_stat.acceptance_worktime,
    )


def _get_cumulation_info(task_list: List[Task], actual_worktime_dict: Dict[str, float]) -> ProgressData:
    task_count, input_data_count = get_completed_task_count_and_input_data_count(task_list)
    actual_worktime = sum(actual_worktime_dict.values())

    return ProgressData(
        task_count=task_count,
        input_data_count=input_data_count,
        monitored_worktime=sum([t["worktime_hour"] for t in task_list]),
        actual_worktime=actual_worktime,
        velocity_per_task=actual_worktime / task_count if task_count > 0 else None,
        velocity_per_input_data=actual_worktime / input_data_count if input_data_count > 0 else None,
    )


def _get_plan_value(
    plan_worktime_dict: Dict[str, float], dt_today: datetime.date, days: int, velocity_per_task: Optional[float],
) -> Planvalues:
    dt_from_date = dt_today + datetime.timedelta(days=1)
    dt_end_date = dt_today + datetime.timedelta(days=days)

    plan_worktime = get_worktime_for_period(plan_worktime_dict, lower_date=dt_from_date, upper_date=dt_end_date)
    task_count = (
        int(plan_worktime / velocity_per_task) if velocity_per_task is not None and velocity_per_task > 0 else None
    )
    return Planvalues(plan_worktime=plan_worktime, task_count=task_count)


def get_task_exhaustation_date(
    plan_worktime_dict: Dict[str, float], annotation_not_started: int, velocity_per_task: float
) -> Optional[str]:
    """
    タスクの枯渇予定日を求める。
    教師付されていないタスク数がすでに０ならば、Noneを返す。

    Args:
        plan_worktime_dict:
        annotation_not_started:
        velocity_per_task:

    Returns:

    """
    if annotation_not_started <= 0 or velocity_per_task <= 0:
        return None

    remaining_task: float = annotation_not_started
    for date in sorted(plan_worktime_dict.keys()):
        plan_worktime = plan_worktime_dict[date]
        task_count = plan_worktime / velocity_per_task
        remaining_task -= task_count
        if remaining_task <= 0:
            return date
    return None


def create_plan_values(
    plan_worktime_dict: Dict[str, float], velocity_per_task: Optional[float], today: str
) -> Dict[int, Planvalues]:
    dt_today = datetime.datetime.strptime(today, "%Y-%m-%d").date()
    return {
        7: _get_plan_value(plan_worktime_dict, dt_today=dt_today, days=7, velocity_per_task=velocity_per_task),
        14: _get_plan_value(plan_worktime_dict, dt_today=dt_today, days=14, velocity_per_task=velocity_per_task),
    }


class PrintDashBoardMain:
    def __init__(self, service: annofabapi.Resource):
        self.service = service
        self.facade = AnnofabApiFacade(service)

    def get_task_phase_statistics(self, project_id: str) -> List[TaskPhaseStatistics]:
        """
        フェーズごとの累積作業時間をCSVに出力するための dict 配列を作成する。

        Args:
            project_id:

        Returns:
            フェーズごとの累積作業時間に対応するdict配列

        """
        task_phase_statistics = self.service.wrapper.get_task_phase_statistics(project_id)
        row_list: List[TaskPhaseStatistics] = []
        for stat_by_date in task_phase_statistics:
            elm = {"date": stat_by_date["date"]}
            for phase_stat in stat_by_date["phases"]:
                phase = phase_stat["phase"]
                worktime_hour = isoduration_to_hour(phase_stat["worktime"])
                elm[f"{phase}_worktime"] = worktime_hour
            row_list.append(TaskPhaseStatistics.from_dict(elm))  # type: ignore
        return row_list

    def get_actual_worktime_dict(self, project_id: str, date: str) -> Dict[str, float]:
        """
        日毎のプロジェクト全体の実績作業時間を取得する。

        Args:
            project_id:
            date: 対象期間の終了日

        Returns:
            key:date, value:実績作業時間のdict

        """
        # 予定稼働時間を取得するには、特殊な組織IDを渡す
        labor_list, _ = self.service.api.get_labor_control({"project_id": project_id, "to": date})
        actual_worktime_dict: Dict[str, float] = defaultdict(float)
        for labor in labor_list:
            date = labor["date"]
            actual_worktime = _get_actual_worktime_hour_from_labor(labor)
            actual_worktime_dict[date] += actual_worktime

        return actual_worktime_dict

    def get_plan_worktime_dict(self, project_id: str, today: str, days: Optional[int] = None) -> Dict[str, float]:
        """
        日毎のプロジェクト全体の予定作業時間を取得する。

        Args:
            project_id:
            date: 対象期間の終了日

        Returns:
            key:date, value: 予定作業時間のdict

        """
        dt_today = datetime.datetime.strptime(today, "%Y-%m-%d").date()
        dt_from_date = dt_today + datetime.timedelta(days=1)
        end_date = str(dt_today + datetime.timedelta(days=days)) if days is not None else None

        # 予定稼働時間を取得するには、特殊な組織IDを渡す
        labor_list, _ = self.service.api.get_labor_control(
            {"project_id": project_id, "from": str(dt_from_date), "to": end_date}
        )
        plan_worktime_dict: Dict[str, float] = defaultdict(float)
        for labor in labor_list:
            date = labor["date"]
            plan_worktime = _get_plan_worktime_hour_from_labor(labor)
            plan_worktime_dict[date] += plan_worktime

        return plan_worktime_dict

    def create_result_values(self, project_id: str, date: str, task_list: List[Task]) -> ResultValues:
        """
        実績情報を生成する。

        Args:
            task_list:
            date: タスク数　集計対象日

        Returns:

        """
        for task in task_list:
            task["status_for_summary"] = TaskStatusForSummary.from_task(task).value
            task["worktime_hour"] = millisecond_to_hour(task["work_time_span"])

        actual_worktime_dict = self.get_actual_worktime_dict(project_id, date)
        task_phase_statistics = self.get_task_phase_statistics(project_id)

        cumulation_info = _get_cumulation_info(task_list, actual_worktime_dict)
        today_info = _get_today_info(
            today=date,
            task_list=task_list,
            actual_worktime_dict=actual_worktime_dict,
            task_phase_statistics=task_phase_statistics,
        )
        week_info = _get_week_info(
            today=date,
            task_list=task_list,
            actual_worktime_dict=actual_worktime_dict,
            task_phase_statistics=task_phase_statistics,
        )
        return ResultValues(cumulation=cumulation_info, today=today_info, week=week_info)

    def create_dashboard_data(self, project_id: str, date: str, task_list: List[Task]) -> DashboardData:
        project_title = self.facade.get_project_title(project_id)
        result = self.create_result_values(project_id=project_id, date=date, task_list=task_list)
        remaining_task_count = get_remaining_task_count_info_from_task_list(task_list)
        plan_worktime_dict = self.get_plan_worktime_dict(project_id, today=date)
        velocity_per_task = result.week.velocity_per_task

        task_exhaustation_date = (
            get_task_exhaustation_date(
                plan_worktime_dict=plan_worktime_dict,
                annotation_not_started=remaining_task_count.annotation_not_started,
                velocity_per_task=velocity_per_task,
            )
            if velocity_per_task is not None
            else None
        )

        dashboard_info = DashboardData(
            project_id=project_id,
            project_title=project_title,
            date=date,
            measurement_datetime=str_now(),
            remaining_task_count=remaining_task_count,
            result=result,
            plan=create_plan_values(plan_worktime_dict, velocity_per_task=velocity_per_task, today=date),
            task_exhaustation_date=task_exhaustation_date,
        )
        return dashboard_info


class DashBoard(AbstractCommandLineInterface):
    def print_summarize_task_count(self, target_dict: dict) -> None:
        annofabcli.utils.print_according_to_format(
            target_dict, arg_format=FormatArgument.JSON, output=self.output,
        )

    def main(self):
        args = self.args
        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        if args.task_json is not None:
            task_json_path = args.task_json
        else:
            wait_options = get_wait_options_from_args(get_json_from_args(args.wait_options), DEFAULT_WAIT_OPTIONS)
            cache_dir = annofabcli.utils.get_cache_dir()
            task_json_path = cache_dir / f"{project_id}-task.json"

            downloading_obj = DownloadingFile(self.service)
            downloading_obj.download_task_json(
                project_id, dest_path=str(task_json_path), is_latest=args.latest, wait_options=wait_options
            )

        with open(task_json_path, encoding="utf-8") as f:
            task_list = json.load(f)

        main_obj = PrintDashBoardMain(self.service)

        dashboard_date = main_obj.create_dashboard_data(project_id, date=args.date, task_list=task_list)
        annofabcli.utils.print_according_to_format(
            dashboard_date.to_dict(), arg_format=FormatArgument(self.str_format), output=self.output,
        )


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    parser.add_argument(
        "--task_json",
        type=str,
        help="タスク情報が記載されたJSONファイルのパスを指定してます。JSONファイルは`$ annofabcli project download task`コマンドで取得できます。"
        "指定しない場合は、AnnoFabからタスク全件ファイルをダウンロードします。",
    )

    parser.add_argument("--date", type=str, required=True, help="`YYYY-MM-DD`形式で実績の対象日を指定してください。")

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

    argument_parser.add_format([FormatArgument.PRETTY_JSON, FormatArgument.JSON], default=FormatArgument.PRETTY_JSON)
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DashBoard(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "dashboard"
    subcommand_help = "ダッシュボードとなる情報（タスク数など）をJSON形式で出力します。"
    description = "ダッシュボードとなる情報（タスク数など）をJSON形式で出力します。"
    epilog = "オーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog
    )
    parse_args(parser)
