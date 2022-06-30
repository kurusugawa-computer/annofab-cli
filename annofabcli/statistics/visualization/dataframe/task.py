from __future__ import annotations

import logging
from pathlib import Path

import bokeh
import bokeh.layouts
import bokeh.palettes
import pandas
import pytz

from annofabcli.common.utils import print_csv
from annofabcli.statistics.histogram import get_histogram_figure, get_sub_title_from_series

logger = logging.getLogger(__name__)


class Task:
    """'タスクlist.csv'に該当するデータフレームをラップしたクラス"""

    def __init__(self, df: pandas.DataFrame) -> None:
        self.df = df

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    @classmethod
    def from_csv(cls, csv_file: Path) -> Task:
        df = pandas.read_csv(str(csv_file))
        return cls(df)

    @staticmethod
    def merge(*obj: Task) -> Task:
        """
        複数のインスタンスをマージします。

        Notes:
            pandas.DataFrameのインスタンス生成のコストを減らすため、複数の引数を受け取れるようにした。
        """
        df_list = [task.df for task in obj]
        df_merged = pandas.concat(df_list)
        return Task(df_merged)

    def plot_histogram_of_worktime(
        self,
        output_file: Path,
        bins: int = 20,
    ):
        """作業時間に関する情報をヒストグラムでプロットする。

        Args:
            output_file (Path): [description]
            bins (int, optional): [description]. Defaults to 20.
        """
        if not self._validate_df_for_output(output_file):
            return

        logger.debug(f"{output_file} を出力します。")
        df = self.df
        histogram_list = [
            dict(
                title="教師付作業時間",
                column="annotation_worktime_hour",
            ),
            dict(
                title="検査作業時間",
                column="inspection_worktime_hour",
            ),
            dict(
                title="受入作業時間",
                column="acceptance_worktime_hour",
            ),
            dict(title="総作業時間", column="worktime_hour"),
        ]

        figure_list = []

        decimals = 2
        for hist in histogram_list:
            column = hist["column"]
            title = hist["title"]
            sub_title = get_sub_title_from_series(df[column], decimals=decimals)
            fig = get_histogram_figure(
                df[column], x_axis_label="作業時間[hour]", y_axis_label="タスク数", title=title, sub_title=sub_title, bins=bins
            )
            figure_list.append(fig)

        # 自動検査したタスクを除外して、検査時間をグラフ化する
        df_ignore_inspection_skipped = df.query("inspection_worktime_hour.notnull() and not inspection_is_skipped")
        sub_title = get_sub_title_from_series(
            df_ignore_inspection_skipped["inspection_worktime_hour"], decimals=decimals
        )
        figure_list.append(
            get_histogram_figure(
                df_ignore_inspection_skipped["inspection_worktime_hour"],
                x_axis_label="作業時間[hour]",
                y_axis_label="タスク数",
                title="検査作業時間(自動検査されたタスクを除外)",
                sub_title=sub_title,
                bins=bins,
            )
        )

        df_ignore_acceptance_skipped = df.query("acceptance_worktime_hour.notnull() and not acceptance_is_skipped")
        sub_title = get_sub_title_from_series(
            df_ignore_acceptance_skipped["acceptance_worktime_hour"], decimals=decimals
        )
        figure_list.append(
            get_histogram_figure(
                df_ignore_acceptance_skipped["acceptance_worktime_hour"],
                x_axis_label="作業時間[hour]",
                y_axis_label="タスク数",
                title="受入作業時間(自動受入されたタスクを除外)",
                sub_title=sub_title,
                bins=bins,
            )
        )

        bokeh_obj = bokeh.layouts.gridplot(figure_list, ncols=3)
        output_file.parent.mkdir(exist_ok=True, parents=True)
        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=output_file.stem)
        bokeh.plotting.save(bokeh_obj)
        logger.debug(f"'{output_file}'を出力しました。")

    def plot_histogram_of_others(
        self,
        output_file: Path,
        bins: int = 20,
    ):
        """アノテーション数や、検査コメント数など、作業時間以外の情報をヒストグラムで表示する。

        Args:
            output_file (Path): [description]
            bins (int, optional): [description]. Defaults to 20.
        """

        def diff_days(s1: pandas.Series, s2: pandas.Series) -> pandas.Series:
            dt1 = pandas.to_datetime(s1)
            dt2 = pandas.to_datetime(s2)

            # タイムゾーンを指定している理由::
            # すべてがNaNのseriesをdatetimeに変換すると、型にタイムゾーンが指定されない。
            # その状態で加算すると、`TypeError: DatetimeArray subtraction must have the same timezones or no timezones`というエラーが発生するため  # noqa:E501
            if not isinstance(dt1.dtype, pandas.DatetimeTZDtype):
                dt1 = dt1.dt.tz_localize(pytz.FixedOffset(540))
            if not isinstance(dt2.dtype, pandas.DatetimeTZDtype):
                dt2 = dt2.dt.tz_localize(pytz.FixedOffset(540))

            return (dt1 - dt2).dt.total_seconds() / 3600 / 24

        if not self._validate_df_for_output(output_file):
            return

        logger.debug(f"{output_file} を出力します。")
        df = self.df.copy()

        df["diff_days_to_first_inspection_started"] = diff_days(
            df["first_inspection_started_datetime"], df["first_annotation_started_datetime"]
        )
        df["diff_days_to_first_acceptance_started"] = diff_days(
            df["first_acceptance_started_datetime"], df["first_annotation_started_datetime"]
        )

        df["diff_days_to_first_acceptance_completed"] = diff_days(
            df["first_acceptance_completed_datetime"], df["first_annotation_started_datetime"]
        )

        histogram_list = [
            dict(column="annotation_count", x_axis_label="アノテーション数", title="アノテーション数"),
            dict(column="input_data_count", x_axis_label="入力データ数", title="入力データ数"),
            dict(column="inspection_comment_count", x_axis_label="検査コメント数", title="検査コメント数"),
            # 経過日数
            dict(
                column="diff_days_to_first_inspection_started",
                x_axis_label="最初の検査を着手するまでの日数",
                title="最初の検査を着手するまでの日数",
            ),
            dict(
                column="diff_days_to_first_acceptance_started",
                x_axis_label="最初の受入を着手するまでの日数",
                title="最初の受入を着手するまでの日数",
            ),
            dict(
                column="diff_days_to_first_acceptance_completed",
                x_axis_label="初めて受入完了状態になるまでの日数",
                title="初めて受入完了状態になるまでの日数",
            ),
            # 差し戻し回数
            dict(
                column="number_of_rejections_by_inspection",
                x_axis_label="検査フェーズでの差し戻し回数",
                title="検査フェーズでの差し戻し回数",
            ),
            dict(
                column="number_of_rejections_by_acceptance",
                x_axis_label="受入フェーズでの差し戻し回数",
                title="受入フェーズでの差し戻し回数",
            ),
        ]

        figure_list = []

        for hist in histogram_list:
            column = hist["column"]
            title = hist["title"]
            x_axis_label = hist["x_axis_label"]
            ser = df[column].dropna()
            sub_title = get_sub_title_from_series(ser, decimals=2)
            fig = get_histogram_figure(
                ser, x_axis_label=x_axis_label, y_axis_label="タスク数", title=title, sub_title=sub_title, bins=bins
            )
            figure_list.append(fig)

        bokeh_obj = bokeh.layouts.gridplot(figure_list, ncols=4)
        output_file.parent.mkdir(exist_ok=True, parents=True)
        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=output_file.stem)
        bokeh.plotting.save(bokeh_obj)
        logger.debug(f"'{output_file}'を出力しました。")

    def to_csv(self, output_file: Path) -> None:
        """
        タスク一覧をTSVで出力する
        Args:
            arg_df:
            dropped_columns:

        Returns:

        """

        if not self._validate_df_for_output(output_file):
            return

        columns = [
            "project_id",
            "task_id",
            "phase",
            "phase_stage",
            "status",
            "number_of_rejections_by_inspection",
            "number_of_rejections_by_acceptance",
            # 1回目の教師付フェーズ
            "first_annotation_user_id",
            "first_annotation_username",
            "first_annotation_worktime_hour",
            "first_annotation_started_datetime",
            # 1回目の検査フェーズ
            "first_inspection_user_id",
            "first_inspection_username",
            "first_inspection_worktime_hour",
            "first_inspection_started_datetime",
            # 1回目の受入フェーズ
            "first_acceptance_user_id",
            "first_acceptance_username",
            "first_acceptance_worktime_hour",
            "first_acceptance_started_datetime",
            # 最後の受入
            "first_acceptance_completed_datetime",
            # 作業時間に関する内容
            "worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
            # 個数
            "input_data_count",
            "annotation_count",
            "inspection_comment_count",
            # タスクの状態
            "inspection_is_skipped",
            "acceptance_is_skipped",
        ]

        print_csv(self.df[columns], str(output_file))
