from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from annofabapi.models import TaskPhase
from dataclasses_json import DataClassJsonMixin

from annofabcli.common.utils import print_json
from annofabcli.statistics.database import Query
from annofabcli.statistics.visualization.dataframe.cumulative_productivity import AbstractPhaseCumulativeProductivity
from annofabcli.statistics.visualization.dataframe.productivity_per_date import AbstractPhaseProductivityPerDate
from annofabcli.statistics.visualization.dataframe.task import Task
from annofabcli.statistics.visualization.dataframe.user_performance import UserPerformance, WholePerformance
from annofabcli.statistics.visualization.dataframe.whole_productivity_per_date import (
    WholeProductivityPerCompletedDate,
    WholeProductivityPerFirstAnnotationStartedDate,
)
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate

logger = logging.getLogger(__name__)


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

    @staticmethod
    def get_phase_name_for_filename(phase: TaskPhase) -> str:
        """
        ファイル名に使うフェーズの名前を返します。
        """
        phase_name = ""
        if phase == TaskPhase.ANNOTATION:
            phase_name = "教師付"
        elif phase == TaskPhase.INSPECTION:
            phase_name = "検査"
        elif phase == TaskPhase.ACCEPTANCE:
            phase_name = "受入"
        return phase_name

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

    def write_cumulative_line_graph(
        self,
        obj: AbstractPhaseCumulativeProductivity,
        phase: TaskPhase,
        user_id_list: Optional[List[str]] = None,
        minimal_output: bool = False,
    ):
        """
        ユーザごとにプロットした累積折れ線グラフを出力します。
        横軸が生産量、縦軸が作業時間です。

        Args:
            user_id_list: 折れ線グラフに表示するユーザ
            minimal_output: 詳細なグラフを出力するかどうか。Trueなら

        """
        output_dir = self.project_dir / "line-graph"

        phase_name = self.get_phase_name_for_filename(phase)
        obj.plot_annotation_metrics(output_dir / f"{phase_name}者用/累積折れ線-横軸_アノテーション数-{phase_name}者用.html", user_id_list)

        if not minimal_output:
            # アノテーション単位より大きい単位の折れ線グラフは不要かもしれないので、オプションにした
            obj.plot_input_data_metrics(
                output_dir / f"{phase_name}者用/累積折れ線-横軸_入力データ数-{phase_name}者用.html", user_id_list
            )

            if phase == TaskPhase.ANNOTATION:
                # 教師付フェーズの場合は、「差し戻し回数」で品質を評価した場合があるので、タスク単位の指標も出力する
                obj.plot_task_metrics(output_dir / f"{phase_name}者用/累積折れ線-横軸_タスク数-{phase_name}者用.html", user_id_list)

    def write_performance_per_started_date_csv(self, obj: AbstractPhaseProductivityPerDate, phase: TaskPhase):
        """
        指定したフェーズの開始日ごとの作業時間や生産性情報を、CSVに出力します。
        """
        phase_name = self.get_phase_name_for_filename(phase)
        obj.to_csv(self.project_dir / Path(f"{phase_name}者_{phase_name}開始日list.csv"))

    def write_performance_line_graph_per_date(
        self, obj: AbstractPhaseProductivityPerDate, phase: TaskPhase, user_id_list: Optional[List[str]] = None
    ):
        """
        指定したフェーズの開始日ごとの作業時間や生産性情報を、折れ線グラフとして出力します。
        """
        output_dir = self.project_dir / "line-graph"
        phase_name = self.get_phase_name_for_filename(phase)
        obj.plot_annotation_metrics(
            output_dir / Path(f"{phase_name}者用/折れ線-横軸_{phase_name}開始日-縦軸_アノテーション単位の指標-{phase_name}者用.html"),
            user_id_list,
        )
        obj.plot_input_data_metrics(
            output_dir / Path(f"{phase_name}者用/折れ線-横軸_{phase_name}開始日-縦軸_入力データ単位の指標-{phase_name}者用.html"), user_id_list
        )

    def read_whole_performance(self) -> WholePerformance:
        """`全体の生産性と品質.csv`を読み込む。"""
        file = self.project_dir / self.FILENAME_WHOLE_PERFORMANCE
        if file.exists():
            return WholePerformance.from_csv(file)
        else:
            logger.warning(f"'{str(file)}'を読み込もうとしましたが、ファイルは存在しません。")
            return WholePerformance.empty()

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

    def write_whole_productivity_line_graph_per_date(self, obj: WholeProductivityPerCompletedDate):
        """
        横軸が日付、縦軸が全体の生産性などをプロットした折れ線グラフを出力します。
        """
        obj.plot(self.project_dir / "line-graph/折れ線-横軸_日-全体.html")
        obj.plot_cumulatively(self.project_dir / "line-graph/累積折れ線-横軸_日-全体.html")

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

    def write_whole_productivity_line_graph_per_annotation_started_date(
        self, obj: WholeProductivityPerFirstAnnotationStartedDate
    ):
        """
        横軸が教師付開始日、縦軸が全体の生産性などをプロットした折れ線グラフを出力します。
        """
        obj.plot(self.project_dir / "line-graph/折れ線-横軸_教師付開始日-全体.html")

    def read_user_performance(self) -> UserPerformance:
        """
        メンバごとの生産性と品質の情報を読み込みます。
        """
        file = self.project_dir / self.FILENAME_USER_PERFORMANCE
        if file.exists():
            return UserPerformance.from_csv(file)
        else:
            logger.warning(f"'{str(file)}'を読み込もうとしましたが、ファイルは存在しません。")
            return UserPerformance.empty()

    def write_user_performance(self, user_performance: UserPerformance):
        """
        メンバごとの生産性と品質の情報を書き込みます。
        """
        user_performance.to_csv(self.project_dir / self.FILENAME_USER_PERFORMANCE)

    def write_user_performance_scatter_plot(self, obj: UserPerformance):
        """
        メンバごとの生産性と品質に関する散布図を出力します。
        """
        output_dir = self.project_dir / "scatter"
        obj.plot_quality(output_dir / "散布図-教師付者の品質と作業量の関係.html")
        obj.plot_productivity_from_monitored_worktime(output_dir / "散布図-アノテーションあたり作業時間と累計作業時間の関係-計測時間.html")
        obj.plot_quality_and_productivity_from_monitored_worktime(
            output_dir / "散布図-アノテーションあたり作業時間と品質の関係-計測時間-教師付者用.html"
        )

        if obj.actual_worktime_exists():
            obj.plot_productivity_from_actual_worktime(output_dir / "散布図-アノテーションあたり作業時間と累計作業時間の関係-実績時間.html")
            obj.plot_quality_and_productivity_from_actual_worktime(
                output_dir / "散布図-アノテーションあたり作業時間と品質の関係-実績時間-教師付者用.html"
            )
        else:
            logger.warning(
                f"実績作業時間の合計値が0なので、実績作業時間関係の次のグラフを'{output_dir}'に出力しません。:: "
                "'散布図-アノテーションあたり作業時間と累計作業時間の関係-実績時間.html',"
                "'散布図-アノテーションあたり作業時間と品質の関係-実績時間-教師付者用'"
            )

    def read_worktime_per_date_user(self) -> WorktimePerDate:
        """`ユーザ_日付list-作業時間.csvを読み込む。"""
        file = self.project_dir / self.FILENAME_WORKTIME_PER_DATE_USER
        if file.exists():
            return WorktimePerDate.from_csv(file)
        else:
            logger.warning(f"'{str(file)}'を読み込もうとしましたが、ファイルは存在しません。")
            return WorktimePerDate.empty()

    def write_worktime_per_date_user(self, obj: WorktimePerDate):
        """`ユーザ_日付list-作業時間.csvを書き込む"""
        obj.to_csv(self.project_dir / self.FILENAME_WORKTIME_PER_DATE_USER)

    def write_worktime_line_graph(self, obj: WorktimePerDate, user_id_list: Optional[list[str]] = None):
        """横軸が日付、縦軸がユーザごとの作業時間である折れ線グラフを出力します。"""
        obj.plot_cumulatively(self.project_dir / "line-graph/累積折れ線-横軸_日-縦軸_作業時間.html", user_id_list)

    def read_project_info(self) -> ProjectInfo:
        """
        `project_info.json`を読み込む。
        ただし`self.is_merged()`がFalseのときのみ、読み込みに成功します。

        """
        with (self.project_dir / self.FILENAME_PROJECT_INFO).open(encoding="utf-8") as f:
            return ProjectInfo.from_dict(json.load(f))

    def write_project_info(self, project_info: ProjectInfo):
        """
        `project_info.json`を書き込む。
        """
        print_json(
            project_info.to_dict(encode_json=True), output=self.project_dir / self.FILENAME_PROJECT_INFO, is_pretty=True
        )

    def read_merge_info(self) -> MergingInfo:
        """
        `merge_info.json`を読み込む。
        ただし`self.is_merged()`がTrueのときのみ、読み込みに成功します。
        """
        with (self.project_dir / self.FILENAME_MERGE_INFO).open(encoding="utf-8") as f:
            return MergingInfo.from_dict(json.load(f))

    def write_merge_info(self, obj: MergingInfo):
        """
        `merge_info.json`を書き込む。
        """
        print_json(obj.to_dict(encode_json=True), output=self.project_dir / self.FILENAME_MERGE_INFO, is_pretty=True)


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
