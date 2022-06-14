from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import pandas

from annofabcli.common.utils import print_csv
from annofabcli.statistics.visualization.dataframe.user_performance import UserPerformance
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate
from annofabcli.statistics.visualization.project_dir import ProjectDir

logger = logging.getLogger(__name__)


class ProjectPerformance:
    """
    プロジェクトごとの生産性と品質
    """

    def __init__(self, df: pandas.DataFrame):
        self.df = df

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    @classmethod
    def _get_start_date_end_date(
        cls, worktime_per_date_user_obj: WorktimePerDate
    ) -> tuple[Optional[str], Optional[str]]:
        df = worktime_per_date_user_obj.df
        df2 = df[df["actual_worktime_hour"] > 0]
        if len(df2) == 0:
            return None, None
        return df2["date"].min(), df2["date"].max()

    @classmethod
    def _get_project_info(cls, project_dir: ProjectDir) -> dict[tuple[str, str], Any]:
        if project_dir.is_merged():
            merge_info = project_dir.read_merge_info()
            project_id_list = []
            project_title_list = []
            for project_info in merge_info.project_info_list:
                project_id_list.append(project_info.project_id)
                project_title_list.append(project_info.project_title)

            # 異なるプロジェクトの種類でマージすることはないはずなので、先頭要素のinput_data_typeを参照する
            input_data_type = merge_info.project_info_list[0].input_data_type

            # マージされている場合、CSVの列に複数の値を表示する
            return {
                ("project_id", ""): project_id_list,
                ("project_title", ""): project_title_list,
                ("input_data_type", ""): input_data_type,
            }

        else:
            project_info = project_dir.read_project_info()
            return {
                ("project_id", ""): project_info.project_id,
                ("project_title", ""): project_info.project_title,
                ("input_data_type", ""): project_info.input_data_type,
            }

    @classmethod
    def _get_series_from_project_dir(cls, project_dir: ProjectDir) -> pandas.Series:
        """1個のプロジェクトディレクトリから、プロジェクトの生産性や品質が格納されたpandas.Seriesを取得します。"""
        # プロジェクトの生産性と品質を取得
        whole_performance_obj = project_dir.read_whole_performance()
        series = whole_performance_obj.series
        series[("dirname", "")] = project_dir.project_dir.name

        start_date, end_date = cls._get_start_date_end_date(project_dir.read_worktime_per_date_user())
        series[("start_date", "")] = start_date
        series[("end_date", "")] = end_date

        for key, value in cls._get_project_info(project_dir).items():
            series[key] = value

        return series

    @classmethod
    def from_project_dirs(cls, project_dir_list: list[ProjectDir]) -> ProjectPerformance:
        row_list: list[pandas.Series] = []
        for project_dir in project_dir_list:
            try:
                row_list.append(cls._get_series_from_project_dir(project_dir))
            except Exception:
                logger.warning(f"'{project_dir}'から、プロジェクトごとの生産性と品質を算出するのに失敗しました。", exc_info=True)
                row_list.append(
                    pandas.Series([project_dir.project_dir.name], index={("dirname", ""): project_dir.project_dir.name})
                )

        return cls(pandas.DataFrame(row_list))

    def to_csv(self, output_file: Path) -> None:
        """
        プロジェクトごとの生産性と品質が格納されたCSVを出力します。
        """
        if not self._validate_df_for_output(output_file):
            return

        phase_list = UserPerformance.get_phase_list(self.df.columns)

        first_columns = [
            ("dirname", ""),
            ("project_title", ""),
            ("project_id", ""),
            ("input_data_type", ""),
            ("start_date", ""),
            ("end_date", ""),
        ]
        value_columns = UserPerformance.get_productivity_columns(phase_list)

        columns = first_columns + value_columns + [("working_user_count", phase) for phase in phase_list]
        print_csv(self.df[columns], output=str(output_file))


class ProjectWorktimePerMonth:
    """
    プロジェクトごとの月ごとの作業時間。
    行方向にプロジェクト、列方向に月ごとの作業時間を出力する。
    """

    def __init__(self, df: pandas.DataFrame):
        self.df = df

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    @classmethod
    def _get_series_from_project_dir(cls, project_dir: ProjectDir) -> pandas.Series:
        """
        1個のプロジェクトディレクトリから、月ごとの作業時間を算出する
        """
        # プロジェクトの生産性と品質を取得
        df = project_dir.read_worktime_per_date_user().df.copy()

        df["dt_date"] = pandas.to_datetime(df["date"])
        series = df.groupby(pandas.Grouper(key="dt_date", freq="M")).sum()["actual_worktime_hour"]

        # indexを"2022-04"という形式にする
        new_index = [str(dt)[0:7] for dt in series.index]
        result = pandas.Series(series.values, index=new_index)
        result["dirname"] = project_dir.project_dir.name
        return result

    @classmethod
    def from_project_dirs(cls, project_dir_list: list[ProjectDir]) -> ProjectWorktimePerMonth:
        row_list: list[pandas.Series] = []
        for project_dir in project_dir_list:
            try:
                row_list.append(cls._get_series_from_project_dir(project_dir))
            except Exception:
                logger.warning(f"'{project_dir}'から、プロジェクトごとの作業時間を算出するのに失敗しました。", exc_info=True)
                row_list.append(
                    pandas.Series([project_dir.project_dir.name], index={("dirname", ""): project_dir.project_dir.name})
                )
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
        print(f"{remain_columns=}")
        for col in header_columns:
            print(f"{col=}")
            remain_columns.remove(col)

        month_columns = sorted(remain_columns)

        columns = header_columns + month_columns
        print_csv(self.df[columns], output=str(output_file))
