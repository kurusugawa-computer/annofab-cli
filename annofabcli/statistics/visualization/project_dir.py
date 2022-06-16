from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

from dataclasses_json import DataClassJsonMixin

from annofabcli.common.utils import print_json
from annofabcli.statistics.database import Query
from annofabcli.statistics.visualization.dataframe.task import Task
from annofabcli.statistics.visualization.dataframe.user_performance import UserPerformance, WholePerformance
from annofabcli.statistics.visualization.dataframe.whole_productivity_per_date import (
    WholeProductivityPerCompletedDate,
    WholeProductivityPerFirstAnnotationStartedDate,
)
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate


class ProjectDir(DataClassJsonMixin):
    """
    ``annofabcli statistics visualize``コマンドによって出力されたプロジェクトディレクトリに対応するクラス

    Args:
        project_dir: ``annofabcli statistics visualize``コマンドによって出力されたプロジェクトディレクトリ
    """

    FILENAME_WHOLE_PERFORMANCE = "全体の生産性と品質.csv"
    FILENAME_USER_PERFORMANCE = "メンバごとの生産性と品質.csv"
    FILENAME_WHOLE_PRODUCTIVITY_PER_DATE = "日毎の生産量と生産性.csv"
    FILENAME_WHOLE_PRODUCTIVITY_PER_FIRST_ANNOTATION_STARTED_DATE = "教師付開始日毎の生産量と生産性.csv"

    FILENAME_WORKTIME_PER_DATE_USER = "ユーザ_日付list-作業時間.csv"
    FILENAME_TASK_LIST = "タスクlist.csv"

    FILENAME_PROJECT_INFO = "project_info.json"
    FILENAME_MERGE_INFO = "merge_info.json"

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir

    def __repr__(self) -> str:
        return f"ProjectDir(project_dir={self.project_dir!r})"

    def is_merged(self) -> bool:
        """
        マージされたディレクトリかどうか
        """
        return (self.project_dir / self.FILENAME_MERGE_INFO).exists()

    def read_task_list(self) -> Task:
        """`タスクlist.csv`を読み込む。"""
        return Task.from_csv(self.project_dir / self.FILENAME_TASK_LIST)

    def write_task_list(self, obj: Task):
        """`タスクlist.csv`を書き込む。"""
        obj.to_csv(self.project_dir / self.FILENAME_TASK_LIST)

    def write_task_histogram(self, obj: Task):
        """
        タスク単位のヒストグラムを出力します。
        """
        obj.plot_histogram_of_worktime(self.project_dir / "histogram/ヒストグラム-作業時間.html")
        obj.plot_histogram_of_others(self.project_dir / "histogram/ヒストグラム.html")

    def read_whole_performance(self) -> WholePerformance:
        """`全体の生産性と品質.csv`を読み込む。"""
        return WholePerformance.from_csv(self.project_dir / self.FILENAME_WHOLE_PERFORMANCE)

    def write_whole_performance(self, whole_performance: WholePerformance):
        """`全体の生産性と品質.csv`を出力します。"""
        whole_performance.to_csv(self.project_dir / self.FILENAME_WHOLE_PERFORMANCE)

    def read_whole_productivity_per_date(self) -> WholeProductivityPerCompletedDate:
        """
        日ごとの生産性と品質の情報を読み込みます。
        """
        return WholeProductivityPerCompletedDate.from_csv(self.project_dir / self.FILENAME_WHOLE_PRODUCTIVITY_PER_DATE)

    def write_whole_productivity_per_date(self, obj: WholeProductivityPerCompletedDate):
        """
        日ごとの生産性と品質の情報を書き込みます。
        """
        obj.to_csv(self.project_dir / self.FILENAME_WHOLE_PRODUCTIVITY_PER_DATE)

    def read_whole_productivity_per_first_annotation_started_date(
        self,
    ) -> WholeProductivityPerFirstAnnotationStartedDate:
        """
        教師付開始日ごとの生産性と品質の情報を読み込みます。
        """
        return WholeProductivityPerFirstAnnotationStartedDate.from_csv(
            self.project_dir / self.FILENAME_WHOLE_PRODUCTIVITY_PER_FIRST_ANNOTATION_STARTED_DATE
        )

    def write_whole_productivity_per_first_annotation_started_date(
        self, obj: WholeProductivityPerFirstAnnotationStartedDate
    ):
        """
        教師付開始日ごとの生産性と品質の情報を書き込みます。
        """
        obj.to_csv(self.project_dir / self.FILENAME_WHOLE_PRODUCTIVITY_PER_FIRST_ANNOTATION_STARTED_DATE)

    def read_user_performance(self) -> UserPerformance:
        """
        メンバごとの生産性と品質の情報を読み込みます。
        """
        return UserPerformance.from_csv(self.project_dir / self.FILENAME_USER_PERFORMANCE)

    def write_user_performance(self, user_performance: UserPerformance):
        """
        メンバごとの生産性と品質の情報を書き込みます。
        """
        user_performance.to_csv(self.project_dir / self.FILENAME_USER_PERFORMANCE)

    def read_worktime_per_date_user(self) -> WorktimePerDate:
        """`ユーザ_日付list-作業時間.csvを読み込む。"""
        return WorktimePerDate.from_csv(self.project_dir / self.FILENAME_WORKTIME_PER_DATE_USER)

    def write_worktime_per_date_user(self, obj: WorktimePerDate):
        """`ユーザ_日付list-作業時間.csvを書き込む"""
        obj.to_csv(self.project_dir / self.FILENAME_WORKTIME_PER_DATE_USER)

    def read_project_info(self) -> ProjectInfo:
        """
        `project_info.json`を読み込む。
        ただし`self.is_merged()`がFalseのときのみ、読み込みに成功します。

        """
        with (self.project_dir / self.FILENAME_PROJECT_INFO).open() as f:
            return ProjectInfo.from_dict(json.load(f))

    def write_project_info(self, project_info: ProjectInfo):
        """
        `project_info.json`を書き込む。
        """
        print_json(project_info.to_dict(), output=self.project_dir / self.FILENAME_PROJECT_INFO, is_pretty=True)

    def read_merge_info(self) -> MergingInfo:
        """
        `merge_info.json`を読み込む。
        ただし`self.is_merged()`がTrueのときのみ、読み込みに成功します。
        """
        with (self.project_dir / self.FILENAME_MERGE_INFO).open() as f:
            return MergingInfo.from_dict(json.load(f))

    def write_merge_info(self, obj: MergingInfo):
        """
        `merge_info.json`を書き込む。
        """
        print_json(obj.to_dict(), output=self.project_dir / self.FILENAME_MERGE_INFO, is_pretty=True)


@dataclass
class ProjectInfo(DataClassJsonMixin):
    """統計情報を出力したプロジェクトの情報"""

    project_id: str
    project_title: str
    input_data_type: str
    """入力データの種類"""
    measurement_datetime: str
    """計測日時。（2004-04-01T12:00+09:00形式）"""
    query: Query
    """集計対象を絞り込むためのクエリ"""


@dataclass
class MergingInfo(DataClassJsonMixin):
    """可視化結果のファイルをマージする際の情報"""

    target_dir_list: List[str]
    """マージ対象のディレクトリ名"""
    project_info_list: List[ProjectInfo]
    """マージ対象のプロジェクト情報"""
