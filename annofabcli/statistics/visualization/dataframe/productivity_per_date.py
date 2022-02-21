# pylint: disable=too-many-lines
"""
日ごとユーザごとの生産性
"""
from __future__ import annotations

import abc
import logging
from pathlib import Path
from typing import Optional

import bokeh
import bokeh.layouts
import bokeh.palettes
import pandas
from bokeh.plotting import ColumnDataSource, figure
from dateutil.parser import parse

from annofabcli.common.utils import datetime_to_date, print_csv
from annofabcli.statistics.linegraph import (
    WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX,
    add_legend_to_figure,
    create_hover_tool,
    get_color_from_palette,
    get_plotted_user_id_list,
    get_weekly_sum,
    plot_line_and_circle,
    plot_moving_average,
    write_bokeh_graph,
)

logger = logging.getLogger(__name__)


class AbstractRoleProductivityPerDate(abc.ABC):
    """ロールごとの日ごとの生産性に関する情報を格納する抽象クラス"""

    PLOT_WIDTH = 1200
    PLOT_HEIGHT = 600

    def __init__(self, df: pandas.DataFrame) -> None:
        self.df = df

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    @classmethod
    @abc.abstractmethod
    def from_df_task(cls, df_task: pandas.DataFrame) -> AbstractRoleProductivityPerDate:
        pass

    @abc.abstractmethod
    def to_csv(self, output_file: Path):
        pass

    @abc.abstractmethod
    def plot_input_data_metrics(self, output_file: Path, target_user_id_list: Optional[list[str]] = None):
        pass

    @abc.abstractmethod
    def plot_annotation_metrics(self, output_file: Path, target_user_id_list: Optional[list[str]] = None):
        pass


class AnnotatorProductivityPerDate(AbstractRoleProductivityPerDate):
    """教師付開始日ごとの教師付者の生産性に関する情報"""

    @classmethod
    def from_df_task(cls, df_task: pandas.DataFrame) -> AnnotatorProductivityPerDate:
        """
        日毎、ユーザごとの情報を出力する。

        Args:
            task_df:

        Returns:

        """
        new_df = df_task.copy()
        new_df["first_annotation_started_date"] = new_df["first_annotation_started_datetime"].map(
            lambda e: datetime_to_date(e) if e is not None and isinstance(e, str) else None
        )
        new_df["task_count"] = 1  # 集計用

        # first_annotation_user_id と first_annotation_usernameの両方を指定している理由：
        # first_annotation_username を取得するため
        group_obj = new_df.groupby(
            ["first_annotation_started_date", "first_annotation_user_id", "first_annotation_username"],
            as_index=False,
        )

        sum_df = group_obj[
            [
                "first_annotation_worktime_hour",
                "annotation_worktime_hour",
                "inspection_worktime_hour",
                "acceptance_worktime_hour",
                "worktime_hour",
                "task_count",
                "input_data_count",
                "annotation_count",
                "inspection_comment_count",
            ]
        ].sum()

        for denominator_column in ["input_data_count", "annotation_count"]:
            for phase in ["annotation", "inspection", "acceptance"]:
                numerator_column = f"{phase}_worktime_hour"
                sum_df[f"{numerator_column}/{denominator_column}"] = (
                    sum_df[numerator_column] / sum_df[denominator_column]
                )

        sum_df["inspection_comment_count/annotation_count"] = (
            sum_df["inspection_comment_count"] / sum_df["annotation_count"]
        )
        sum_df["inspection_comment_count/input_data_count"] = (
            sum_df["inspection_comment_count"] / sum_df["annotation_count"]
        )

        return cls(sum_df)

    @staticmethod
    def _get_df_sequential_date(df: pandas.DataFrame) -> pandas.DataFrame:
        """連続した日付のDataFrameを生成する。"""
        df_date = pandas.DataFrame(
            {
                "first_annotation_started_date": [
                    str(e.date())
                    for e in pandas.date_range(
                        df["first_annotation_started_date"].min(),
                        df["first_annotation_started_date"].max(),
                    )
                ]
            }
        )
        df2 = df_date.merge(df, how="left", on="first_annotation_started_date")
        df2["dt_first_annotation_started_date"] = df2["first_annotation_started_date"].map(lambda e: parse(e).date())

        assert len(df) > 0
        first_row = df.iloc[0]
        df2["first_annotation_user_id"] = first_row["first_annotation_user_id"]
        df2["first_annotation_username"] = first_row["first_annotation_username"]

        df2.fillna(
            {
                key: 0
                for key in [
                    "first_annotation_worktime_hour",
                    "annotation_worktime_hour",
                    "inspection_worktime_hour",
                    "acceptance_worktime_hour",
                    "worktime_hour",
                    "inspection_comment_count",
                    "task_count",
                    "input_data_count",
                    "annotation_count",
                    "inspection_comment",
                ]
            },
            inplace=True,
        )

        return df2

    def plot_annotation_metrics(
        self,
        output_file: Path,
        target_user_id_list: Optional[list[str]] = None,
    ):
        """
        生産性を教師付作業者ごとにプロットする。

        Args:
            df:
            first_annotation_user_id_list:

        Returns:

        """

        if not self._validate_df_for_output(output_file):
            return

        df = self.df.copy()

        if target_user_id_list is not None:
            user_id_list = target_user_id_list
        else:
            user_id_list = (
                df.sort_values(by="first_annotation_started_date", ascending=False)["first_annotation_user_id"]
                .dropna()
                .unique()
                .tolist()
            )

        user_id_list = get_plotted_user_id_list(user_id_list)

        fig_info_list = [
            dict(
                title="教師付開始日ごとの教師付作業時間",
                y_column_name="annotation_worktime_hour",
                y_axis_label="教師付作業時間[hour]",
            ),
            dict(
                title="教師付開始日ごとのアノテーションあたり教師付作業時間",
                y_column_name="annotation_worktime_minute/annotation_count",
                y_axis_label="アノテーションあたり教師付時間[min/annotation]",
            ),
            dict(
                title="教師付開始日ごとのアノテーションあたり教師付作業時間(1週間移動平均)",
                y_column_name=f"annotation_worktime_minute/annotation_count{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}",
                y_axis_label="アノテーションあたり教師付時間[min/annotation]",
            ),
            dict(
                title="教師付開始日ごとのアノテーションあたり検査コメント数",
                y_column_name="inspection_comment_count/annotation_count",
                y_axis_label="アノテーションあたり検査コメント数",
            ),
            dict(
                title="教師付開始日ごとのアノテーションあたり検査コメント数(1週間移動平均)",
                y_column_name=f"inspection_comment_count/annotation_count{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}",
                y_axis_label="アノテーションあたり検査コメント数",
            ),
        ]

        logger.debug(f"{output_file} を出力します。")

        figs: list[bokeh.plotting.Figure] = []
        for fig_info in fig_info_list:
            figs.append(
                figure(
                    plot_width=self.PLOT_WIDTH,
                    plot_height=self.PLOT_HEIGHT,
                    title=fig_info["title"],
                    x_axis_label="教師付開始日",
                    x_axis_type="datetime",
                    y_axis_label=fig_info["y_axis_label"],
                )
            )

        for user_index, user_id in enumerate(user_id_list):
            df_subset = df[df["first_annotation_user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            df_subset = self._get_df_sequential_date(df_subset)
            df_subset["annotation_worktime_minute/annotation_count"] = (
                df_subset["annotation_worktime_hour"] * 60 / df_subset["annotation_count"]
            )
            df_subset[f"annotation_worktime_minute/annotation_count{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = (
                get_weekly_sum(df_subset["annotation_worktime_hour"])
                * 60
                / get_weekly_sum(df_subset["annotation_count"])
            )
            df_subset[
                f"inspection_comment_count/annotation_count{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"
            ] = get_weekly_sum(df_subset["inspection_comment_count"]) / get_weekly_sum(df_subset["annotation_count"])

            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["first_annotation_username"]

            for fig, fig_info in zip(figs, fig_info_list):
                y_column_name = fig_info["y_column_name"]
                if y_column_name.endswith(WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX):
                    plot_moving_average(
                        fig,
                        source=source,
                        x_column_name="dt_first_annotation_started_date",
                        y_column_name=y_column_name,
                        legend_label=username,
                        color=color,
                    )

                else:
                    plot_line_and_circle(
                        fig,
                        x_column_name="dt_first_annotation_started_date",
                        y_column_name=y_column_name,
                        source=source,
                        legend_label=username,
                        color=color,
                    )

        hover_tool = create_hover_tool(
            [
                "first_annotation_user_id",
                "first_annotation_username",
                "first_annotation_started_date",
                "annotation_worktime_hour",
                "task_count",
                "input_data_count",
                "annotation_count",
                "inspection_comment_count",
            ]
        )
        for fig in figs:
            fig.add_tools(hover_tool)
            add_legend_to_figure(fig)

        write_bokeh_graph(bokeh.layouts.column(figs), output_file)

    def plot_input_data_metrics(
        self,
        output_file: Path,
        target_user_id_list: Optional[list[str]] = None,
    ):
        """
        教師付者の入力データ単位の生産性情報を折れ線グラフでプロットする。
        """

        if not self._validate_df_for_output(output_file):
            return

        df = self.df.copy()

        if target_user_id_list is not None:
            user_id_list = target_user_id_list
        else:
            user_id_list = (
                df.sort_values(by="first_annotation_started_date", ascending=False)["first_annotation_user_id"]
                .dropna()
                .unique()
                .tolist()
            )

        user_id_list = get_plotted_user_id_list(user_id_list)

        fig_info_list = [
            dict(
                title="教師付開始日ごとの教師付作業時間",
                y_column_name="annotation_worktime_hour",
                y_axis_label="教師付作業時間[hour]",
            ),
            dict(
                title="教師付開始日ごとの入力データあたり教師付作業時間",
                y_column_name="annotation_worktime_minute/input_data_count",
                y_axis_label="入力データあたり教師付時間[min/input_data]",
            ),
            dict(
                title="教師付開始日ごとの入力データあたり教師付作業時間(1週間移動平均)",
                y_column_name=f"annotation_worktime_minute/input_data_count{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}",
                y_axis_label="入力データあたり教師付時間[min/annotation]",
            ),
            dict(
                title="教師付開始日ごとの入力データあたり検査コメント数",
                y_column_name="inspection_comment_count/input_data_count",
                y_axis_label="入力データあたり検査コメント数",
            ),
            dict(
                title="教師付開始日ごとの入力データあたり検査コメント数(1週間移動平均)",
                y_column_name=f"inspection_comment_count/input_data_count{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}",
                y_axis_label="入力データあたり検査コメント数",
            ),
        ]

        logger.debug(f"{output_file} を出力します。")

        figs: list[bokeh.plotting.Figure] = []
        for fig_info in fig_info_list:
            figs.append(
                figure(
                    plot_width=self.PLOT_WIDTH,
                    plot_height=self.PLOT_HEIGHT,
                    title=fig_info["title"],
                    x_axis_label="教師付開始日",
                    x_axis_type="datetime",
                    y_axis_label=fig_info["y_axis_label"],
                )
            )

        for user_index, user_id in enumerate(user_id_list):
            df_subset = df[df["first_annotation_user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            df_subset = self._get_df_sequential_date(df_subset)
            df_subset["annotation_worktime_minute/input_data_count"] = (
                df_subset["annotation_worktime_hour"] * 60 / df_subset["input_data_count"]
            )

            df_subset[f"annotation_worktime_minute/input_data_count{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = (
                get_weekly_sum(df_subset["annotation_worktime_hour"])
                * 60
                / get_weekly_sum(df_subset["input_data_count"])
            )
            df_subset[
                f"inspection_comment_count/input_data_count{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"
            ] = get_weekly_sum(df_subset["inspection_comment_count"]) / get_weekly_sum(df_subset["input_data_count"])

            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["first_annotation_username"]

            for fig, fig_info in zip(figs, fig_info_list):
                y_column_name = fig_info["y_column_name"]
                if y_column_name.endswith(WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX):
                    plot_moving_average(
                        fig,
                        source=source,
                        x_column_name="dt_first_annotation_started_date",
                        y_column_name=y_column_name,
                        legend_label=username,
                        color=color,
                    )

                else:
                    plot_line_and_circle(
                        fig,
                        x_column_name="dt_first_annotation_started_date",
                        y_column_name=y_column_name,
                        source=source,
                        legend_label=username,
                        color=color,
                    )

        hover_tool = create_hover_tool(
            [
                "first_annotation_user_id",
                "first_annotation_username",
                "first_annotation_started_date",
                "annotation_worktime_hour",
                "task_count",
                "input_data_count",
                "annotation_count",
                "inspection_comment_count",
            ]
        )
        for fig in figs:
            fig.add_tools(hover_tool)
            add_legend_to_figure(fig)

        write_bokeh_graph(bokeh.layouts.column(figs), output_file)

    def to_csv(self, output_file: Path) -> None:

        if not self._validate_df_for_output(output_file):
            return

        production_columns = [
            "first_annotation_started_date",
            "first_annotation_user_id",
            "first_annotation_username",
            "task_count",
            "input_data_count",
            "annotation_count",
            "inspection_comment_count",
            "worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
        ]

        velocity_columns = [
            f"{numerator}/{denominator}"
            for numerator in ["annotation_worktime_hour", "inspection_worktime_hour", "acceptance_worktime_hour"]
            for denominator in ["input_data_count", "annotation_count"]
        ]

        columns = (
            production_columns
            + velocity_columns
            + ["inspection_comment_count/input_data_count", "inspection_comment_count/annotation_count"]
        )

        print_csv(self.df[columns], output=str(output_file))


class InspectorProductivityPerDate(AbstractRoleProductivityPerDate):
    """検査開始日ごとの検査者の生産性に関する情報"""

    @classmethod
    def from_df_task(cls, df_task: pandas.DataFrame) -> InspectorProductivityPerDate:
        """
        検査開始日ごとの受入者の生産性に関するDataFrameを生成する。

        Args:
            df_task:

        Returns:

        """
        new_df = df_task.copy()
        new_df["first_inspection_started_date"] = new_df["first_inspection_started_datetime"].map(
            lambda e: datetime_to_date(e) if e is not None and isinstance(e, str) else None
        )
        new_df["task_count"] = 1  # 集計用

        # first_inspection_username を列に追加するために、first_inspection_user_idだけでなくfirst_inspection_usernameもgroupby関数のキーに指定した
        group_obj = new_df.groupby(
            ["first_inspection_started_date", "first_inspection_user_id", "first_inspection_username"],
            as_index=False,
        )

        sum_df = group_obj[
            [
                "first_inspection_worktime_hour",
                "inspection_worktime_hour",
                "task_count",
                "input_data_count",
                "annotation_count",
            ]
        ].sum()

        sum_df["inspection_worktime_hour/annotation_count"] = (
            sum_df["inspection_worktime_hour"] / sum_df["annotation_count"]
        )
        sum_df["inspection_worktime_hour/input_data_count"] = (
            sum_df["inspection_worktime_hour"] / sum_df["input_data_count"]
        )

        return cls(sum_df)

    @staticmethod
    def _get_df_sequential_date(df: pandas.DataFrame) -> pandas.DataFrame:
        """連続した日付のDataFrameを生成する。"""
        df_date = pandas.DataFrame(
            {
                "first_inspection_started_date": [
                    str(e.date())
                    for e in pandas.date_range(
                        df["first_inspection_started_date"].min(),
                        df["first_inspection_started_date"].max(),
                    )
                ]
            }
        )
        df2 = df_date.merge(df, how="left", on="first_inspection_started_date")
        df2["dt_first_inspection_started_date"] = df2["first_inspection_started_date"].map(lambda e: parse(e).date())

        assert len(df) > 0
        first_row = df.iloc[0]
        df2["first_inspection_user_id"] = first_row["first_inspection_user_id"]
        df2["first_inspection_username"] = first_row["first_inspection_username"]

        df2.fillna(
            {
                key: 0
                for key in [
                    "first_inspection_worktime_hour",
                    "inspection_worktime_hour",
                    "task_count",
                    "input_data_count",
                    "annotation_count",
                ]
            },
            inplace=True,
        )
        return df2

    def plot_annotation_metrics(
        self,
        output_file: Path,
        target_user_id_list: Optional[list[str]] = None,
    ):
        """
        アノテーション単位の生産性を受入作業者ごとにプロットする。

        """

        if not self._validate_df_for_output(output_file):
            return

        df = self.df.copy()

        if target_user_id_list is not None:
            user_id_list = target_user_id_list
        else:
            user_id_list = (
                df.sort_values(by="first_inspection_started_date", ascending=False)["first_inspection_user_id"]
                .dropna()
                .unique()
                .tolist()
            )

        user_id_list = get_plotted_user_id_list(user_id_list)

        fig_info_list = [
            dict(
                title="検査開始日ごとの受入作業時間",
                y_column_name="inspection_worktime_hour",
                y_axis_label="検査作業時間[hour]",
            ),
            dict(
                title="検査開始日ごとのアノテーションあたり検査作業時間",
                y_column_name="inspection_worktime_minute/annotation_count",
                y_axis_label="アノテーションあたり検査作業時間[min/annotation]",
            ),
            dict(
                title="検査開始日ごとのアノテーションあたり検査作業時間(1週間移動平均)",
                y_column_name=f"inspection_worktime_minute/annotation_count{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}",
                y_axis_label="アノテーションあたり検査作業時間[min/annotation]",
            ),
        ]

        logger.debug(f"{output_file} を出力します。")

        figs: list[bokeh.plotting.Figure] = []
        for fig_info in fig_info_list:
            figs.append(
                figure(
                    plot_width=self.PLOT_WIDTH,
                    plot_height=self.PLOT_HEIGHT,
                    title=fig_info["title"],
                    x_axis_label="受入開始日",
                    x_axis_type="datetime",
                    y_axis_label=fig_info["y_axis_label"],
                )
            )

        for user_index, user_id in enumerate(user_id_list):
            df_subset = df[df["first_inspection_user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            df_subset = self._get_df_sequential_date(df_subset)
            df_subset["inspection_worktime_minute/annotation_count"] = (
                df_subset["inspection_worktime_hour"] * 60 / df_subset["annotation_count"]
            )
            df_subset[f"inspection_worktime_minute/annotation_count{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = (
                get_weekly_sum(df_subset["inspection_worktime_hour"])
                * 60
                / get_weekly_sum(df_subset["annotation_count"])
            )

            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["first_inspection_username"]

            for fig, fig_info in zip(figs, fig_info_list):
                y_column_name = fig_info["y_column_name"]
                if y_column_name.endswith(WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX):
                    plot_moving_average(
                        fig,
                        source=source,
                        x_column_name="dt_first_inspection_started_date",
                        y_column_name=y_column_name,
                        legend_label=username,
                        color=color,
                    )

                else:
                    plot_line_and_circle(
                        fig,
                        x_column_name="dt_first_inspection_started_date",
                        y_column_name=y_column_name,
                        source=source,
                        legend_label=username,
                        color=color,
                    )

        hover_tool = create_hover_tool(
            [
                "first_inspection_user_id",
                "first_inspection_username",
                "first_inspection_started_date",
                "inspection_worktime_hour",
                "task_count",
                "input_data_count",
                "annotation_count",
            ]
        )
        for fig in figs:
            fig.add_tools(hover_tool)
            add_legend_to_figure(fig)

        write_bokeh_graph(bokeh.layouts.column(figs), output_file)

    def plot_input_data_metrics(
        self,
        output_file: Path,
        target_user_id_list: Optional[list[str]] = None,
    ):
        """
        検査者の入力データ単位の生産性情報を折れ線グラフでプロットする。
        """

        if not self._validate_df_for_output(output_file):
            return

        df = self.df.copy()

        if target_user_id_list is not None:
            user_id_list = target_user_id_list
        else:
            user_id_list = (
                df.sort_values(by="first_inspection_started_date", ascending=False)["first_inspection_user_id"]
                .dropna()
                .unique()
                .tolist()
            )

        user_id_list = get_plotted_user_id_list(user_id_list)

        fig_info_list = [
            dict(
                title="検査開始日ごとの検査作業時間",
                y_column_name="inspection_worktime_hour",
                y_axis_label="教師付作業時間[hour]",
            ),
            dict(
                title="検査開始日ごとの入力データあたり検査作業時間",
                y_column_name="inspection_worktime_minute/input_data_count",
                y_axis_label="入力データあたり検査時間[min/input_data]",
            ),
            dict(
                title="検査開始日ごとの入力データあたり検査作業時間(1週間移動平均)",
                y_column_name=f"inspection_worktime_minute/input_data_count{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}",
                y_axis_label="入力データあたり検査時間[min/annotation]",
            ),
        ]

        logger.debug(f"{output_file} を出力します。")

        figs: list[bokeh.plotting.Figure] = []
        for fig_info in fig_info_list:
            figs.append(
                figure(
                    plot_width=self.PLOT_WIDTH,
                    plot_height=self.PLOT_HEIGHT,
                    title=fig_info["title"],
                    x_axis_label="検査開始日",
                    x_axis_type="datetime",
                    y_axis_label=fig_info["y_axis_label"],
                )
            )

        for user_index, user_id in enumerate(user_id_list):
            df_subset = df[df["first_inspection_user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            df_subset = self._get_df_sequential_date(df_subset)
            df_subset["inspection_worktime_minute/input_data_count"] = (
                df_subset["inspection_worktime_hour"] * 60 / df_subset["input_data_count"]
            )
            df_subset[f"inspection_worktime_minute/input_data_count{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = (
                get_weekly_sum(df_subset["inspection_worktime_hour"])
                * 60
                / get_weekly_sum(df_subset["input_data_count"])
            )

            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["first_inspection_username"]

            for fig, fig_info in zip(figs, fig_info_list):
                y_column_name = fig_info["y_column_name"]
                if y_column_name.endswith(WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX):
                    plot_moving_average(
                        fig,
                        source=source,
                        x_column_name="dt_first_inspection_started_date",
                        y_column_name=y_column_name,
                        legend_label=username,
                        color=color,
                    )

                else:
                    plot_line_and_circle(
                        fig,
                        x_column_name="dt_first_inspection_started_date",
                        y_column_name=y_column_name,
                        source=source,
                        legend_label=username,
                        color=color,
                    )

        hover_tool = create_hover_tool(
            [
                "first_annotation_user_id",
                "first_inspection_username",
                "first_inspection_started_date",
                "inspection_worktime_hour",
                "task_count",
                "input_data_count",
                "annotation_count",
                "inspection_comment_count",
            ]
        )
        for fig in figs:
            fig.add_tools(hover_tool)
            add_legend_to_figure(fig)

        write_bokeh_graph(bokeh.layouts.column(figs), output_file)

    def to_csv(self, output_file: Path) -> None:
        """
        検査作業者の日ごとの生産性が記載されたCSVを出力する。

        """
        if not self._validate_df_for_output(output_file):
            return

        production_columns = [
            "first_inspection_started_date",
            "first_inspection_user_id",
            "first_inspection_username",
            "task_count",
            "input_data_count",
            "annotation_count",
            "inspection_worktime_hour",
        ]

        velocity_columns = [
            f"inspection_worktime_hour/{denominator}" for denominator in ["input_data_count", "annotation_count"]
        ]

        columns = production_columns + velocity_columns

        print_csv(self.df[columns], output=str(output_file))


class AcceptorProductivityPerDate(AbstractRoleProductivityPerDate):
    """受入開始日ごとの受入者の生産性に関する情報"""

    @classmethod
    def from_df_task(cls, df_task: pandas.DataFrame) -> AcceptorProductivityPerDate:
        """
        受入開始日ごとの受入者の生産性に関するDataFrameを生成する。

        Args:
            df_task:

        Returns:

        """
        new_df = df_task.copy()
        new_df["first_acceptance_started_date"] = new_df["first_acceptance_started_datetime"].map(
            lambda e: datetime_to_date(e) if e is not None and isinstance(e, str) else None
        )
        new_df["task_count"] = 1  # 集計用

        # first_acceptance_username を列に追加するために、first_acceptance_user_idだけでなくfirst_acceptance_usernameもgroupby関数のキーに指定した
        group_obj = new_df.groupby(
            ["first_acceptance_started_date", "first_acceptance_user_id", "first_acceptance_username"],
            as_index=False,
        )

        sum_df = group_obj[
            [
                "first_acceptance_worktime_hour",
                "acceptance_worktime_hour",
                "task_count",
                "input_data_count",
                "annotation_count",
            ]
        ].sum()

        sum_df["acceptance_worktime_hour/annotation_count"] = (
            sum_df["acceptance_worktime_hour"] / sum_df["annotation_count"]
        )
        sum_df["acceptance_worktime_hour/input_data_count"] = (
            sum_df["acceptance_worktime_hour"] / sum_df["input_data_count"]
        )

        return AcceptorProductivityPerDate(sum_df)

    @staticmethod
    def _get_df_sequential_date(df: pandas.DataFrame) -> pandas.DataFrame:
        """連続した日付のDataFrameを生成する。"""
        df_date = pandas.DataFrame(
            {
                "first_acceptance_started_date": [
                    str(e.date())
                    for e in pandas.date_range(
                        df["first_acceptance_started_date"].min(),
                        df["first_acceptance_started_date"].max(),
                    )
                ]
            }
        )
        df2 = df_date.merge(df, how="left", on="first_acceptance_started_date")
        df2["dt_first_acceptance_started_date"] = df2["first_acceptance_started_date"].map(lambda e: parse(e).date())

        assert len(df) > 0
        first_row = df.iloc[0]
        df2["first_acceptance_user_id"] = first_row["first_acceptance_user_id"]
        df2["first_acceptance_username"] = first_row["first_acceptance_username"]

        df2.fillna(
            {
                key: 0
                for key in [
                    "first_acceptance_worktime_hour",
                    "acceptance_worktime_hour",
                    "task_count",
                    "input_data_count",
                    "annotation_count",
                ]
            },
            inplace=True,
        )
        return df2

    def plot_annotation_metrics(
        self,
        output_file: Path,
        target_user_id_list: Optional[list[str]] = None,
    ):
        """
        アノテーション単位の生産性を受入作業者ごとにプロットする。

        """

        if not self._validate_df_for_output(output_file):
            return

        df = self.df.copy()

        if target_user_id_list is not None:
            user_id_list = target_user_id_list
        else:
            user_id_list = (
                df.sort_values(by="first_acceptance_started_date", ascending=False)["first_acceptance_user_id"]
                .dropna()
                .unique()
                .tolist()
            )

        user_id_list = get_plotted_user_id_list(user_id_list)

        fig_info_list = [
            dict(
                title="受入開始日ごとの受入作業時間",
                y_column_name="acceptance_worktime_hour",
                y_axis_label="受入作業時間[hour]",
            ),
            dict(
                title="受入開始日ごとのアノテーションあたり受入作業時間",
                y_column_name="acceptance_worktime_minute/annotation_count",
                y_axis_label="アノテーションあたり受入時間[min/annotation]",
            ),
            dict(
                title="受入開始日ごとのアノテーションあたり受入作業時間(1週間移動平均)",
                y_column_name=f"acceptance_worktime_minute/annotation_count{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}",
                y_axis_label="アノテーションあたり受入時間[min/annotation]",
            ),
        ]

        logger.debug(f"{output_file} を出力します。")

        figs: list[bokeh.plotting.Figure] = []
        for fig_info in fig_info_list:
            figs.append(
                figure(
                    plot_width=self.PLOT_WIDTH,
                    plot_height=self.PLOT_HEIGHT,
                    title=fig_info["title"],
                    x_axis_label="受入開始日",
                    x_axis_type="datetime",
                    y_axis_label=fig_info["y_axis_label"],
                )
            )

        for user_index, user_id in enumerate(user_id_list):
            df_subset = df[df["first_acceptance_user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            df_subset = self._get_df_sequential_date(df_subset)
            df_subset["acceptance_worktime_minute/annotation_count"] = (
                df_subset["acceptance_worktime_hour"] * 60 / df_subset["annotation_count"]
            )

            df_subset[f"acceptance_worktime_minute/annotation_count{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = (
                get_weekly_sum(df_subset["acceptance_worktime_hour"])
                * 60
                / get_weekly_sum(df_subset["annotation_count"])
            )

            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["first_acceptance_username"]

            for fig, fig_info in zip(figs, fig_info_list):
                y_column_name = fig_info["y_column_name"]
                if y_column_name.endswith(WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX):
                    plot_moving_average(
                        fig,
                        source=source,
                        x_column_name="dt_first_acceptance_started_date",
                        y_column_name=y_column_name,
                        legend_label=username,
                        color=color,
                    )

                else:
                    plot_line_and_circle(
                        fig,
                        x_column_name="dt_first_acceptance_started_date",
                        y_column_name=y_column_name,
                        source=source,
                        legend_label=username,
                        color=color,
                    )

        hover_tool = create_hover_tool(
            [
                "first_acceptance_user_id",
                "first_acceptance_username",
                "first_acceptance_started_date",
                "acceptance_worktime_hour",
                "task_count",
                "input_data_count",
                "annotation_count",
            ]
        )
        for fig in figs:
            fig.add_tools(hover_tool)
            add_legend_to_figure(fig)

        write_bokeh_graph(bokeh.layouts.column(figs), output_file)

    def plot_input_data_metrics(
        self,
        output_file: Path,
        target_user_id_list: Optional[list[str]] = None,
    ):
        """
        教師付者の入力データ単位の生産性情報を折れ線グラフでプロットする。
        """

        if not self._validate_df_for_output(output_file):
            return

        df = self.df.copy()

        if target_user_id_list is not None:
            user_id_list = target_user_id_list
        else:
            user_id_list = (
                df.sort_values(by="first_acceptance_started_date", ascending=False)["first_acceptance_user_id"]
                .dropna()
                .unique()
                .tolist()
            )

        user_id_list = get_plotted_user_id_list(user_id_list)

        fig_info_list = [
            dict(
                title="受入開始日ごとの受入作業時間",
                y_column_name="acceptance_worktime_hour",
                y_axis_label="受入作業時間[hour]",
            ),
            dict(
                title="受入開始日ごとの入力データあたり受入作業時間",
                y_column_name="acceptance_worktime_minute/input_data_count",
                y_axis_label="入力データあたり受入作業時間[min/input_data]",
            ),
            dict(
                title="受入開始日ごとの入力データあたり受入作業時間(1週間移動平均)",
                y_column_name=f"acceptance_worktime_minute/input_data_count{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}",
                y_axis_label="入力データあたり受入作業時間[min/annotation]",
            ),
        ]

        logger.debug(f"{output_file} を出力します。")

        figs: list[bokeh.plotting.Figure] = []
        for fig_info in fig_info_list:
            figs.append(
                figure(
                    plot_width=self.PLOT_WIDTH,
                    plot_height=self.PLOT_HEIGHT,
                    title=fig_info["title"],
                    x_axis_label="受入開始日",
                    x_axis_type="datetime",
                    y_axis_label=fig_info["y_axis_label"],
                )
            )

        for user_index, user_id in enumerate(user_id_list):
            df_subset = df[df["first_acceptance_user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            df_subset = self._get_df_sequential_date(df_subset)
            df_subset["acceptance_worktime_minute/input_data_count"] = (
                df_subset["acceptance_worktime_hour"] * 60 / df_subset["input_data_count"]
            )
            df_subset[f"acceptance_worktime_minute/input_data_count{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = (
                get_weekly_sum(df_subset["acceptance_worktime_hour"])
                * 60
                / get_weekly_sum(df_subset["input_data_count"])
            )

            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["first_acceptance_username"]

            for fig, fig_info in zip(figs, fig_info_list):
                y_column_name = fig_info["y_column_name"]
                if y_column_name.endswith(WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX):
                    plot_moving_average(
                        fig,
                        source=source,
                        x_column_name="dt_first_acceptance_started_date",
                        y_column_name=y_column_name,
                        legend_label=username,
                        color=color,
                    )

                else:
                    plot_line_and_circle(
                        fig,
                        x_column_name="dt_first_acceptance_started_date",
                        y_column_name=y_column_name,
                        source=source,
                        legend_label=username,
                        color=color,
                    )

        hover_tool = create_hover_tool(
            [
                "first_annotation_user_id",
                "first_acceptance_username",
                "first_acceptance_started_date",
                "acceptance_worktime_hour",
                "task_count",
                "input_data_count",
                "annotation_count",
                "inspection_comment_count",
            ]
        )
        for fig in figs:
            fig.add_tools(hover_tool)
            add_legend_to_figure(fig)

        write_bokeh_graph(bokeh.layouts.column(figs), output_file)

    def to_csv(self, output_file: Path) -> None:
        """
        受入作業者の日ごとの生産性が記載されたCSVを出力する。

        """
        if not self._validate_df_for_output(output_file):
            return

        production_columns = [
            "first_acceptance_started_date",
            "first_acceptance_user_id",
            "first_acceptance_username",
            "task_count",
            "input_data_count",
            "annotation_count",
            "acceptance_worktime_hour",
        ]

        velocity_columns = [
            f"acceptance_worktime_hour/{denominator}" for denominator in ["input_data_count", "annotation_count"]
        ]

        columns = production_columns + velocity_columns

        print_csv(self.df[columns], output=str(output_file))
