# pylint: disable=too-many-lines
"""
日ごとユーザごとの生産性
"""
from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Optional

import annofabapi
import bokeh
import bokeh.layouts
import bokeh.palettes
import pandas
from bokeh.plotting import ColumnDataSource, figure

from annofabcli.common.utils import print_csv
from annofabcli.statistics.linegraph import (
    add_legend_to_figure,
    create_hover_tool,
    get_color_from_palette,
    get_plotted_user_id_list,
    plot_line_and_circle,
    write_bokeh_graph,
)
from annofabcli.statistics.list_worktime import get_df_worktime
from annofabcli.task_history_event.list_worktime import ListWorktimeFromTaskHistoryEventMain

logger = logging.getLogger(__name__)


class WorktimePerDate:
    PLOT_WIDTH = 1200
    PLOT_HEIGHT = 600

    def __init__(self, df: pandas.DataFrame):
        self.df = df

    @staticmethod
    def from_webapi(service: annofabapi.Resource, project_id: str) -> WorktimePerDate:
        main_obj = ListWorktimeFromTaskHistoryEventMain(service, project_id=project_id)
        worktime_list = main_obj.get_worktime_list(
            project_id,
        )
        project_member_list = service.wrapper.get_all_project_members(
            project_id, query_params={"include_inactive_member": ""}
        )
        df = get_df_worktime(worktime_list, project_member_list)
        return WorktimePerDate(df)

    def _get_cumulative_dataframe(self) -> pandas.DataFrame:
        """
        累積情報が格納されたDataFrameを生成する。
        """
        # 教師付の開始時刻でソートして、indexを更新する
        df = self.df.sort_values(["user_id", "date"]).reset_index(drop=True)
        groupby_obj = df.groupby("user_id")

        # 作業時間の累積値
        df["cumulative_worktime_hour"] = groupby_obj["worktime_hour"].cumsum()
        df["cumulative_annotation_worktime_hour"] = groupby_obj["annotation_worktime_hour"].cumsum()
        df["cumulative_acceptance_worktime_hour"] = groupby_obj["acceptance_worktime_hour"].cumsum()
        df["cumulative_inspection_worktime_hour"] = groupby_obj["inspection_worktime_hour"].cumsum()

        return df

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False

        return True

    def _get_default_user_id_list(self) -> list[str]:
        return self.df.sort_values(by=f"date", ascending=False)[f"user_id"].dropna().unique().tolist()

    def plot_cumulatively(
        self,
        output_file: Path,
        target_user_id_list: Optional[list[str]] = None,
    ):
        """
        作業時間の累積値をプロットする。
        """

        if not self._validate_df_for_output(output_file):
            return

        logger.debug(f"{output_file} を出力します。")

        if target_user_id_list is not None:
            user_id_list = target_user_id_list
        else:
            user_id_list = self._get_default_user_id_list()

        user_id_list = get_plotted_user_id_list(user_id_list)

        fig_info_list = [
            dict(
                title="作業時間の累積値",
                y_column_name="cumulative_worktime_hour",
                y_axis_label="作業時間[hour]",
            ),
            dict(
                title="教師付作業時間の累積値",
                y_column_name="cumulative_annotation_worktime_hour",
                y_axis_label="教師付作業時間[hour]",
            ),
            dict(
                title="検査作業時間の累積値",
                y_column_name="cumulative_inspection_worktime_hour",
                y_axis_label="検査作業時間[hour]",
            ),
            dict(
                title="受入作業時間の累積値",
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
                    x_axis_label="日",
                    x_axis_type="datetime",
                    y_axis_label=fig_info["y_axis_label"],
                )
            )

        df_cumulative = self._get_cumulative_dataframe()
        df_cumulative["dt_date"] = df_cumulative["date"].map(lambda e: datetime.datetime.fromisoformat(e).date())
        for user_index, user_id in enumerate(user_id_list):
            df_subset = df_cumulative[df_cumulative["user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["username"]

            for fig, fig_info in zip(figs, fig_info_list):
                plot_line_and_circle(
                    fig,
                    x_column_name="dt_date",
                    y_column_name=fig_info["y_column_name"],
                    source=source,
                    legend_label=username,
                    color=color,
                )

        hover_tool = create_hover_tool(
            [
                "date",
                "user_id",
                "username",
                "biography",
                "worktime_hour",
                "annotation_worktime_hour",
                "inspection_worktime_hour",
                "acceptance_worktime_hour",
            ]
        )
        for fig in figs:
            fig.add_tools(hover_tool)
            add_legend_to_figure(fig)

        write_bokeh_graph(bokeh.layouts.column(figs), output_file)

    def to_csv(self, output_file: Path) -> None:
        if not self._validate_df_for_output(output_file):
            return

        date_user_columns = [
            "date",
            "user_id",
            "username",
            "biography",
        ]
        worktime_columns = [
            "worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
        ]

        columns = date_user_columns + worktime_columns

        print_csv(self.df[columns], output=str(output_file))
