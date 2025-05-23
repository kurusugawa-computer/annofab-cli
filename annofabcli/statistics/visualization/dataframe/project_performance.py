from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy
import pandas
from annofabapi.models import TaskPhase

from annofabcli.common.pandas import get_frequency_of_monthend
from annofabcli.common.utils import print_csv
from annofabcli.statistics.visualization.dataframe.user_performance import ProductionVolumeColumn
from annofabcli.statistics.visualization.dataframe.whole_performance import WholePerformance
from annofabcli.statistics.visualization.model import TaskCompletionCriteria, WorktimeColumn
from annofabcli.statistics.visualization.project_dir import ProjectDir

logger = logging.getLogger(__name__)


class ProjectPerformance:
    """
    プロジェクトごとの生産性と品質
    """

    def __init__(self, df: pandas.DataFrame, *, custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None) -> None:
        self.df = df
        self.custom_production_volume_list = custom_production_volume_list if custom_production_volume_list is not None else []

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    @classmethod
    def _get_project_info(cls, project_dir: ProjectDir) -> pandas.Series:
        index = pandas.MultiIndex.from_tuples([("project_id", ""), ("project_title", ""), ("input_data_type", "")])

        if project_dir.is_merged():
            try:
                merge_info = project_dir.read_merge_info()

                project_id_list = []
                project_title_list = []
                for project_info in merge_info.project_info_list:
                    project_id_list.append(project_info.project_id)
                    project_title_list.append(project_info.project_title)

                # 異なるプロジェクトの種類でマージすることはないはずなので、先頭要素のinput_data_typeを参照する
                input_data_type = merge_info.project_info_list[0].input_data_type

                # マージされている場合、CSVの列に複数の値を表示する
                return pandas.Series([project_id_list, project_title_list, input_data_type], index=index)

            except Exception:
                logger.warning(f"'{project_dir}'の`merge_info.json`の読み込みに失敗しました。", exc_info=True)
                return pandas.Series([numpy.nan, numpy.nan, numpy.nan], index=index)

        else:
            try:
                project_info = project_dir.read_project_info()
                return pandas.Series([project_info.project_id, project_info.project_title, project_info.input_data_type], index=index)

            except Exception:
                logger.warning(f"'{project_dir}'の`project_info.json`の読み込みに失敗しました。", exc_info=True)
                return pandas.Series([numpy.nan, numpy.nan, numpy.nan], index=index)

    @classmethod
    def _get_series_from_project_dir(cls, project_dir: ProjectDir) -> pandas.Series:
        """1個のプロジェクトディレクトリから、プロジェクトの生産性や品質が格納されたpandas.Seriesを取得します。"""

        series = pandas.Series([project_dir.project_dir.name], index=pandas.MultiIndex.from_tuples([("dirname", "")]))
        # プロジェクトの基本情報を取得
        project_info_series = cls._get_project_info(project_dir)
        series = pandas.concat([series, project_info_series])
        # プロジェクトの生産性と品質を取得
        try:
            whole_performance_obj = project_dir.read_whole_performance()
            series = pandas.concat([series, whole_performance_obj.series])
        except Exception:
            logger.warning(f"'{project_dir}'の全体の生産性と品質を取得するのに失敗しました。", exc_info=True)
            series = pandas.concat([series, WholePerformance.empty(TaskCompletionCriteria.ACCEPTANCE_COMPLETED).series])

        return series

    def get_phase_list(self) -> list[str]:
        tmp_set = {c1 for c0, c1 in self.df.columns if c0 == "monitored_worktime_hour"}
        return [e.value for e in TaskPhase if e.value in tmp_set]

    @classmethod
    def from_project_dirs(cls, project_dir_list: list[ProjectDir], *, custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None) -> ProjectPerformance:
        row_list: list[pandas.Series] = [cls._get_series_from_project_dir(project_dir) for project_dir in project_dir_list]
        return cls(pandas.DataFrame(row_list), custom_production_volume_list=custom_production_volume_list)

    def to_csv(self, output_file: Path) -> None:
        """
        プロジェクトごとの生産性と品質が格納されたCSVを出力します。
        """
        if not self._validate_df_for_output(output_file):
            return

        phase_list = self.get_phase_list()

        first_columns = [("dirname", ""), ("project_title", ""), ("project_id", ""), ("input_data_type", "")]

        production_volume_columns = ["input_data_count", "annotation_count", *[e.value for e in self.custom_production_volume_list]]
        value_columns = WholePerformance.get_series_index(phase_list, production_volume_columns=production_volume_columns)  # type: ignore[arg-type]

        columns = first_columns + value_columns
        print_csv(self.df[columns], output=str(output_file))


class ProjectWorktimePerMonth:
    """
    プロジェクトごとの月ごとの作業時間。
    行方向にプロジェクト、列方向に月ごとの作業時間を出力する。
    """

    def __init__(self, df: pandas.DataFrame) -> None:
        self.df = df

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    @classmethod
    def _get_series_from_project_dir(cls, project_dir: ProjectDir, worktime_column: WorktimeColumn) -> pandas.Series:
        """
        1個のプロジェクトディレクトリから、月ごとの作業時間を算出する
        """
        df = project_dir.read_worktime_per_date_user().df.copy()
        df["dt_date"] = pandas.to_datetime(df["date"], format="ISO8601")

        series = df.groupby(pandas.Grouper(key="dt_date", freq=get_frequency_of_monthend())).sum(numeric_only=True)[worktime_column.value]
        # indexを"2022-04"という形式にする
        new_index = [str(dt)[0:7] for dt in series.index]
        result = pandas.Series(series.values, index=new_index)
        result["dirname"] = project_dir.project_dir.name
        return result

    @classmethod
    def from_project_dirs(cls, project_dir_list: list[ProjectDir], worktime_column: WorktimeColumn) -> ProjectWorktimePerMonth:
        """
        プロジェクトディレクトリのlistから、インスタンスを生成します。
        Args:
            project_dir_list (list[ProjectDir]): _description_
            worktime_column: 作業時間を表す列

        Returns:
            ProjectWorktimePerMonth: _description_
        """
        row_list: list[pandas.Series] = []
        for project_dir in project_dir_list:
            try:
                row_list.append(cls._get_series_from_project_dir(project_dir, worktime_column))
            except Exception:
                logger.warning(f"'{project_dir}'から、プロジェクトごとの作業時間を算出するのに失敗しました。", exc_info=True)
                row_list.append(pandas.Series([project_dir.project_dir.name], index=["dirname"]))
        df = pandas.DataFrame(row_list)
        df.fillna(0, inplace=True)
        return cls(df)

    def to_csv(self, output_file: Path) -> None:
        """
        行方向にプロジェクト、列方向に月が並んだ作業時間のCSVを出力します。
        """
        if not self._validate_df_for_output(output_file):
            return

        header_columns = ["dirname"]
        remain_columns = list(self.df.columns)
        for col in header_columns:
            remain_columns.remove(col)

        month_columns = sorted(remain_columns)

        columns = header_columns + month_columns
        print_csv(self.df[columns], output=str(output_file))
