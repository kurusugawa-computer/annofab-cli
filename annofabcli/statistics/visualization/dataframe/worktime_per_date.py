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
from bokeh.plotting import ColumnDataSource

from annofabcli.common.utils import print_csv
from annofabcli.statistics.linegraph import (
    LineGraph,
    get_color_from_palette,
    get_plotted_user_id_list,
    write_bokeh_graph,
)
from annofabcli.statistics.list_worktime import get_worktime_dict_from_event_list
from annofabcli.task_history_event.list_worktime import (
    ListWorktimeFromTaskHistoryEventMain,
    WorktimeFromTaskHistoryEvent,
)

logger = logging.getLogger(__name__)


class WorktimePerDate:
    """
    日ごとユーザごとの作業時間情報
    """

    df_dtype = {
        "date": "string",
        "user_id": "string",
        "username": "string",
        "biography": "string",
        "actual_worktime_hour": "float64",
        "monitored_worktime_hour": "float64",
        "monitored_annotation_worktime_hour": "float64",
        "monitored_inspection_worktime_hour": "float64",
        "monitored_acceptance_worktime_hour": "float64",
    }

    def __init__(self, df: pandas.DataFrame):
        self.df = df

    @classmethod
    def from_csv(cls, csv_file: Path) -> WorktimePerDate:
        """CSVファイルからインスタンスを生成します。"""
        df = pandas.read_csv(str(csv_file), dtype=cls.df_dtype)
        return cls(df)

    @classmethod
    def empty(cls) -> WorktimePerDate:
        """空のデータフレームを持つインスタンスを生成します。"""
        df = pandas.DataFrame(columns=cls.df_dtype.values()).astype(cls.df_dtype)
        return cls(df)

    @classmethod
    def get_df_worktime(
        cls,
        task_history_event_list: list[WorktimeFromTaskHistoryEvent],
        df_member: pandas.DataFrame,
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

        if df_labor is not None and len(df_labor) > 0:
            df = df.merge(
                df_labor[["date", "actual_worktime_hour", "account_id"]], how="outer", on=["date", "account_id"]
            )
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

    @classmethod
    def _get_df_member(cls, service: annofabapi.Resource, project_id: str) -> pandas.DataFrame:
        """project_idに関するメンバ情報を取得します。
        Annoworkで作業したメンバが、Annofabのプロジェクトで作業していない場合もあるので、
        できるだけたくさんのメンバを取得できるようにするため、組織メンバを取得しています。
        """
        project_member_list = service.wrapper.get_all_project_members(
            project_id, query_params={"include_inactive_member": ""}
        )
        df_project_member = pandas.DataFrame(project_member_list)
        organization, _ = service.api.get_organization_of_project(project_id)
        organization_member_list = service.wrapper.get_all_organization_members(organization["organization_name"])
        df_organization_member = pandas.DataFrame(organization_member_list)

        df_member = pandas.concat([df_project_member, df_organization_member])[
            ["account_id", "user_id", "username", "biography"]
        ]
        df_member.drop_duplicates(subset=["account_id", "user_id", "username", "biography"], inplace=True)
        return df_member

    @classmethod
    def from_webapi(
        cls,
        service: annofabapi.Resource,
        project_id: str,
        df_labor: Optional[pandas.DataFrame] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> WorktimePerDate:
        """

        Args:
            service (annofabapi.Resource): [description]
            project_id (str): [description]
            df_labor: 実績作業時間が格納されたDataFrame。date, account_id, actual_worktime_hour 列を参照する。
            start_date: 指定した日以降で絞り込みます
            end_date: 指定した日以前で絞り込みます

        Returns:
            WorktimePerDate: [description]
        """

        main_obj = ListWorktimeFromTaskHistoryEventMain(service, project_id=project_id)
        worktime_list = main_obj.get_worktime_list(
            project_id,
        )

        df_member = cls._get_df_member(service, project_id)

        df = cls.get_df_worktime(worktime_list, df_member, df_labor=df_labor)
        if start_date is not None:
            df = df[df["date"] >= start_date]
        if end_date is not None:
            df = df[df["date"] <= end_date]
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

        x_axis_label = "日"
        x_column = "dt_date"
        tooltip_columns = [
            "date",
            "user_id",
            "username",
            "biography",
            "actual_worktime_hour",
            "monitored_worktime_hour",
            "monitored_annotation_worktime_hour",
            "monitored_inspection_worktime_hour",
            "monitored_acceptance_worktime_hour",
        ]

        line_graph_list = [
            LineGraph(
                title="実績作業時間の累積値",
                y_column="cumulative_actual_worktime_hour",
                y_axis_label="実績作業時間[hour]",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_column=x_column,
                x_axis_type="datetime",
            ),
            LineGraph(
                title="計測作業時間の累積値",
                y_column="cumulative_monitored_worktime_hour",
                y_axis_label="計測作業時間[hour]",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_column=x_column,
                x_axis_type="datetime",
            ),
            LineGraph(
                title="教師付計測作業時間の累積値",
                y_column="cumulative_monitored_annotation_worktime_hour",
                y_axis_label="教師付計測作業時間[hour]",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_column=x_column,
                x_axis_type="datetime",
            ),
            LineGraph(
                title="検査計測作業時間の累積値",
                y_column="cumulative_monitored_inspection_worktime_hour",
                y_axis_label="検査計測作業時間[hour]",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_column=x_column,
                x_axis_type="datetime",
            ),
            LineGraph(
                title="受入計測作業時間の累積値",
                y_column="cumulative_monitored_acceptance_worktime_hour",
                y_axis_label="受入計測作業時間[hour]",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_column=x_column,
                x_axis_type="datetime",
            ),
        ]

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

            for line_graph in line_graph_list:
                line_graph.add_line(
                    source=source,
                    legend_label=username,
                    color=color,
                )

        graph_group_list = []
        for line_graph in line_graph_list:
            line_graph.config_legend()
            hide_all_button = line_graph.create_button_hiding_all_lines()
            checkbox_group = line_graph.create_checkbox_displaying_markers()

            widgets = bokeh.layouts.column([hide_all_button, checkbox_group])
            graph_group = bokeh.layouts.row([line_graph.figure, widgets])
            graph_group_list.append(graph_group)

        write_bokeh_graph(bokeh.layouts.layout(graph_group_list), output_file)

    def to_csv(self, output_file: Path) -> None:
        if not self._validate_df_for_output(output_file):
            return

        columns = self.df_dtype.values()

        print_csv(self.df[columns], output=str(output_file))
