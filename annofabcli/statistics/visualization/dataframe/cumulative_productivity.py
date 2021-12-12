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

    def __init__(self, df: pandas.DataFrame) -> None:
        self.df = df

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    # @abc.abstractmethod
    # def plot_input_data_metrics(self, output_file: Path, target_user_id_list: Optional[list[str]] = None):
    #     pass

    @abc.abstractmethod
    def plot_annotation_metrics(self, output_file: Path, target_user_id_list: Optional[list[str]] = None):
        pass


class AnnotatorCumulativeProductivity(AbstractRoleCumulativeProductivity):
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
        df = self.df.copy()

        if target_user_id_list is not None:
            user_id_list = target_user_id_list
        else:
            user_id_list = (
                df.sort_values(by="first_annotation_started_datetime", ascending=False)["first_annotation_user_id"]
                .dropna()
                .unique()
                .tolist()
            )

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
                y_column_name="cumulative_inspection_count",
                y_axis_label="検査コメント数",
            ),
        ]

        figs: list[bokeh.plotting.Figure] = []
        for fig_info in fig_info_list:
            figs.append(
                figure(
                    plot_width=1200,
                    plot_height=600,
                    title=fig_info["title"],
                    x_axis_label="アノテーション数",
                    y_axis_label=fig_info["y_axis_label"],
                )
            )

        for user_index, user_id in enumerate(user_id_list):
            df_subset = df[df["first_annotation_user_id"] == user_id].copy()
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            df_subset.sort_values(["first_annotation_started_datetime"], inplace=True)

            # 作業時間の累積値
            df_subset["cumulative_annotation_worktime_hour"] = df_subset["annotation_worktime_hour"].cumsum()
            df_subset["cumulative_inspection_worktime_hour"] = df_subset["inspection_worktime_hour"].cumsum()
            df_subset["cumulative_acceptance_worktime_hour"] = df_subset["acceptance_worktime_hour"].cumsum()

            # タスク完了数、差し戻し数など
            df_subset["cumulative_inspection_count"] = df_subset["inspection_count"].cumsum()
            df_subset["cumulative_annotation_count"] = df_subset["annotation_count"].cumsum()

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
                "inspection_count",
            ]
        )
        for fig in figs:
            fig.add_tools(hover_tool)
            add_legend_to_figure(fig)

        write_bokeh_graph(bokeh.layouts.column(figs), output_file)
