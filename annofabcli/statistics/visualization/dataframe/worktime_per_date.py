# pylint: disable=too-many-lines
"""
日ごとユーザごとの生産性
"""
from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Any, Optional

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
from annofabcli.statistics.list_worktime import get_worktime_dict_from_event_list
from annofabcli.task_history_event.list_worktime import (
    ListWorktimeFromTaskHistoryEventMain,
    WorktimeFromTaskHistoryEvent,
)

logger = logging.getLogger(__name__)


def get_df_worktime(
    task_history_event_list: list[WorktimeFromTaskHistoryEvent],
    member_list: list[dict[str, Any]],
    df_labor: Optional[pandas.DataFrame] = None,
) -> pandas.DataFrame:
    dict_worktime = get_worktime_dict_from_event_list(task_history_event_list)

    s = pandas.Series(
        dict_worktime.values(),
        index=pandas.MultiIndex.from_tuples(dict_worktime.keys(), names=("date", "account_id", "phase")),
    )
    df = s.unstack()
    df.reset_index(inplace=True)
    df.rename(
        columns={
            "annotation": "monitored_annotation_worktime_hour",
            "inspection": "monitored_inspection_worktime_hour",
            "acceptance": "monitored_acceptance_worktime_hour",
        },
        inplace=True,
    )

    # 列数を固定させる
    for phase in ["annotation", "inspection", "acceptance"]:
        column = f"{phase}_worktime_hour"
        if column not in df.columns:
            df[column] = 0

    df.fillna(
        {
            "monitored_annotation_worktime_hour": 0,
            "monitored_inspection_worktime_hour": 0,
            "monitored_acceptance_worktime_hour": 0,
        },
        inplace=True,
    )

    # フェーズごとのmonitor_worktime_hour 列がない場合は、強制的に列を作成する
    for phase in ["annotation", "inspection", "acceptance"]:
        if f"monitored_{phase}_worktime_hour" not in df.columns:
            df[f"monitored_{phase}_worktime_hour"] = 0

    df["monitored_worktime_hour"] = (
        df["monitored_annotation_worktime_hour"]
        + df["monitored_inspection_worktime_hour"]
        + df["monitored_acceptance_worktime_hour"]
    )

    df_member = pandas.DataFrame(member_list)[["account_id", "user_id", "username", "biography"]]

    if df_labor is not None and len(df_labor) > 0:
        df = df.merge(df_labor[["date", "actual_worktime_hour", "account_id"]], how="outer", on=["date", "account_id"])
    else:
        df["actual_worktime_hour"] = 0

    value_columns = [
        "actual_worktime_hour",
        "monitored_worktime_hour",
        "monitored_annotation_worktime_hour",
        "monitored_inspection_worktime_hour",
        "monitored_acceptance_worktime_hour",
    ]
    df.fillna({c: 0 for c in value_columns}, inplace=True)

    df = df.merge(df_member, how="left", on="account_id")
    return df[
        [
            "date",
            "account_id",
            "user_id",
            "username",
            "biography",
            "actual_worktime_hour",
            "monitored_worktime_hour",
            "monitored_annotation_worktime_hour",
            "monitored_inspection_worktime_hour",
            "monitored_acceptance_worktime_hour",
        ]
    ]


class WorktimePerDate:
    PLOT_WIDTH = 1200
    PLOT_HEIGHT = 600

    def __init__(self, df: pandas.DataFrame):
        self.df = df

    @classmethod
    def from_webapi(
        cls, service: annofabapi.Resource, project_id: str, df_labor: Optional[pandas.DataFrame] = None
    ) -> WorktimePerDate:
        """

        Args:
            service (annofabapi.Resource): [description]
            project_id (str): [description]
            df_labor: 実績作業時間が格納されたDataFrame。date, account_id, actual_worktime_hour 列を参照する。

        Returns:
            WorktimePerDate: [description]
        """
        main_obj = ListWorktimeFromTaskHistoryEventMain(service, project_id=project_id)
        worktime_list = main_obj.get_worktime_list(
            project_id,
        )
        project_member_list = service.wrapper.get_all_project_members(
            project_id, query_params={"include_inactive_member": ""}
        )
        if df_labor is not None:
            df = get_df_worktime(worktime_list, project_member_list, df_labor=df_labor)
        else:
            df = get_df_worktime(worktime_list, project_member_list)
        return cls(df)

    def _get_cumulative_dataframe(self) -> pandas.DataFrame:
        """
        累積情報が格納されたDataFrameを生成する。
        """
        # 教師付の開始時刻でソートして、indexを更新する
        df = self.df.sort_values(["user_id", "date"]).reset_index(drop=True)
        groupby_obj = df.groupby("user_id")

        # 作業時間の累積値
        df["cumulative_actual_worktime_hour"] = groupby_obj["actual_worktime_hour"].cumsum()
        df["cumulative_monitored_worktime_hour"] = groupby_obj["monitored_worktime_hour"].cumsum()
        df["cumulative_monitored_annotation_worktime_hour"] = groupby_obj["monitored_annotation_worktime_hour"].cumsum()
        df["cumulative_monitored_acceptance_worktime_hour"] = groupby_obj["monitored_acceptance_worktime_hour"].cumsum()
        df["cumulative_monitored_inspection_worktime_hour"] = groupby_obj["monitored_inspection_worktime_hour"].cumsum()

        return df

    @classmethod
    def merge(cls, obj1: WorktimePerDate, obj2: WorktimePerDate) -> WorktimePerDate:

        df_tmp = pandas.concat([obj1.df, obj2.df])

        df = df_tmp.groupby(["date", "user_id"])[
            [
                "actual_worktime_hour",
                "monitored_worktime_hour",
                "monitored_annotation_worktime_hour",
                "monitored_inspection_worktime_hour",
                "monitored_acceptance_worktime_hour",
            ]
        ].sum()
        df.reset_index(inplace=True)

        df_user = df_tmp.drop_duplicates(subset="user_id")[["user_id", "username", "biography"]]

        df = df.merge(df_user, on="user_id", how="left")

        return cls(df)

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
                title="実績作業時間の累積値",
                y_column_name="cumulative_actual_worktime_hour",
            ),
            dict(
                title="計測作業時間の累積値",
                y_column_name="cumulative_monitored_worktime_hour",
            ),
            dict(
                title="教師付計測作業時間の累積値",
                y_column_name="cumulative_monitored_annotation_worktime_hour",
            ),
            dict(
                title="検査計測作業時間の累積値",
                y_column_name="cumulative_monitored_inspection_worktime_hour",
            ),
            dict(
                title="受入計測作業時間の累積値",
                y_column_name="cumulative_monitored_acceptance_worktime_hour",
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
                    y_axis_label="作業時間[hour]",
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
                "monitored_worktime_hour",
                "monitored_annotation_worktime_hour",
                "monitored_inspection_worktime_hour",
                "monitored_acceptance_worktime_hour",
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
            "actual_worktime_hour",
            "monitored_worktime_hour",
            "monitored_annotation_worktime_hour",
            "monitored_inspection_worktime_hour",
            "monitored_acceptance_worktime_hour",
        ]

        columns = date_user_columns + worktime_columns

        print_csv(self.df[columns], output=str(output_file))
