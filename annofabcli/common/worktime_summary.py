from __future__ import annotations

import datetime
from collections import defaultdict
from collections.abc import Collection
from pathlib import Path
from typing import Any

import pandas
from dateutil.parser import parse

from annofabcli.common.cli import CommandLine
from annofabcli.common.enums import OutputFormat
from annofabcli.common.task_history_worktime import ListWorktimeFromTaskHistoryEventMain, WorktimeFromTaskHistoryEvent

WorktimeDict = dict[tuple[str, str, str], float]
"""日付、アカウントID、工程をキーとする作業時間（時間単位）。"""

WORKTIME_COLUMNS = [
    "date",
    "account_id",
    "user_id",
    "username",
    "biography",
    "worktime_hour",
    "annotation_worktime_hour",
    "inspection_worktime_hour",
    "acceptance_worktime_hour",
]
"""作業時間集計の出力列。"""


def _get_worktime_dict_from_event(event: WorktimeFromTaskHistoryEvent) -> WorktimeDict:
    """作業区間を日付ごとに分割する。

    Args:
        event: 作業区間の情報。

    Returns:
        日付、アカウントID、工程ごとの作業時間。
    """
    dict_result: WorktimeDict = defaultdict(float)

    dt_start = parse(event.start_event.created_datetime)
    dt_end = parse(event.end_event.created_datetime)

    if dt_start.date() == dt_end.date():
        worktime_hour = (dt_end - dt_start).total_seconds() / 3600
        dict_result[(str(dt_start.date()), event.account_id, event.phase)] = worktime_hour
    else:
        jst_tzinfo = datetime.timezone(datetime.timedelta(hours=9))
        dt_tmp_start = dt_start

        while dt_tmp_start.date() < dt_end.date():
            dt_next_date = dt_tmp_start.date() + datetime.timedelta(days=1)
            dt_tmp_end = datetime.datetime(year=dt_next_date.year, month=dt_next_date.month, day=dt_next_date.day, tzinfo=jst_tzinfo)
            worktime_hour = (dt_tmp_end - dt_tmp_start).total_seconds() / 3600
            dict_result[(str(dt_tmp_start.date()), event.account_id, event.phase)] = worktime_hour
            dt_tmp_start = dt_tmp_end

        worktime_hour = (dt_end - dt_tmp_start).total_seconds() / 3600
        dict_result[(str(dt_tmp_start.date()), event.account_id, event.phase)] = worktime_hour

    return dict_result


def get_worktime_dict_from_event_list(task_history_event_list: Collection[WorktimeFromTaskHistoryEvent]) -> WorktimeDict:
    """作業区間を日付、アカウントID、工程ごとに集計する。

    Args:
        task_history_event_list: 作業区間の一覧。

    Returns:
        日付、アカウントID、工程ごとの作業時間。
    """
    dict_result: WorktimeDict = defaultdict(float)

    for event in task_history_event_list:
        dict_tmp = _get_worktime_dict_from_event(event)
        for key, value in dict_tmp.items():
            dict_result[key] += value
    return dict_result


def get_df_worktime(task_history_event_list: Collection[WorktimeFromTaskHistoryEvent], member_list: list[dict[str, Any]]) -> pandas.DataFrame:
    """ユーザーごと日付ごとの作業時間を表にする。

    Args:
        task_history_event_list: 作業区間の一覧。
        member_list: プロジェクトメンバーの一覧。

    Returns:
        工程別の作業時間と合計作業時間を持つDataFrame。
    """
    if not task_history_event_list:
        return pandas.DataFrame(columns=WORKTIME_COLUMNS)

    dict_worktime = get_worktime_dict_from_event_list(task_history_event_list)

    s = pandas.Series(
        dict_worktime.values(),
        index=pandas.MultiIndex.from_tuples(dict_worktime.keys(), names=("date", "account_id", "phase")),
    )
    df = s.unstack()  # noqa: PD010 : pandas.Seriesにはpivot_tableがないので、警告を無視する
    df.reset_index(inplace=True)
    df.rename(
        columns={
            "annotation": "annotation_worktime_hour",
            "inspection": "inspection_worktime_hour",
            "acceptance": "acceptance_worktime_hour",
        },
        inplace=True,
    )

    # 列数を固定させる
    for phase in ["annotation", "inspection", "acceptance"]:
        column = f"{phase}_worktime_hour"
        if column not in df.columns:
            df[column] = 0

    df.fillna({"annotation_worktime_hour": 0, "inspection_worktime_hour": 0, "acceptance_worktime_hour": 0}, inplace=True)

    df["worktime_hour"] = df["annotation_worktime_hour"] + df["inspection_worktime_hour"] + df["acceptance_worktime_hour"]

    df_member = pandas.DataFrame(member_list, columns=["account_id", "user_id", "username", "biography"])

    df = df.merge(df_member, how="left", on="account_id")
    return df[WORKTIME_COLUMNS]


class SummarizeWorktimeByUserAndDate(CommandLine):
    def print_worktime_list(
        self,
        project_id: str,
        task_history_event_json: Path | None,
    ) -> None:
        """タスク履歴イベントから作業時間を集計して出力する。

        Args:
            project_id: プロジェクトID。
            task_history_event_json: タスク履歴イベント全件ファイルのパス。

        Returns:
            None
        """
        super().require_project_access(project_id, project_member_roles=None)

        main_obj = ListWorktimeFromTaskHistoryEventMain(self.service, project_id=project_id)
        worktime_list = main_obj.get_worktime_list(
            project_id,
            task_history_event_json=task_history_event_json,
        )
        project_member_list = self.service.wrapper.get_all_project_members(project_id, query_params={"include_inactive_member": ""})
        df = get_df_worktime(worktime_list, project_member_list)

        if self.str_format == OutputFormat.CSV.value:
            self.print_csv(df)
        else:
            self.print_according_to_format(df.to_dict(orient="records"))

    def main(self) -> None:
        """コマンドライン引数に従って集計する。

        Args:
            なし。

        Returns:
            None
        """
        args = self.args

        self.print_worktime_list(
            args.project_id,
            task_history_event_json=args.task_history_event_json,
        )
