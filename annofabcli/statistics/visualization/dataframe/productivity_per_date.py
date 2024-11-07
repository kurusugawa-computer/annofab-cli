"""
日ごとユーザごとの生産性
"""

from __future__ import annotations

import abc
import logging
from pathlib import Path
from typing import Any, Optional

import bokeh
import bokeh.layouts
import bokeh.palettes
import pandas
from annofabapi.models import TaskPhase
from bokeh.models.ui import UIElement
from bokeh.models.widgets.widget import Widget
from bokeh.plotting import ColumnDataSource
from dateutil.parser import parse

from annofabcli.common.bokeh import create_pretext_from_metadata
from annofabcli.common.utils import datetime_to_date, print_csv
from annofabcli.statistics.linegraph import (
    WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX,
    LineGraph,
    get_color_from_palette,
    get_plotted_user_id_list,
    get_weekly_sum,
    write_bokeh_graph,
)
from annofabcli.statistics.visualization.dataframe.task import Task
from annofabcli.statistics.visualization.model import ProductionVolumeColumn

logger = logging.getLogger(__name__)


class AbstractPhaseProductivityPerDate(abc.ABC):
    """ロールごとの日ごとの生産性に関する情報を格納する抽象クラス"""

    PLOT_WIDTH = 1200
    PLOT_HEIGHT = 600

    def __init__(
        self, df: pandas.DataFrame, phase: TaskPhase, *, custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None
    ) -> None:
        self.df = df
        self.phase = phase
        self.custom_production_volume_list = custom_production_volume_list if custom_production_volume_list is not None else []
        self.production_volume_columns = ["input_data_count", "annotation_count", *[e.value for e in self.custom_production_volume_list]]

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    @staticmethod
    def _plot(
        line_graph_list: list[LineGraph],
        plotted_users: list[tuple[str, str]],
        output_file: Path,
        metadata: Optional[dict[str, Any]],
    ) -> None:
        """
        折れ線グラフを、HTMLファイルに出力します。
        """
        graph_group_list: list[UIElement] = []
        for line_graph in line_graph_list:
            line_graph.process_after_adding_glyphs()

            widget_list: list[Widget] = []
            hide_all_button = line_graph.create_button_hiding_showing_all_lines(is_hiding=True)
            show_all_button = line_graph.create_button_hiding_showing_all_lines(is_hiding=False)
            widget_list.extend([hide_all_button, show_all_button])

            # マーカーがある場合は、マーカーを表示/非表示切り替えられるチェックボックスを配置する
            if len(line_graph.marker_glyphs) > 0:
                checkbox_group = line_graph.create_checkbox_displaying_markers()
                widget_list.append(checkbox_group)

            multi_choice_widget = line_graph.create_multi_choice_widget_for_searching_user(plotted_users)
            widget_list.append(multi_choice_widget)

            widgets = bokeh.layouts.column(widget_list)
            graph_group = bokeh.layouts.row([line_graph.figure, widgets])
            graph_group_list.append(graph_group)

        if metadata is not None:
            graph_group_list.insert(0, create_pretext_from_metadata(metadata))

        write_bokeh_graph(bokeh.layouts.layout(graph_group_list), output_file)

    @classmethod
    @abc.abstractmethod
    def from_task(cls, task: Task) -> AbstractPhaseProductivityPerDate:
        raise NotImplementedError()

    @abc.abstractmethod
    def to_csv(self, output_file: Path) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    def plot_production_volume_metrics(
        self,
        production_volume_column: str,
        production_volume_name: str,
        output_file: Path,
        *,
        target_user_id_list: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        raise NotImplementedError()


class AnnotatorProductivityPerDate(AbstractPhaseProductivityPerDate):
    """教師付開始日ごとの教師付者の生産性に関する情報"""

    def __init__(self, df: pandas.DataFrame, *, custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None) -> None:
        super().__init__(df, phase=TaskPhase.ANNOTATION, custom_production_volume_list=custom_production_volume_list)

    @classmethod
    def from_task(cls, task: Task) -> AnnotatorProductivityPerDate:
        """
        日毎、ユーザごとの情報を出力する。

        Args:
            task_df:

        Returns:

        """
        new_df = task.df.copy()
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

        production_volume_columns = ["input_data_count", "annotation_count", *[e.value for e in task.custom_production_volume_list]]
        sum_df = group_obj[
            [
                "first_annotation_worktime_hour",
                "annotation_worktime_hour",
                "inspection_worktime_hour",
                "acceptance_worktime_hour",
                "worktime_hour",
                "task_count",
                *production_volume_columns,
                "inspection_comment_count",
            ]
        ].sum(numeric_only=True)

        for denominator_column in production_volume_columns:
            for numerator_column in ["annotation_worktime_hour", "inspection_worktime_hour", "acceptance_worktime_hour", "inspection_comment_count"]:
                sum_df[f"{numerator_column}/{denominator_column}"] = sum_df[numerator_column] / sum_df[denominator_column]

        return cls(sum_df, custom_production_volume_list=task.custom_production_volume_list)

    def _get_df_sequential_date(self, df: pandas.DataFrame) -> pandas.DataFrame:
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
                    *self.production_volume_columns,
                ]
            },
            inplace=True,
        )

        return df2

    def plot_production_volume_metrics(
        self,
        production_volume_column: str,
        production_volume_name: str,
        output_file: Path,
        *,
        target_user_id_list: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
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
            user_id_list = df.sort_values(by="first_annotation_started_date", ascending=False)["first_annotation_user_id"].dropna().unique().tolist()

        user_id_list = get_plotted_user_id_list(user_id_list)

        x_axis_label = "教師付開始日"
        tooltip_columns = [
            "first_annotation_user_id",
            "first_annotation_username",
            "first_annotation_started_date",
            "annotation_worktime_hour",
            "task_count",
            production_volume_column,
            f"annotation_worktime_minute/{production_volume_column}",
            "inspection_comment_count",
            f"inspection_comment_count/{production_volume_column}",
        ]
        line_graph_list = [
            LineGraph(
                title="教師付開始日ごとの教師付作業時間",
                y_axis_label="教師付作業時間[時間]",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_axis_type="datetime",
            ),
            LineGraph(
                title=f"教師付開始日ごとの{production_volume_name}あたり教師付作業時間",
                y_axis_label=f"アノテーションあたり教師付時間[分/{production_volume_name}]",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_axis_type="datetime",
            ),
            LineGraph(
                title=f"教師付開始日ごとの{production_volume_name}あたり教師付作業時間(1週間移動平均)",
                y_axis_label=f"アノテーションあたり教師付時間[分/{production_volume_name}]",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_axis_type="datetime",
            ),
            LineGraph(
                title=f"教師付開始日ごとの{production_volume_name}あたり検査コメント数",
                y_axis_label=f"{production_volume_name}あたり検査コメント数",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_axis_type="datetime",
            ),
            LineGraph(
                title=f"教師付開始日ごとの{production_volume_name}あたり検査コメント数(1週間移動平均)",
                y_axis_label=f"{production_volume_name}あたり検査コメント数",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_axis_type="datetime",
            ),
        ]

        x_column = "dt_first_annotation_started_date"
        columns_list = [
            (x_column, "annotation_worktime_hour"),
            (x_column, f"annotation_worktime_minute/{production_volume_column}"),
            (x_column, f"annotation_worktime_minute/{production_volume_column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"),
            (x_column, f"inspection_comment_count/{production_volume_column}"),
            (x_column, f"inspection_comment_count/{production_volume_column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"),
        ]

        logger.debug(f"{output_file} を出力します。")

        line_count = 0
        plotted_users: list[tuple[str, str]] = []
        for user_index, user_id in enumerate(user_id_list):
            df_subset = df[df["first_annotation_user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            df_subset = self._get_df_sequential_date(df_subset)
            df_subset[f"annotation_worktime_minute/{production_volume_column}"] = (
                df_subset["annotation_worktime_hour"] * 60 / df_subset[production_volume_column]
            )
            df_subset[f"annotation_worktime_minute/{production_volume_column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = (
                get_weekly_sum(df_subset["annotation_worktime_hour"]) * 60 / get_weekly_sum(df_subset[production_volume_column])
            )
            df_subset[f"inspection_comment_count/{production_volume_column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = get_weekly_sum(
                df_subset["inspection_comment_count"]
            ) / get_weekly_sum(df_subset[production_volume_column])

            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["first_annotation_username"]

            line_count += 1
            for line_graph, (x_column, y_column) in zip(line_graph_list, columns_list):
                if y_column.endswith(WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX):
                    line_graph.add_moving_average_line(
                        source=source,
                        x_column=x_column,
                        y_column=y_column,
                        legend_label=username,
                        color=color,
                    )

                else:
                    line_graph.add_line(
                        source=source,
                        x_column=x_column,
                        y_column=y_column,
                        legend_label=username,
                        color=color,
                    )
            plotted_users.append((user_id, username))

        if line_count == 0:
            logger.warning(f"プロットするデータがなかっため、'{output_file}'は出力しません。")
            return

        self._plot(line_graph_list, plotted_users, output_file, metadata=metadata)

    def to_csv(self, output_file: Path) -> None:
        if not self._validate_df_for_output(output_file):
            return

        production_columns = [
            "first_annotation_started_date",
            "first_annotation_user_id",
            "first_annotation_username",
            "task_count",
            *self.production_volume_columns,
            "inspection_comment_count",
            "worktime_hour",
            "annotation_worktime_hour",
            # 品質の指標として検査者/受入者が使った時間を使うときがあるので、検査時間と受入時間も出力する
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
        ]

        velocity_columns = [
            f"{numerator}/{denominator}"
            for numerator in ["annotation_worktime_hour", "inspection_worktime_hour", "acceptance_worktime_hour"]
            for denominator in self.production_volume_columns
        ]

        quality_columns = [f"inspection_comment_count/{denominator}" for denominator in self.production_volume_columns]

        columns = production_columns + velocity_columns + quality_columns
        print_csv(self.df[columns], output=str(output_file))


class InspectorProductivityPerDate(AbstractPhaseProductivityPerDate):
    """検査開始日ごとの検査者の生産性に関する情報"""

    def __init__(self, df: pandas.DataFrame, *, custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None) -> None:
        super().__init__(df, phase=TaskPhase.INSPECTION, custom_production_volume_list=custom_production_volume_list)

    @classmethod
    def from_task(cls, task: Task) -> InspectorProductivityPerDate:
        """
        検査開始日ごとの受入者の生産性に関するDataFrameを生成する。

        Args:
            df_task:

        Returns:

        """
        new_df = task.df.copy()
        new_df["first_inspection_started_date"] = new_df["first_inspection_started_datetime"].map(
            lambda e: datetime_to_date(e) if e is not None and isinstance(e, str) else None
        )
        new_df["task_count"] = 1  # 集計用

        # first_inspection_username を列に追加するために、first_inspection_user_idだけでなくfirst_inspection_usernameもgroupby関数のキーに指定した
        group_obj = new_df.groupby(
            ["first_inspection_started_date", "first_inspection_user_id", "first_inspection_username"],
            as_index=False,
        )

        production_volume_columns = ["input_data_count", "annotation_count", *[e.value for e in task.custom_production_volume_list]]
        sum_df = group_obj[["first_inspection_worktime_hour", "inspection_worktime_hour", "task_count", *production_volume_columns]].sum(
            numeric_only=True
        )

        for denominator_column in production_volume_columns:
            sum_df[f"inspection_worktime_hour/{denominator_column}"] = sum_df["inspection_worktime_hour"] / sum_df[denominator_column]

        return cls(sum_df, custom_production_volume_list=task.custom_production_volume_list)

    def _get_df_sequential_date(self, df: pandas.DataFrame) -> pandas.DataFrame:
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
            {key: 0 for key in ["first_inspection_worktime_hour", "inspection_worktime_hour", "task_count", *self.production_volume_columns]},
            inplace=True,
        )
        return df2

    def plot_production_volume_metrics(
        self,
        production_volume_column: str,
        production_volume_name: str,
        output_file: Path,
        *,
        target_user_id_list: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        アノテーション単位の生産性を受入作業者ごとにプロットする。

        """

        if not self._validate_df_for_output(output_file):
            return

        df = self.df.copy()

        if target_user_id_list is not None:
            user_id_list = target_user_id_list
        else:
            user_id_list = df.sort_values(by="first_inspection_started_date", ascending=False)["first_inspection_user_id"].dropna().unique().tolist()

        user_id_list = get_plotted_user_id_list(user_id_list)

        x_axis_label = "検査開始日"
        tooltip_columns = [
            "first_inspection_user_id",
            "first_inspection_username",
            "first_inspection_started_date",
            "inspection_worktime_hour",
            "task_count",
            production_volume_column,
            f"inspection_worktime_hour/{production_volume_column}",
        ]

        line_graph_list = [
            LineGraph(
                title="検査開始日ごとの検査作業時間",
                y_axis_label="検査作業時間[時間]",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_axis_type="datetime",
            ),
            LineGraph(
                title=f"検査開始日ごとの{production_volume_name}あたり検査作業時間",
                y_axis_label=f"{production_volume_name}あたり検査作業時間[分/アノテーション]",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_axis_type="datetime",
            ),
            LineGraph(
                title=f"検査開始日ごとの{production_volume_name}あたり検査作業時間(1週間移動平均)",
                y_axis_label=f"{production_volume_name}あたり検査作業時間[分/アノテーション]",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_axis_type="datetime",
            ),
        ]

        x_column = "dt_first_inspection_started_date"
        columns_list = [
            (x_column, "inspection_worktime_hour"),
            (x_column, f"inspection_worktime_minute/{production_volume_column}"),
            (x_column, f"inspection_worktime_minute/{production_volume_column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"),
        ]

        logger.debug(f"{output_file} を出力します。")

        line_count = 0
        plotted_users: list[tuple[str, str]] = []
        for user_index, user_id in enumerate(user_id_list):
            df_subset = df[df["first_inspection_user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            df_subset = self._get_df_sequential_date(df_subset)
            df_subset[f"inspection_worktime_minute/{production_volume_column}"] = (
                df_subset["inspection_worktime_hour"] * 60 / df_subset[production_volume_column]
            )
            df_subset[f"inspection_worktime_minute/{production_volume_column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = (
                get_weekly_sum(df_subset["inspection_worktime_hour"]) * 60 / get_weekly_sum(df_subset[production_volume_column])
            )

            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["first_inspection_username"]

            for line_graph, (x_column, y_column) in zip(line_graph_list, columns_list):
                if y_column.endswith(WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX):
                    line_graph.add_moving_average_line(
                        source=source,
                        x_column=x_column,
                        y_column=y_column,
                        legend_label=username,
                        color=color,
                    )

                else:
                    line_graph.add_line(
                        source=source,
                        x_column=x_column,
                        y_column=y_column,
                        legend_label=username,
                        color=color,
                    )
            plotted_users.append((user_id, username))

        if line_count == 0:
            logger.warning(f"プロットするデータがなかっため、'{output_file}'は出力しません。")
            return

        self._plot(line_graph_list, plotted_users, output_file, metadata=metadata)

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
            *self.production_volume_columns,
            "inspection_worktime_hour",
        ]

        velocity_columns = [f"inspection_worktime_hour/{denominator}" for denominator in self.production_volume_columns]

        columns = production_columns + velocity_columns

        print_csv(self.df[columns], output=str(output_file))


class AcceptorProductivityPerDate(AbstractPhaseProductivityPerDate):
    """受入開始日ごとの受入者の生産性に関する情報"""

    def __init__(self, df: pandas.DataFrame, *, custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None) -> None:
        super().__init__(df, phase=TaskPhase.ACCEPTANCE, custom_production_volume_list=custom_production_volume_list)

    @classmethod
    def from_task(cls, task: Task) -> AcceptorProductivityPerDate:
        """
        受入開始日ごとの受入者の生産性に関するDataFrameを生成する。

        Args:
            df_task:

        Returns:

        """
        new_df = task.df.copy()
        new_df["first_acceptance_started_date"] = new_df["first_acceptance_started_datetime"].map(
            lambda e: datetime_to_date(e) if e is not None and isinstance(e, str) else None
        )
        new_df["task_count"] = 1  # 集計用

        # first_acceptance_username を列に追加するために、first_acceptance_user_idだけでなくfirst_acceptance_usernameもgroupby関数のキーに指定した
        group_obj = new_df.groupby(
            ["first_acceptance_started_date", "first_acceptance_user_id", "first_acceptance_username"],
            as_index=False,
        )

        production_volume_columns = ["input_data_count", "annotation_count", *[e.value for e in task.custom_production_volume_list]]
        sum_df = group_obj[["first_acceptance_worktime_hour", "acceptance_worktime_hour", "task_count", *production_volume_columns]].sum(
            numeric_only=True
        )

        for denominator_column in production_volume_columns:
            sum_df[f"acceptance_worktime_hour/{denominator_column}"] = sum_df["acceptance_worktime_hour"] / sum_df[denominator_column]

        return AcceptorProductivityPerDate(sum_df, custom_production_volume_list=task.custom_production_volume_list)

    def _get_df_sequential_date(self, df: pandas.DataFrame) -> pandas.DataFrame:
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
            {key: 0 for key in ["first_acceptance_worktime_hour", "acceptance_worktime_hour", "task_count", *self.production_volume_columns]},
            inplace=True,
        )
        return df2

    def plot_production_volume_metrics(
        self,
        production_volume_column: str,
        production_volume_name: str,
        output_file: Path,
        *,
        target_user_id_list: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        アノテーション単位の生産性を受入作業者ごとにプロットする。

        """

        if not self._validate_df_for_output(output_file):
            return

        df = self.df.copy()

        if target_user_id_list is not None:
            user_id_list = target_user_id_list
        else:
            user_id_list = df.sort_values(by="first_acceptance_started_date", ascending=False)["first_acceptance_user_id"].dropna().unique().tolist()

        user_id_list = get_plotted_user_id_list(user_id_list)

        x_axis_label = "受入開始日"
        x_column = "dt_first_acceptance_started_date"
        tooltip_columns = [
            "first_acceptance_user_id",
            "first_acceptance_username",
            "first_acceptance_started_date",
            "acceptance_worktime_hour",
            "task_count",
            production_volume_column,
            f"acceptance_worktime_hour/{production_volume_column}",
        ]

        line_graph_list = [
            LineGraph(
                title="受入開始日ごとの受入作業時間",
                y_axis_label="受入作業時間[時間]",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_axis_type="datetime",
            ),
            LineGraph(
                title=f"受入開始日ごとの{production_volume_name}あたり受入作業時間",
                y_axis_label=f"{production_volume_name}あたり受入時間[分/アノテーション]",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_axis_type="datetime",
            ),
            LineGraph(
                title=f"受入開始日ごとの{production_volume_name}あたり受入作業時間(1週間移動平均)",
                y_axis_label=f"{production_volume_name}あたり受入時間[分/{production_volume_name}]",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_axis_type="datetime",
            ),
        ]

        x_column = "dt_first_acceptance_started_date"
        columns_list = [
            (x_column, "acceptance_worktime_hour"),
            (x_column, f"acceptance_worktime_minute/{production_volume_column}"),
            (x_column, f"acceptance_worktime_minute/{production_volume_column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"),
        ]

        logger.debug(f"{output_file} を出力します。")

        line_count = 0
        plotted_users: list[tuple[str, str]] = []
        for user_index, user_id in enumerate(user_id_list):
            df_subset = df[df["first_acceptance_user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            df_subset = self._get_df_sequential_date(df_subset)
            df_subset[f"acceptance_worktime_minute/{production_volume_column}"] = (
                df_subset["acceptance_worktime_hour"] * 60 / df_subset[production_volume_column]
            )

            df_subset[f"acceptance_worktime_minute/{production_volume_column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = (
                get_weekly_sum(df_subset["acceptance_worktime_hour"]) * 60 / get_weekly_sum(df_subset[production_volume_column])
            )

            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["first_acceptance_username"]

            line_count += 1
            for line_graph, (x_column, y_column) in zip(line_graph_list, columns_list):
                if y_column.endswith(WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX):
                    line_graph.add_moving_average_line(
                        source=source,
                        x_column=x_column,
                        y_column=y_column,
                        legend_label=username,
                        color=color,
                    )

                else:
                    line_graph.add_line(
                        source=source,
                        x_column=x_column,
                        y_column=y_column,
                        legend_label=username,
                        color=color,
                    )
            plotted_users.append((user_id, username))

        if line_count == 0:
            logger.warning(f"プロットするデータがなかっため、'{output_file}'は出力しません。")
            return

        self._plot(line_graph_list, plotted_users, output_file, metadata=metadata)

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
            *self.production_volume_columns,
            "acceptance_worktime_hour",
        ]

        velocity_columns = [f"acceptance_worktime_hour/{denominator}" for denominator in self.production_volume_columns]

        columns = production_columns + velocity_columns

        print_csv(self.df[columns], output=str(output_file))
