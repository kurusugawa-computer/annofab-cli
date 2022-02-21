"""
各ユーザの合計の生産性と品質
"""
from __future__ import annotations

import copy
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Collection, Optional

import bokeh
import bokeh.layouts
import bokeh.palettes
import numpy
import pandas
from annofabapi.models import TaskPhase
from bokeh.plotting import ColumnDataSource, figure

from annofabcli.common.utils import print_csv, read_multiheader_csv
from annofabcli.statistics.scatter import (
    create_hover_tool,
    get_color_from_palette,
    plot_bubble,
    plot_scatter,
    write_bokeh_graph,
)

logger = logging.getLogger(__name__)


class WorktimeType(Enum):
    """
    作業時間の種類
    """

    ACTUAL = "actual"
    MONITORED = "monitored"


class UserPerformance:
    """
    各ユーザの合計の生産性と品質

    """

    PLOT_WIDTH = 1200
    PLOT_HEIGHT = 800

    def __init__(self, df: pandas.DataFrame):
        self.df = df
        self.phase_list = self.get_phase_list(df.columns)

    @staticmethod
    def _add_ratio_column_for_productivity_per_user(df: pandas.DataFrame, phase_list: list[str]):
        for phase in phase_list:
            # AnnoFab時間の比率
            df[("monitored_worktime_ratio", phase)] = (
                df[("monitored_worktime_hour", phase)] / df[("monitored_worktime_hour", "sum")]
            )
            # AnnoFab時間の比率から、Annowork時間を予測する
            df[("actual_worktime_hour", phase)] = (
                df[("actual_worktime_hour", "sum")] * df[("monitored_worktime_ratio", phase)]
            )

            # 生産性を算出
            df[("monitored_worktime_hour/input_data_count", phase)] = (
                df[("monitored_worktime_hour", phase)] / df[("input_data_count", phase)]
            )
            df[("actual_worktime_hour/input_data_count", phase)] = (
                df[("actual_worktime_hour", phase)] / df[("input_data_count", phase)]
            )

            df[("monitored_worktime_hour/annotation_count", phase)] = (
                df[("monitored_worktime_hour", phase)] / df[("annotation_count", phase)]
            )
            df[("actual_worktime_hour/annotation_count", phase)] = (
                df[("actual_worktime_hour", phase)] / df[("annotation_count", phase)]
            )

        phase = TaskPhase.ANNOTATION.value
        df[("pointed_out_inspection_comment_count/annotation_count", phase)] = (
            df[("pointed_out_inspection_comment_count", phase)] / df[("annotation_count", phase)]
        )
        df[("pointed_out_inspection_comment_count/input_data_count", phase)] = (
            df[("pointed_out_inspection_comment_count", phase)] / df[("input_data_count", phase)]
        )
        df[("rejected_count/task_count", phase)] = df[("rejected_count", phase)] / df[("task_count", phase)]

    @staticmethod
    def get_phase_list(columns: list[tuple[str, str]]) -> list[str]:
        # multiindexの2段目を取得する
        tmp_set = {c[1] for c in columns}

        phase_list = []

        for phase in TaskPhase:
            if phase.value in tmp_set:
                phase_list.append(phase.value)

        return phase_list

    @classmethod
    def from_csv(cls, csv_file: Path) -> UserPerformance:
        df = read_multiheader_csv(str(csv_file))
        return cls(df)

    def actual_worktime_exists(self) -> bool:
        """実績作業時間が入力されているか否か"""
        return self.df[("actual_worktime_hour", "sum")].sum() > 0

    @classmethod
    def from_df(
        cls,
        df_task_history: pandas.DataFrame,
        df_worktime_ratio: pandas.DataFrame,
        df_labor: Optional[pandas.DataFrame] = None,
    ) -> UserPerformance:
        """
        AnnoWorkの実績時間から、作業者ごとに生産性を算出する。

        Args:
            df_task_history: タスク履歴のDataFrame
            df_worktime_ratio: 作業したタスク数を、作業時間で按分した値が格納されたDataFrame. 以下の列を参照する。
                account_id, phase, worktime_hour
            df_labor: 実績作業時間のDataFrame。以下の列を参照する
                actual_worktime_hour, date, account_id

        Returns:

        """

        def get_phase_list(columns) -> list[str]:
            phase_list = []

            for phase in TaskPhase:
                if phase.value in columns:
                    phase_list.append(phase.value)
            return phase_list

        df_agg_task_history = df_task_history.pivot_table(
            values="worktime_hour", columns="phase", index="account_id", aggfunc=numpy.sum
        ).fillna(0)

        if df_labor is not None and len(df_labor) > 0:
            df_agg_labor = df_labor.pivot_table(values="actual_worktime_hour", index="account_id", aggfunc=numpy.sum)
            df_tmp = df_labor[df_labor["actual_worktime_hour"] > 0].pivot_table(
                values="date", index="account_id", aggfunc=numpy.max
            )
            if len(df_tmp) > 0:
                df_agg_labor["last_working_date"] = df_tmp
            else:
                df_agg_labor["last_working_date"] = numpy.nan
            df = df_agg_task_history.join(df_agg_labor)
        else:
            df = df_agg_task_history
            df["actual_worktime_hour"] = 0
            df["last_working_date"] = None

        phase_list = get_phase_list(list(df.columns))

        df = df[["actual_worktime_hour", "last_working_date"] + phase_list].copy()
        df.columns = pandas.MultiIndex.from_tuples(
            [("actual_worktime_hour", "sum"), ("last_working_date", "")]
            + [("monitored_worktime_hour", phase) for phase in phase_list]
        )

        df[("monitored_worktime_hour", "sum")] = df[[("monitored_worktime_hour", phase) for phase in phase_list]].sum(
            axis=1
        )

        df_agg_production = df_worktime_ratio.pivot_table(
            values=[
                "worktime_ratio_by_task",
                "input_data_count",
                "annotation_count",
                "pointed_out_inspection_comment_count",
                "rejected_count",
            ],
            columns="phase",
            index="account_id",
            aggfunc=numpy.sum,
        ).fillna(0)

        df_agg_production.rename(columns={"worktime_ratio_by_task": "task_count"}, inplace=True)
        df = df.join(df_agg_production)

        # 比例関係の列を計算して追加する
        cls._add_ratio_column_for_productivity_per_user(df, phase_list=phase_list)

        # 不要な列を削除する
        tmp_phase_list = copy.deepcopy(phase_list)
        tmp_phase_list.remove(TaskPhase.ANNOTATION.value)

        dropped_column = [("pointed_out_inspection_comment_count", phase) for phase in tmp_phase_list] + [
            ("rejected_count", phase) for phase in tmp_phase_list
        ]
        df = df.drop(dropped_column, axis=1)

        # ユーザ情報を取得
        df_user = df_task_history.groupby("account_id").first()[["user_id", "username", "biography"]]
        df_user.columns = pandas.MultiIndex.from_tuples([("user_id", ""), ("username", ""), ("biography", "")])
        df = df.join(df_user)
        return cls(df)

    @classmethod
    def merge(cls, obj1: UserPerformance, obj2: UserPerformance) -> UserPerformance:
        def max_last_working_date(date1, date2):
            if not isinstance(date1, str) and numpy.isnan(date1):
                date1 = ""
            if not isinstance(date2, str) and numpy.isnan(date2):
                date2 = ""
            max_date = max(date1, date2)
            if max_date == "":
                return numpy.nan
            else:
                return max_date

        def merge_row(row1: pandas.Series, row2: pandas.Series) -> pandas.Series:
            string_column_list = ["username", "biography", "last_working_date"]
            sum_row = row1.drop(labels=string_column_list, level=0).fillna(0) + row2.drop(
                labels=string_column_list, level=0
            ).fillna(0)
            sum_row.loc["username", ""] = row1.loc["username", ""]
            sum_row.loc["biography", ""] = row1.loc["biography", ""]
            sum_row.loc["last_working_date", ""] = max_last_working_date(
                row1.loc["last_working_date", ""], row2.loc["last_working_date", ""]
            )
            return sum_row

        df1 = obj1.df
        df2 = obj2.df
        user_id_set = set(df1["user_id"]) | set(df2["user_id"])
        sum_df = df1.set_index("user_id").copy()
        added_df = df2.set_index("user_id")

        for user_id in user_id_set:
            if user_id not in added_df.index:
                continue
            if user_id in sum_df.index:
                sum_df.loc[user_id] = merge_row(sum_df.loc[user_id], added_df.loc[user_id])
            else:
                sum_df.loc[user_id] = added_df.loc[user_id]

        phase_list = cls.get_phase_list(list(sum_df["monitored_worktime_hour"].columns))
        cls._add_ratio_column_for_productivity_per_user(sum_df, phase_list=phase_list)
        sum_df.reset_index(inplace=True)
        sum_df.sort_values(["user_id"], inplace=True)
        return cls(sum_df)

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    @staticmethod
    def get_productivity_columns(phase_list: list[str]) -> list[tuple[str, str]]:
        monitored_worktime_columns = (
            [("monitored_worktime_hour", phase) for phase in phase_list]
            + [("monitored_worktime_hour", "sum")]
            + [("monitored_worktime_ratio", phase) for phase in phase_list]
        )
        production_columns = (
            [("task_count", phase) for phase in phase_list]
            + [("input_data_count", phase) for phase in phase_list]
            + [("annotation_count", phase) for phase in phase_list]
        )

        actual_worktime_columns = [("actual_worktime_hour", "sum")] + [
            ("actual_worktime_hour", phase) for phase in phase_list
        ]

        productivity_columns = (
            [("monitored_worktime_hour/input_data_count", phase) for phase in phase_list]
            + [("actual_worktime_hour/input_data_count", phase) for phase in phase_list]
            + [("monitored_worktime_hour/annotation_count", phase) for phase in phase_list]
            + [("actual_worktime_hour/annotation_count", phase) for phase in phase_list]
        )

        inspection_comment_columns = [
            ("pointed_out_inspection_comment_count", TaskPhase.ANNOTATION.value),
            ("pointed_out_inspection_comment_count/input_data_count", TaskPhase.ANNOTATION.value),
            ("pointed_out_inspection_comment_count/annotation_count", TaskPhase.ANNOTATION.value),
        ]

        rejected_count_columns = [
            ("rejected_count", TaskPhase.ANNOTATION.value),
            ("rejected_count/task_count", TaskPhase.ANNOTATION.value),
        ]

        prior_columns = (
            monitored_worktime_columns
            + production_columns
            + actual_worktime_columns
            + productivity_columns
            + inspection_comment_columns
            + rejected_count_columns
        )

        return prior_columns

    def to_csv(self, output_file: Path) -> None:

        if not self._validate_df_for_output(output_file):
            return

        value_columns = self.get_productivity_columns(self.phase_list)

        user_columns = [("user_id", ""), ("username", ""), ("biography", ""), ("last_working_date", "")]
        columns = user_columns + value_columns

        print_csv(self.df[columns], str(output_file))

    @staticmethod
    def _plot_average_line(fig: bokeh.plotting.Figure, value: float, dimension: str):
        span_average_line = bokeh.models.Span(
            location=value,
            dimension=dimension,
            line_color="red",
            line_width=0.5,
        )
        fig.add_layout(span_average_line)

    @staticmethod
    def _plot_quartile_line(fig: bokeh.plotting.Figure, quartile: tuple[float, float, float], dimension: str):
        """

        Args:
            fig (bokeh.plotting.Figure):
            quartile (tuple[float, float, float]): 四分位数。tuple[25%値, 50%値, 75%値]
            dimension (str): [description]: width or height
        """

        for value in quartile:
            span_average_line = bokeh.models.Span(
                location=value,
                dimension=dimension,
                line_color="blue",
                line_width=0.5,
            )
            fig.add_layout(span_average_line)

    @staticmethod
    def _get_average_value(df: pandas.DataFrame, numerator_column: Any, denominator_column: Any) -> Optional[float]:
        numerator = df[numerator_column].sum()
        denominator = df[denominator_column].sum()
        if denominator > 0:
            return numerator / denominator
        else:
            return None

    @staticmethod
    def _get_quartile_value(df: pandas.DataFrame, column: Any) -> Optional[tuple[float, float, float]]:
        tmp = df[column].describe()
        if tmp["count"] > 3:
            return (tmp["25%"], tmp["50%"], tmp["75%"])
        else:
            return None

    @staticmethod
    def _create_div_element() -> bokeh.models.Div:
        """
        HTMLページの先頭に付与するdiv要素を生成する。
        """
        return bokeh.models.Div(
            text="""<h4>グラフの見方</h4>
            <span style="color:red;">赤線</span>：平均値<br>
            <span style="color:blue;">青線</span>：四分位数<br>
            """
        )

    @staticmethod
    def _set_legend(fig: bokeh.plotting.Figure) -> None:
        """
        凡例の設定。
        """
        fig.legend.location = "top_left"
        fig.legend.click_policy = "mute"
        fig.legend.title = "biography"
        if len(fig.legend) > 0:
            legend = fig.legend[0]
            fig.add_layout(legend, "left")

    def get_summary(self) -> pandas.Series:
        """
        全体の生産性と品質が格納された pandas.Series を取得する。

        """
        columns_for_sum = [
            "monitored_worktime_hour",
            "task_count",
            "input_data_count",
            "annotation_count",
            "actual_worktime_hour",
            "pointed_out_inspection_comment_count",
            "rejected_count",
        ]
        sum_series = self.df[columns_for_sum].sum()

        self._add_ratio_column_for_productivity_per_user(sum_series, phase_list=self.phase_list)

        # 作業している人数をカウントする
        for phase in self.phase_list:
            sum_series[("working_user_count", phase)] = (self.df[("task_count", phase)] > 0).sum()

        return sum_series

    def _plot_productivity(self, output_file: Path, worktime_type: WorktimeType):
        """作業時間と生産性の関係をメンバごとにプロットする。"""

        if not self._validate_df_for_output(output_file):
            return

        # numpy.inf が含まれていると散布図を出力できないので置換する
        df = self.df.replace(numpy.inf, numpy.nan)

        def create_figure(title: str) -> bokeh.plotting.Figure:
            return figure(
                plot_width=self.PLOT_WIDTH,
                plot_height=self.PLOT_HEIGHT,
                title=title,
                x_axis_label="累計作業時間[hour]",
                y_axis_label="アノテーションあたり作業時間[minute/annotation]",
            )

        if worktime_type == WorktimeType.ACTUAL:
            worktime_name = "実績時間"
        elif worktime_type == WorktimeType.MONITORED:
            worktime_name = "計測時間"

        logger.debug(f"{output_file} を出力します。")

        DICT_PHASE_NAME = {
            TaskPhase.ANNOTATION.value: "教師付",
            TaskPhase.INSPECTION.value: "検査",
            TaskPhase.ACCEPTANCE.value: "受入",
        }
        figure_list = [
            create_figure(f"{DICT_PHASE_NAME[phase]}のアノテーションあたり作業時間と累計作業時間の関係({worktime_name})")
            for phase in self.phase_list
        ]

        df["biography"] = df["biography"].fillna("")

        x_column = f"{worktime_type.value}_worktime_hour"
        y_column = f"{worktime_type.value}_worktime_minute/annotation_count"
        # 分単位の生産性を算出する
        for phase in self.phase_list:
            df[(f"{worktime_type.value}_worktime_minute/annotation_count", phase)] = (
                df[(f"{worktime_type.value}_worktime_hour/annotation_count", phase)] * 60
            )

        for biography_index, biography in enumerate(sorted(set(df["biography"]))):
            for fig, phase in zip(figure_list, self.phase_list):
                filtered_df = df[
                    (df["biography"] == biography) & df[(x_column, phase)].notna() & df[(y_column, phase)].notna()
                ]
                if len(filtered_df) == 0:
                    continue
                source = ColumnDataSource(data=filtered_df)
                plot_scatter(
                    fig=fig,
                    source=source,
                    x_column_name=f"{x_column}_{phase}",
                    y_column_name=f"{y_column}_{phase}",
                    text_column_name="username_",
                    legend_label=biography,
                    color=get_color_from_palette(biography_index),
                )

        for fig, phase in zip(figure_list, self.phase_list):
            average_hour = self._get_average_value(
                df,
                numerator_column=(f"{worktime_type.value}_worktime_hour", phase),
                denominator_column=("annotation_count", phase),
            )
            if average_hour is not None:
                average_minute = average_hour * 60
                self._plot_average_line(fig, average_minute, dimension="width")

            quartile = self._get_quartile_value(df, (f"{worktime_type.value}_worktime_minute/annotation_count", phase))
            if quartile is not None:
                self._plot_quartile_line(fig, quartile, dimension="width")

        for fig, phase in zip(figure_list, self.phase_list):
            tooltip_item = [
                "user_id_",
                "username_",
                "biography_",
                f"{worktime_type.value}_worktime_hour_{phase}",
                f"task_count_{phase}",
                f"input_data_count_{phase}",
                f"annotation_count_{phase}",
                f"{worktime_type.value}_worktime_hour/input_data_count_{phase}",
                f"{worktime_type.value}_worktime_hour/annotation_count_{phase}",
            ]
            if worktime_type == WorktimeType.ACTUAL:
                tooltip_item.append("last_working_date_")

            hover_tool = create_hover_tool(tooltip_item)
            fig.add_tools(hover_tool)
            self._set_legend(fig)

        div_element = self._create_div_element()
        write_bokeh_graph(bokeh.layouts.column([div_element] + figure_list), output_file)

    def plot_productivity_from_monitored_worktime(self, output_file: Path):
        """
        AnnoFab計測時間とAnnoFab計測時間を元に算出した生産性を、メンバごとにプロットする
        """
        self._plot_productivity(output_file, worktime_type=WorktimeType.MONITORED)

    def plot_productivity_from_actual_worktime(self, output_file: Path):
        """
        実績作業時間と実績作業時間を元に算出した生産性を、メンバごとにプロットする
        """
        self._plot_productivity(output_file, worktime_type=WorktimeType.ACTUAL)

    def plot_quality(self, output_file: Path):
        """
        メンバごとに品質を散布図でプロットする

        Args:
            df:
        Returns:

        """
        if not self._validate_df_for_output(output_file):
            return

        # numpy.inf が含まれていると散布図を出力できないので置換する
        df = self.df.replace(numpy.inf, numpy.nan)

        def create_figure(title: str, x_axis_label: str, y_axis_label: str) -> bokeh.plotting.Figure:
            return figure(
                plot_width=self.PLOT_WIDTH,
                plot_height=self.PLOT_HEIGHT,
                title=title,
                x_axis_label=x_axis_label,
                y_axis_label=y_axis_label,
            )

        logger.debug(f"{output_file} を出力します。")

        figure_list = [
            create_figure(title=f"タスクあたり差し戻し回数とタスク数の関係", x_axis_label="タスク数", y_axis_label="タスクあたり差し戻し回数"),
            create_figure(
                title=f"アノテーションあたり検査コメント数とアノテーション数の関係", x_axis_label="アノテーション数", y_axis_label="アノテーションあたり検査コメント数"
            ),
        ]
        column_pair_list = [
            ("task_count", "rejected_count/task_count"),
            ("annotation_count", "pointed_out_inspection_comment_count/annotation_count"),
        ]

        phase = "annotation"

        df["biography"] = df["biography"].fillna("")
        for biography_index, biography in enumerate(sorted(set(df["biography"]))):
            for column_pair, fig in zip(column_pair_list, figure_list):
                x_column = column_pair[0]
                y_column = column_pair[1]
                filtered_df = df[
                    (df["biography"] == biography) & df[(x_column, phase)].notna() & df[(y_column, phase)].notna()
                ]
                if len(filtered_df) == 0:
                    continue

                source = ColumnDataSource(data=filtered_df)
                plot_scatter(
                    fig=fig,
                    source=source,
                    x_column_name=f"{x_column}_{phase}",
                    y_column_name=f"{y_column}_{phase}",
                    text_column_name="username_",
                    legend_label=biography,
                    color=get_color_from_palette(biography_index),
                )

        for column_pair, fig in zip(
            [("rejected_count", "task_count"), ("pointed_out_inspection_comment_count", "annotation_count")],
            figure_list,
        ):
            average_value = self._get_average_value(
                df, numerator_column=(column_pair[0], phase), denominator_column=(column_pair[1], phase)
            )
            if average_value is not None:
                self._plot_average_line(fig, average_value, dimension="width")

        for column, fig in zip(
            ["rejected_count/task_count", "pointed_out_inspection_comment_count/annotation_count"],
            figure_list,
        ):
            quartile = self._get_quartile_value(df, (column, phase))
            if quartile is not None:
                self._plot_quartile_line(fig, quartile, dimension="width")

        for fig in figure_list:
            tooltip_item = [
                "user_id_",
                "username_",
                "biography_",
                "last_working_date_",
                f"monitored_worktime_hour_{phase}",
                f"task_count_{phase}",
                f"input_data_count_{phase}",
                f"annotation_count_{phase}",
                f"rejected_count_{phase}",
                f"pointed_out_inspection_comment_count_{phase}",
                f"rejected_count/task_count_{phase}",
                f"pointed_out_inspection_comment_count/annotation_count_{phase}",
            ]

            hover_tool = create_hover_tool(tooltip_item)
            fig.add_tools(hover_tool)
            self._set_legend(fig)

        div_element = self._create_div_element()
        write_bokeh_graph(bokeh.layouts.column([div_element] + figure_list), output_file)

    def plot_quality_and_productivity_from_actual_worktime(
        self,
        output_file: Path,
    ):
        """
        実績作業時間を元に算出した生産性と品質の関係を、メンバごとにプロットする
        """
        self._plot_quality_and_productivity(output_file, worktime_type=WorktimeType.ACTUAL)

    def plot_quality_and_productivity_from_monitored_worktime(
        self,
        output_file: Path,
    ):
        """
        計測作業時間を元に算出した生産性と品質の関係を、メンバごとにプロットする
        """
        self._plot_quality_and_productivity(output_file, worktime_type=WorktimeType.MONITORED)

    def _plot_quality_and_productivity(self, output_file: Path, worktime_type: WorktimeType):
        """
        作業時間を元に算出した生産性と品質の関係を、メンバごとにプロットする
        """

        def create_figure(title: str, x_axis_label: str, y_axis_label: str) -> bokeh.plotting.Figure:
            return figure(
                plot_width=self.PLOT_WIDTH,
                plot_height=self.PLOT_HEIGHT,
                title=title,
                x_axis_label=x_axis_label,
                y_axis_label=y_axis_label,
            )

        def plot_average_and_quartile_line():
            x_average_hour = self._get_average_value(
                df,
                numerator_column=(f"{worktime_type.value}_worktime_hour", phase),
                denominator_column=("annotation_count", phase),
            )
            x_average_minute = x_average_hour * 60 if x_average_hour is not None else None

            for column_pair, fig in zip(
                [("rejected_count", "task_count"), ("pointed_out_inspection_comment_count", "annotation_count")],
                figure_list,
            ):
                if x_average_minute is not None:
                    self._plot_average_line(fig, x_average_minute, dimension="height")

                y_average = self._get_average_value(
                    df,
                    numerator_column=(column_pair[0], phase),
                    denominator_column=(column_pair[1], phase),
                )
                if y_average is not None:
                    self._plot_average_line(fig, y_average, dimension="width")

            x_quartile = self._get_quartile_value(
                df, (f"{worktime_type.value}_worktime_minute/annotation_count", phase)
            )
            for column, fig in zip(
                ["rejected_count/task_count", "pointed_out_inspection_comment_count/annotation_count"],
                figure_list,
            ):
                if x_quartile is not None:
                    self._plot_quartile_line(fig, x_quartile, dimension="height")
                y_quartile = self._get_quartile_value(df, (column, phase))
                if y_quartile is not None:
                    self._plot_quartile_line(fig, y_quartile, dimension="width")

        def set_tooltip():
            for fig in figure_list:
                tooltip_item = [
                    "user_id_",
                    "username_",
                    "biography_",
                    f"{worktime_type.value}_worktime_hour_{phase}",
                    f"task_count_{phase}",
                    f"input_data_count_{phase}",
                    f"annotation_count_{phase}",
                    f"{worktime_type.value}_worktime_hour/input_data_count_{phase}",
                    f"{worktime_type.value}_worktime_hour/annotation_count_{phase}",
                    f"rejected_count_{phase}",
                    f"pointed_out_inspection_comment_count_{phase}",
                    f"rejected_count/task_count_{phase}",
                    f"pointed_out_inspection_comment_count/annotation_count_{phase}",
                ]
                if worktime_type == WorktimeType.ACTUAL:
                    tooltip_item.append("last_working_date_")

                hover_tool = create_hover_tool(tooltip_item)
                fig.add_tools(hover_tool)
                self._set_legend(fig)

        if not self._validate_df_for_output(output_file):
            return

        # numpy.inf が含まれていると散布図を出力できないので置換する
        df = self.df.replace(numpy.inf, numpy.nan)
        for phase in self.phase_list:
            df[(f"{worktime_type.value}_worktime_minute/annotation_count", phase)] = (
                df[(f"{worktime_type.value}_worktime_hour/annotation_count", phase)] * 60
            )

        logger.debug(f"{output_file} を出力します。")

        figure_list = [
            create_figure(
                title=f"アノテーションあたり作業時間とタスクあたり差し戻し回数の関係",
                x_axis_label="アノテーションあたり作業時間[minute/annotation]",
                y_axis_label="タスクあたり差し戻し回数",
            ),
            create_figure(
                title=f"アノテーションあたり作業時間とアノテーションあたり検査コメント数の関係",
                x_axis_label="アノテーションあたり作業時間[minute/annotation]",
                y_axis_label="アノテーションあたり検査コメント数",
            ),
        ]
        column_pair_list = [
            (f"{worktime_type.value}_worktime_minute/annotation_count", "rejected_count/task_count"),
            (
                f"{worktime_type.value}_worktime_minute/annotation_count",
                "pointed_out_inspection_comment_count/annotation_count",
            ),
        ]
        phase = TaskPhase.ANNOTATION.value
        df["biography"] = df["biography"].fillna("")
        for biography_index, biography in enumerate(sorted(set(df["biography"]))):
            for fig, column_pair in zip(figure_list, column_pair_list):
                x_column, y_column = column_pair
                filtered_df = df[
                    (df["biography"] == biography) & df[(x_column, phase)].notna() & df[(y_column, phase)].notna()
                ]
                if len(filtered_df) == 0:
                    continue
                source = ColumnDataSource(data=filtered_df)
                plot_bubble(
                    fig=fig,
                    source=source,
                    x_column_name=f"{x_column}_{phase}",
                    y_column_name=f"{y_column}_{phase}",
                    text_column_name="username_",
                    size_column_name=f"{worktime_type.value}_worktime_hour_{phase}",
                    legend_label=biography,
                    color=get_color_from_palette(biography_index),
                )

        plot_average_and_quartile_line()
        set_tooltip()

        div_element = self._create_div_element()
        div_element.text += """円の大きさ：作業時間<br>"""
        write_bokeh_graph(bokeh.layouts.column([div_element] + figure_list), output_file)


class WholePerformance:
    """
    全体の生産性と品質の情報
    """

    def __init__(self, series: pandas.Series):
        self.series = series

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.series) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    @classmethod
    def from_csv(cls, csv_file: Path) -> WholePerformance:
        df = pandas.read_csv(str(csv_file), header=None, index_col=[0, 1])
        # 3列目を値としたpandas.Series を取得する。
        series = df[2]
        return cls(series)

    def to_csv(self, output_file: Path) -> None:
        """
        全体の生産性と品質が格納されたCSVを出力します。

        """
        if not self._validate_df_for_output(output_file):
            return

        # 列の順番を整える
        phase_list = UserPerformance.get_phase_list(self.series.index)
        indexes = UserPerformance.get_productivity_columns(phase_list) + [
            ("working_user_count", phase) for phase in phase_list
        ]
        series = self.series[indexes]

        output_file.parent.mkdir(exist_ok=True, parents=True)
        logger.debug(f"{str(output_file)} を出力します。")
        series.to_csv(str(output_file), sep=",", encoding="utf_8_sig", header=False)


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
    def from_whole_performance_objs(
        cls, objs: Collection[WholePerformance], project_titles: Collection[str]
    ) -> ProjectPerformance:

        series_list = []
        for whole_performance_obj, project_title in zip(objs, project_titles):
            series = whole_performance_obj.series
            series[("project_title", "")] = project_title
            series_list.append(series)

        df = pandas.DataFrame(series_list)
        return cls(df)

    def to_csv(self, output_file: Path) -> None:
        """
        全体の生産性と品質が格納されたCSVを出力します。

        """
        if not self._validate_df_for_output(output_file):
            return

        phase_list = UserPerformance.get_phase_list(self.df.columns)

        first_columns = [("project_title", "")]
        value_columns = UserPerformance.get_productivity_columns(phase_list)

        columns = first_columns + value_columns + [("working_user_count", phase) for phase in phase_list]
        print_csv(self.df[columns], output=str(output_file))
