# pylint: disable=too-many-lines
"""
累積の生産性に関する内容
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

from annofabcli.statistics.linegraph import (
    add_legend_to_figure,
    create_hover_tool,
    get_color_from_palette,
    get_plotted_user_id_list,
    plot_line_and_circle,
    write_bokeh_graph,
)

logger = logging.getLogger(__name__)


class AbstractRoleCumulativeProductivity(abc.ABC):
    """ロールごとの累積の生産性をプロットするための抽象クラス"""

    PLOT_WIDTH = 1200
    PLOT_HEIGHT = 600

    def __init__(self, df: pandas.DataFrame, phase: str) -> None:
        self.df = df
        self.phase = phase
        self.phase_name = self._get_phase_name(phase)
        self.df_cumulative = self._get_cumulative_dataframe()
        self.default_user_id_list = self._get_default_user_id_list()

    @staticmethod
    def _get_phase_name(phase: str) -> str:
        if phase == "annotation":
            return "教師付"
        elif phase == "inspection":
            return "検査"
        elif phase == "acceptance":
            return "受入"
        raise RuntimeError(f"phase='{phase}'が対象外です。")

    def _get_default_user_id_list(self) -> list[str]:
        return (
            self.df.sort_values(by=f"first_{self.phase}_started_datetime", ascending=False)[
                f"first_{self.phase}_user_id"
            ]
            .dropna()
            .unique()
            .tolist()
        )

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False

        if len(self.default_user_id_list) == 0:
            logger.warning(
                f"{self.phase_name} 作業したタスクが0件なので（'first_{self.phase}_user_id'がすべて空欄）、{output_file} を出力しません。"
            )
            return False

        return True

    @abc.abstractmethod
    def _get_cumulative_dataframe(self) -> pandas.DataFrame:
        pass

    @abc.abstractmethod
    def plot_annotation_metrics(self, output_file: Path, target_user_id_list: Optional[list[str]] = None):
        pass

    @abc.abstractmethod
    def plot_input_data_metrics(self, output_file: Path, target_user_id_list: Optional[list[str]] = None):
        pass


class AnnotatorCumulativeProductivity(AbstractRoleCumulativeProductivity):
    def __init__(self, df: pandas.DataFrame):
        super().__init__(df, phase="annotation")

    def _get_cumulative_dataframe(self) -> pandas.DataFrame:
        """
        累積情報が格納されたDataFrameを生成する。
        """
        # 教師付の開始時刻でソートして、indexを更新する
        df = self.df.sort_values(["first_annotation_user_id", "first_annotation_started_datetime"]).reset_index(
            drop=True
        )
        # タスクの累計数を取得するために設定する
        df["task_count"] = 1
        # 教師付の作業者でgroupby
        groupby_obj = df.groupby("first_annotation_user_id")

        # 作業時間の累積値
        df["cumulative_annotation_worktime_hour"] = groupby_obj["annotation_worktime_hour"].cumsum()
        df["cumulative_acceptance_worktime_hour"] = groupby_obj["acceptance_worktime_hour"].cumsum()
        df["cumulative_inspection_worktime_hour"] = groupby_obj["inspection_worktime_hour"].cumsum()

        # タスク完了数、差し戻し数など
        df["cumulative_inspection_comment_count"] = groupby_obj["inspection_comment_count"].cumsum()
        df["cumulative_annotation_count"] = groupby_obj["annotation_count"].cumsum()
        df["cumulative_input_data_count"] = groupby_obj["input_data_count"].cumsum()
        df["cumulative_task_count"] = groupby_obj["task_count"].cumsum()
        df["cumulative_number_of_rejections"] = groupby_obj["number_of_rejections"].cumsum()
        df["cumulative_number_of_rejections_by_inspection"] = groupby_obj["number_of_rejections_by_inspection"].cumsum()
        df["cumulative_number_of_rejections_by_acceptance"] = groupby_obj["number_of_rejections_by_acceptance"].cumsum()

        # 元に戻す
        df = df.drop(["task_count"], axis=1)
        return df

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

        logger.debug(f"{output_file} を出力します。")

        if target_user_id_list is not None:
            user_id_list = target_user_id_list
        else:
            user_id_list = self.default_user_id_list

        user_id_list = get_plotted_user_id_list(user_id_list)

        fig_info_list = [
            dict(
                title="累積のアノテーション数と教師付作業時間",
                y_column_name="cumulative_annotation_worktime_hour",
                y_axis_label="教師付作業時間[hour]",
            ),
            dict(
                title="累積のアノテーション数と検査作業時間",
                y_column_name="cumulative_inspection_worktime_hour",
                y_axis_label="検査作業時間[hour]",
            ),
            dict(
                title="累積のアノテーション数と受入作業時間",
                y_column_name="cumulative_acceptance_worktime_hour",
                y_axis_label="受入作業時間[hour]",
            ),
            dict(
                title="累積のアノテーション数と検査コメント数",
                y_column_name="cumulative_inspection_comment_count",
                y_axis_label="検査コメント数",
            ),
        ]

        figs: list[bokeh.plotting.Figure] = []
        for fig_info in fig_info_list:
            figs.append(
                figure(
                    plot_width=self.PLOT_WIDTH,
                    plot_height=self.PLOT_HEIGHT,
                    title=fig_info["title"],
                    x_axis_label="アノテーション数",
                    y_axis_label=fig_info["y_axis_label"],
                )
            )

        for user_index, user_id in enumerate(user_id_list):
            df_subset = self.df_cumulative[self.df_cumulative["first_annotation_user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["first_annotation_username"]

            for fig, fig_info in zip(figs, fig_info_list):
                plot_line_and_circle(
                    fig,
                    x_column_name="cumulative_annotation_count",
                    y_column_name=fig_info["y_column_name"],
                    source=source,
                    legend_label=username,
                    color=color,
                )

        hover_tool = create_hover_tool(
            [
                "task_id",
                "phase",
                "status",
                "first_annotation_user_id",
                "first_annotation_username",
                "first_annotation_started_datetime",
                "annotation_worktime_hour",
                "inspection_worktime_hour",
                "acceptance_worktime_hour",
                "annotation_count",
                "input_data_count",
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
        教師付者の累積値を入力データ単位でプロットする。

        """

        if not self._validate_df_for_output(output_file):
            return

        logger.debug(f"{output_file} を出力します。")

        if target_user_id_list is not None:
            user_id_list = target_user_id_list
        else:
            user_id_list = self.default_user_id_list

        user_id_list = get_plotted_user_id_list(user_id_list)

        fig_info_list = [
            dict(
                title="累積の入力データ数と教師付作業時間",
                y_column_name="cumulative_annotation_worktime_hour",
                y_axis_label="教師付作業時間[hour]",
            ),
            dict(
                title="累積の入力データ数と検査作業時間",
                y_column_name="cumulative_inspection_worktime_hour",
                y_axis_label="検査作業時間[hour]",
            ),
            dict(
                title="累積の入力データ数と受入作業時間",
                y_column_name="cumulative_acceptance_worktime_hour",
                y_axis_label="受入作業時間[hour]",
            ),
            dict(
                title="累積の入力データ数と検査コメント数",
                y_column_name="cumulative_inspection_comment_count",
                y_axis_label="検査コメント数",
            ),
        ]

        figs: list[bokeh.plotting.Figure] = []
        for fig_info in fig_info_list:
            figs.append(
                figure(
                    plot_width=self.PLOT_WIDTH,
                    plot_height=self.PLOT_HEIGHT,
                    title=fig_info["title"],
                    x_axis_label="入力データ数",
                    y_axis_label=fig_info["y_axis_label"],
                )
            )

        for user_index, user_id in enumerate(user_id_list):
            df_subset = self.df_cumulative[self.df_cumulative["first_annotation_user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["first_annotation_username"]

            for fig, fig_info in zip(figs, fig_info_list):
                plot_line_and_circle(
                    fig,
                    x_column_name="cumulative_input_data_count",
                    y_column_name=fig_info["y_column_name"],
                    source=source,
                    legend_label=username,
                    color=color,
                )

        hover_tool = create_hover_tool(
            [
                "task_id",
                "phase",
                "status",
                "first_annotation_user_id",
                "first_annotation_username",
                "first_annotation_started_datetime",
                "annotation_worktime_hour",
                "inspection_worktime_hour",
                "acceptance_worktime_hour",
                "annotation_count",
                "input_data_count",
                "inspection_comment_count",
            ]
        )
        for fig in figs:
            fig.add_tools(hover_tool)
            add_legend_to_figure(fig)

        write_bokeh_graph(bokeh.layouts.column(figs), output_file)

    def plot_task_metrics(
        self,
        output_file: Path,
        target_user_id_list: Optional[list[str]] = None,
    ):
        """
        教師付者の累積値を入力データ単位でプロットする。

        """

        if not self._validate_df_for_output(output_file):
            return

        logger.debug(f"{output_file} を出力します。")

        if target_user_id_list is not None:
            user_id_list = target_user_id_list
        else:
            user_id_list = self.default_user_id_list

        user_id_list = get_plotted_user_id_list(user_id_list)

        fig_info_list = [
            dict(
                title="累積のタスク数と教師付作業時間",
                y_column_name="cumulative_annotation_worktime_hour",
                y_axis_label="教師付作業時間[hour]",
            ),
            dict(
                title="累積のタスク数と差し戻し回数(検査フェーズ)",
                y_column_name="cumulative_number_of_rejections_by_inspection",
                y_axis_label="差し戻し回数(検査フェーズ)",
            ),
            dict(
                title="累積のタスク数と差し戻し回数(受入フェーズ)",
                y_column_name="cumulative_number_of_rejections_by_acceptance",
                y_axis_label="差し戻し回数(受入フェーズ)",
            ),
        ]

        figs: list[bokeh.plotting.Figure] = []
        for fig_info in fig_info_list:
            figs.append(
                figure(
                    plot_width=self.PLOT_WIDTH,
                    plot_height=self.PLOT_HEIGHT,
                    title=fig_info["title"],
                    x_axis_label="タスク数",
                    y_axis_label=fig_info["y_axis_label"],
                )
            )

        for user_index, user_id in enumerate(user_id_list):
            df_subset = self.df_cumulative[self.df_cumulative["first_annotation_user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["first_annotation_username"]

            for fig, fig_info in zip(figs, fig_info_list):
                plot_line_and_circle(
                    fig,
                    x_column_name="cumulative_task_count",
                    y_column_name=fig_info["y_column_name"],
                    source=source,
                    legend_label=username,
                    color=color,
                )

        hover_tool = create_hover_tool(
            [
                "task_id",
                "phase",
                "status",
                "first_annotation_user_id",
                "first_annotation_username",
                "first_annotation_started_datetime",
                "annotation_worktime_hour",
                "annotation_count",
                "input_data_count",
                "number_of_rejections_by_inspection",
                "number_of_rejections_by_acceptance",
            ]
        )
        for fig in figs:
            fig.add_tools(hover_tool)
            add_legend_to_figure(fig)

        write_bokeh_graph(bokeh.layouts.column(figs), output_file)


class InspectorCumulativeProductivity(AbstractRoleCumulativeProductivity):
    def __init__(self, df: pandas.DataFrame):
        super().__init__(df, phase="inspection")

    def _get_cumulative_dataframe(self) -> pandas.DataFrame:
        """
        最初のアノテーション作業の開始時刻の順にソートして、検査者に関する累計値を算出する
        Args:
            task_df: タスク一覧のDataFrame. 列が追加される
        """
        df = self.df.sort_values(["first_inspection_user_id", "first_inspection_started_datetime"]).reset_index(
            drop=True
        )
        groupby_obj = df.groupby("first_inspection_user_id")

        # 作業時間の累積値
        df["cumulative_inspection_worktime_hour"] = groupby_obj["inspection_worktime_hour"].cumsum()

        df["cumulative_inspection_comment_count"] = groupby_obj["inspection_comment_count"].cumsum()
        df["cumulative_annotation_count"] = groupby_obj["annotation_count"].cumsum()
        df["cumulative_input_data_count"] = groupby_obj["input_data_count"].cumsum()

        return df

    def plot_annotation_metrics(
        self,
        output_file: Path,
        target_user_id_list: Optional[list[str]] = None,
    ):
        """
        生産性を検査作業者ごとにプロットする。

        Args:
            df:
            first_inspection_user_id_list:

        Returns:

        """

        if not self._validate_df_for_output(output_file):
            return

        logger.debug(f"{output_file} を出力します。")

        if target_user_id_list is not None:
            user_id_list = target_user_id_list
        else:
            user_id_list = self.default_user_id_list

        user_id_list = get_plotted_user_id_list(user_id_list)

        fig_info_list = [
            dict(
                title="累積のアノテーション数と検査作業時間",
                y_column_name="cumulative_inspection_worktime_hour",
                y_axis_label="検査作業時間[hour]",
            ),
        ]

        figs: list[bokeh.plotting.Figure] = []
        for fig_info in fig_info_list:
            figs.append(
                figure(
                    plot_width=self.PLOT_WIDTH,
                    plot_height=self.PLOT_HEIGHT,
                    title=fig_info["title"],
                    x_axis_label="アノテーション数",
                    y_axis_label=fig_info["y_axis_label"],
                )
            )

        for user_index, user_id in enumerate(user_id_list):
            df_subset = self.df_cumulative[self.df_cumulative["first_inspection_user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["first_inspection_username"]

            for fig, fig_info in zip(figs, fig_info_list):
                plot_line_and_circle(
                    fig,
                    x_column_name="cumulative_annotation_count",
                    y_column_name=fig_info["y_column_name"],
                    source=source,
                    legend_label=username,
                    color=color,
                )

        hover_tool = create_hover_tool(
            [
                "task_id",
                "phase",
                "status",
                "first_inspection_user_id",
                "first_inspection_username",
                "first_inspection_started_datetime",
                "inspection_worktime_hour",
                "annotation_count",
                "input_data_count",
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
        検査者の累積値を入力データ単位でプロットする。

        """

        if not self._validate_df_for_output(output_file):
            return

        logger.debug(f"{output_file} を出力します。")

        if target_user_id_list is not None:
            user_id_list = target_user_id_list
        else:
            user_id_list = self.default_user_id_list

        user_id_list = get_plotted_user_id_list(user_id_list)

        fig_info_list = [
            dict(
                title="累積の入力データ数と検査作業時間",
                y_column_name="cumulative_inspection_worktime_hour",
                y_axis_label="検査作業時間[hour]",
            ),
        ]

        figs: list[bokeh.plotting.Figure] = []
        for fig_info in fig_info_list:
            figs.append(
                figure(
                    plot_width=self.PLOT_WIDTH,
                    plot_height=self.PLOT_HEIGHT,
                    title=fig_info["title"],
                    x_axis_label="入力データ数",
                    y_axis_label=fig_info["y_axis_label"],
                )
            )

        for user_index, user_id in enumerate(user_id_list):
            df_subset = self.df_cumulative[self.df_cumulative["first_inspection_user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["first_inspection_username"]

            for fig, fig_info in zip(figs, fig_info_list):
                plot_line_and_circle(
                    fig,
                    x_column_name="cumulative_input_data_count",
                    y_column_name=fig_info["y_column_name"],
                    source=source,
                    legend_label=username,
                    color=color,
                )

        hover_tool = create_hover_tool(
            [
                "task_id",
                "phase",
                "status",
                "first_inspection_user_id",
                "first_inspection_username",
                "first_inspection_started_datetime",
                "inspection_worktime_hour",
                "annotation_count",
                "input_data_count",
                "inspection_comment_count",
            ]
        )
        for fig in figs:
            fig.add_tools(hover_tool)
            add_legend_to_figure(fig)

        write_bokeh_graph(bokeh.layouts.column(figs), output_file)


class AcceptorCumulativeProductivity(AbstractRoleCumulativeProductivity):
    def __init__(self, df: pandas.DataFrame):
        super().__init__(df, phase="acceptance")

    def _get_cumulative_dataframe(self) -> pandas.DataFrame:
        """
        最初のアノテーション作業の開始時刻の順にソートして、受入者に関する累計値を算出する
        """
        df = self.df.sort_values(["first_acceptance_user_id", "first_acceptance_started_datetime"]).reset_index(
            drop=True
        )
        groupby_obj = df.groupby("first_acceptance_user_id")

        # 作業時間の累積値
        df["cumulative_acceptance_worktime_hour"] = groupby_obj["acceptance_worktime_hour"].cumsum()
        df["cumulative_annotation_count"] = groupby_obj["annotation_count"].cumsum()
        df["cumulative_input_data_count"] = groupby_obj["input_data_count"].cumsum()

        return df

    def plot_annotation_metrics(
        self,
        output_file: Path,
        target_user_id_list: Optional[list[str]] = None,
    ):
        """
        生産性を受入作業者ごとにプロットする。

        Args:
            df:
            first_acceptance_user_id_list:

        Returns:

        """

        if not self._validate_df_for_output(output_file):
            return

        logger.debug(f"{output_file} を出力します。")

        if target_user_id_list is not None:
            user_id_list = target_user_id_list
        else:
            user_id_list = self.default_user_id_list

        user_id_list = get_plotted_user_id_list(user_id_list)

        fig_info_list = [
            dict(
                title="累積のアノテーション数と受入作業時間",
                y_column_name="cumulative_acceptance_worktime_hour",
                y_axis_label="受入作業時間[hour]",
            ),
        ]

        figs: list[bokeh.plotting.Figure] = []
        for fig_info in fig_info_list:
            figs.append(
                figure(
                    plot_width=self.PLOT_WIDTH,
                    plot_height=self.PLOT_HEIGHT,
                    title=fig_info["title"],
                    x_axis_label="アノテーション数",
                    y_axis_label=fig_info["y_axis_label"],
                )
            )

        for user_index, user_id in enumerate(user_id_list):
            df_subset = self.df_cumulative[self.df_cumulative["first_acceptance_user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["first_acceptance_username"]

            for fig, fig_info in zip(figs, fig_info_list):
                plot_line_and_circle(
                    fig,
                    x_column_name="cumulative_annotation_count",
                    y_column_name=fig_info["y_column_name"],
                    source=source,
                    legend_label=username,
                    color=color,
                )

        hover_tool = create_hover_tool(
            [
                "task_id",
                "phase",
                "status",
                "first_acceptance_user_id",
                "first_acceptance_username",
                "first_acceptance_started_datetime",
                "acceptance_worktime_hour",
                "annotation_count",
                "input_data_count",
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
        受入者の累積値を入力データ単位でプロットする。

        """

        if not self._validate_df_for_output(output_file):
            return

        logger.debug(f"{output_file} を出力します。")

        if target_user_id_list is not None:
            user_id_list = target_user_id_list
        else:
            user_id_list = self.default_user_id_list

        user_id_list = get_plotted_user_id_list(user_id_list)

        fig_info_list = [
            dict(
                title="累積の入力データ数と受入作業時間",
                y_column_name="cumulative_acceptance_worktime_hour",
                y_axis_label="受入作業時間[hour]",
            ),
        ]

        figs: list[bokeh.plotting.Figure] = []
        for fig_info in fig_info_list:
            figs.append(
                figure(
                    plot_width=self.PLOT_WIDTH,
                    plot_height=self.PLOT_HEIGHT,
                    title=fig_info["title"],
                    x_axis_label="入力データ数",
                    y_axis_label=fig_info["y_axis_label"],
                )
            )

        for user_index, user_id in enumerate(user_id_list):
            df_subset = self.df_cumulative[self.df_cumulative["first_acceptance_user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["first_acceptance_username"]

            for fig, fig_info in zip(figs, fig_info_list):
                plot_line_and_circle(
                    fig,
                    x_column_name="cumulative_input_data_count",
                    y_column_name=fig_info["y_column_name"],
                    source=source,
                    legend_label=username,
                    color=color,
                )

        hover_tool = create_hover_tool(
            [
                "task_id",
                "phase",
                "status",
                "first_acceptance_user_id",
                "first_acceptance_username",
                "first_acceptance_started_datetime",
                "acceptance_worktime_hour",
                "annotation_count",
                "input_data_count",
                "acceptance_count",
            ]
        )
        for fig in figs:
            fig.add_tools(hover_tool)
            add_legend_to_figure(fig)

        write_bokeh_graph(bokeh.layouts.column(figs), output_file)
