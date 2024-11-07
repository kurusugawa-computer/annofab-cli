# pylint: disable=too-many-lines
"""
累積の生産性に関する内容
"""

from __future__ import annotations

import abc
import itertools
import logging
from pathlib import Path
from typing import Any, Optional

import bokeh
import bokeh.layouts
import bokeh.palettes
import pandas
from annofabapi.models import TaskPhase
from bokeh.models.ui import UIElement
from bokeh.plotting import ColumnDataSource

from annofabcli.common.bokeh import create_pretext_from_metadata
from annofabcli.statistics.linegraph import (
    LineGraph,
    get_color_from_palette,
    get_plotted_user_id_list,
    write_bokeh_graph,
)
from annofabcli.statistics.visualization.dataframe.task import Task
from annofabcli.statistics.visualization.model import ProductionVolumeColumn

logger = logging.getLogger(__name__)


class AbstractPhaseCumulativeProductivity(abc.ABC):
    """ロールごとの累積の生産性をプロットするための抽象クラス"""

    def __init__(
        self, df: pandas.DataFrame, phase: TaskPhase, *, custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None
    ) -> None:
        self.df = df
        self.phase = phase
        self.phase_name = self._get_phase_name(phase)
        self.default_user_id_list = self._get_default_user_id_list()
        self.custom_production_volume_list = custom_production_volume_list if custom_production_volume_list is not None else []

        self._df_cumulative = self._get_cumulative_dataframe()

    @staticmethod
    def _get_phase_name(phase: TaskPhase) -> str:
        if phase == TaskPhase.ANNOTATION:
            return "教師付"
        elif phase == TaskPhase.INSPECTION:
            return "検査"
        elif phase == TaskPhase.ACCEPTANCE:
            return "受入"
        raise RuntimeError(f"phase='{phase}'が対象外です。")

    def _get_default_user_id_list(self) -> list[str]:
        return (
            self.df.sort_values(by=f"first_{self.phase.value}_started_datetime", ascending=False)[f"first_{self.phase.value}_user_id"]
            .dropna()
            .unique()
            .tolist()
        )

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False

        if len(self.default_user_id_list) == 0:
            logger.info(
                f"{self.phase_name}作業したタスクが0件なので（'first_{self.phase.value}_user_id'がすべて空欄）、{output_file} を出力しません。"
            )
            return False

        return True

    def _plot(
        self,
        line_graph_list: list[LineGraph],
        columns_list: list[tuple[str, str]],
        user_id_list: list[str],
        output_file: Path,
        *,
        metadata: Optional[dict[str, Any]],
    ) -> None:
        """
        折れ線グラフを、HTMLファイルに出力します。

        Args:
            line_graph_list: 描画する折れ線グラフのlist。
            columns_list: 描画する折れ線グラフのX軸とY軸のキー(tuple)のlist。
        """
        assert len(line_graph_list) == len(columns_list)

        def get_required_columns() -> list[str]:
            """
            HTMLに出力するすべてのグラフから、必要な列名を取得します。

            ColumnDataSourceを生成する際に、必要最小限のデータのみHTMLファイルに出力されるようにするためです。
            そうしないと、不要な情報がHTMLファイルに出力されることにより、ファイルサイズが大きくなってしまいます。
            たとえば、20000件をプロットする際、すべての列を出力すると、そうでないときに比べてファイルサイズが3倍以上になる
            """
            xy_columns = set(itertools.chain.from_iterable(columns for columns in columns_list))
            tooltip_columns = set(
                itertools.chain.from_iterable(line_graph.tooltip_columns for line_graph in line_graph_list if line_graph.tooltip_columns is not None)
            )
            return list(xy_columns | tooltip_columns)

        df = self._df_cumulative

        required_columns = get_required_columns()

        line_count = 0
        plotted_users: list[tuple[str, str]] = []

        for user_index, user_id in enumerate(user_id_list):
            df_subset = df[df[f"first_{self.phase.value}_user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            source = ColumnDataSource(df_subset[required_columns])
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0][f"first_{self.phase.value}_username"]

            line_count += 1
            for line_graph, (x_column, y_column) in zip(line_graph_list, columns_list):
                line_graph.add_line(source, x_column=x_column, y_column=y_column, legend_label=username, color=color)

            plotted_users.append((user_id, username))

        if line_count == 0:
            logger.warning(f"プロットするデータがなかっため、'{output_file}'は出力しません。")
            return

        graph_group_list: list[UIElement] = []
        for line_graph in line_graph_list:
            line_graph.process_after_adding_glyphs()
            hide_all_button = line_graph.create_button_hiding_showing_all_lines(is_hiding=True)
            show_all_button = line_graph.create_button_hiding_showing_all_lines(is_hiding=False)
            checkbox_group = line_graph.create_checkbox_displaying_markers()

            multi_choice_widget = line_graph.create_multi_choice_widget_for_searching_user(plotted_users)

            widgets = bokeh.layouts.column([hide_all_button, show_all_button, checkbox_group, multi_choice_widget])
            graph_group = bokeh.layouts.row([line_graph.figure, widgets])
            graph_group_list.append(graph_group)

        if metadata is not None:
            graph_group_list.insert(0, create_pretext_from_metadata(metadata))

        write_bokeh_graph(bokeh.layouts.layout(graph_group_list), output_file)

    @abc.abstractmethod
    def _get_cumulative_dataframe(self) -> pandas.DataFrame:
        """
        累計情報が格納されたDataFrameを生成します。

         * 指定したフェーズを初めて作業したユーザごと
         * 指定したフェーズを初めて作業した日時順に並べた上で、累計値を算出する

        """
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


class AnnotatorCumulativeProductivity(AbstractPhaseCumulativeProductivity):
    def __init__(self, df: pandas.DataFrame, *, custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None) -> None:
        super().__init__(df, phase=TaskPhase.ANNOTATION, custom_production_volume_list=custom_production_volume_list)

    @classmethod
    def from_task(cls, task: Task) -> AnnotatorCumulativeProductivity:
        """
        `タスクlist.csv`に相当する情報から、インスタンスを生成します。
        """
        return cls(task.df, custom_production_volume_list=task.custom_production_volume_list)

    def _get_cumulative_dataframe(self) -> pandas.DataFrame:
        """
        累積情報が格納されたDataFrameを生成する。
        """
        # 教師付の開始時刻でソートして、indexを更新する
        df = self.df.sort_values(["first_annotation_user_id", "first_annotation_started_datetime"]).reset_index(drop=True)
        # タスクの累計数を取得するために設定する
        df["task_count"] = 1
        # 教師付の作業者でgroupby
        groupby_obj = df.groupby("first_annotation_user_id")

        # 作業時間の累積値
        df["cumulative_annotation_worktime_hour"] = groupby_obj["annotation_worktime_hour"].cumsum()
        df["cumulative_acceptance_worktime_hour"] = groupby_obj["acceptance_worktime_hour"].cumsum()
        df["cumulative_inspection_worktime_hour"] = groupby_obj["inspection_worktime_hour"].cumsum()

        # 生産量
        df["cumulative_task_count"] = groupby_obj["task_count"].cumsum()
        df["cumulative_input_data_count"] = groupby_obj["input_data_count"].cumsum()
        df["cumulative_annotation_count"] = groupby_obj["annotation_count"].cumsum()
        for column in [e.value for e in self.custom_production_volume_list]:
            df[f"cumulative_{column}"] = groupby_obj[column].cumsum()

        # タスク完了数、差し戻し数など
        df["cumulative_inspection_comment_count"] = groupby_obj["inspection_comment_count"].cumsum()
        df["cumulative_number_of_rejections_by_inspection"] = groupby_obj["number_of_rejections_by_inspection"].cumsum()
        df["cumulative_number_of_rejections_by_acceptance"] = groupby_obj["number_of_rejections_by_acceptance"].cumsum()

        # 追加理由：ツールチップでは時間情報は不要なので、作業開始「日」のみ表示するため
        # `YYYY-MM-DDThh:mm:ss.sss+09:00`から`YYYY-MM-DD`を取得する
        # キャストする理由: 全部nanだとfloat型になって、".str"にアクセスできないため
        df["first_annotation_started_date"] = df["first_annotation_started_datetime"].astype("string").str[:10]
        # bokeh3.0.3では、string型の列を持つpandas.DataFrameを描画できないため、改めてobject型に戻す
        # TODO この問題が解決されたら、削除する
        # https://qiita.com/yuji38kwmt/items/b5da6ed521e827620186
        df["first_annotation_started_date"] = df["first_annotation_started_date"].astype("object")

        # 元に戻す
        df = df.drop(["task_count"], axis=1)
        return df

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

        logger.debug(f"{output_file} を出力します。")

        if target_user_id_list is not None:  # noqa: SIM108
            user_id_list = target_user_id_list
        else:
            user_id_list = self.default_user_id_list

        user_id_list = get_plotted_user_id_list(user_id_list)

        line_graph_list = [
            LineGraph(
                title=f"累積の{production_volume_name}と教師付作業時間",
                y_axis_label="教師付作業時間[時間]",
                tooltip_columns=[
                    "task_id",
                    "first_annotation_user_id",
                    "first_annotation_username",
                    "first_annotation_started_date",
                    production_volume_column,
                    "annotation_worktime_hour",
                ],
                x_axis_label=production_volume_name,
            ),
            LineGraph(
                title=f"累積の{production_volume_name}と検査コメント数",
                y_axis_label="検査コメント数",
                tooltip_columns=[
                    "task_id",
                    "first_annotation_user_id",
                    "first_annotation_username",
                    "first_annotation_started_date",
                    production_volume_column,
                    "inspection_comment_count",
                ],
                x_axis_label=production_volume_name,
            ),
        ]

        x_column = f"cumulative_{production_volume_column}"
        columns_list = [
            (x_column, "cumulative_annotation_worktime_hour"),
            (x_column, "cumulative_inspection_comment_count"),
        ]
        self._plot(line_graph_list, columns_list, user_id_list, output_file, metadata=metadata)


class InspectorCumulativeProductivity(AbstractPhaseCumulativeProductivity):
    def __init__(self, df: pandas.DataFrame, *, custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None) -> None:
        super().__init__(df, phase=TaskPhase.INSPECTION, custom_production_volume_list=custom_production_volume_list)

    @classmethod
    def from_task(cls, task: Task) -> InspectorCumulativeProductivity:
        """
        `タスクlist.csv`に相当する情報から、インスタンスを生成します。
        """
        return cls(task.df, custom_production_volume_list=task.custom_production_volume_list)

    def _get_cumulative_dataframe(self) -> pandas.DataFrame:
        """
        最初のアノテーション作業の開始時刻の順にソートして、検査者に関する累計値を算出する
        Args:
            task_df: タスク一覧のDataFrame. 列が追加される
        """
        df = self.df.sort_values(["first_inspection_user_id", "first_inspection_started_datetime"]).reset_index(drop=True)

        # タスクの累計数を取得するために設定する
        df["task_count"] = 1

        groupby_obj = df.groupby("first_inspection_user_id")

        # 作業時間の累積値
        df["cumulative_inspection_worktime_hour"] = groupby_obj["inspection_worktime_hour"].cumsum()

        df["cumulative_inspection_comment_count"] = groupby_obj["inspection_comment_count"].cumsum()

        # 生産量
        df["cumulative_task_count"] = groupby_obj["task_count"].cumsum()
        df["cumulative_input_data_count"] = groupby_obj["input_data_count"].cumsum()
        df["cumulative_annotation_count"] = groupby_obj["annotation_count"].cumsum()
        for column in [e.value for e in self.custom_production_volume_list]:
            df[f"cumulative_{column}"] = groupby_obj[column].cumsum()

        # 追加理由：ツールチップでは時間情報は不要なので、作業開始「日」のみ表示するため
        # `YYYY-MM-DDThh:mm:ss.sss+09:00`から`YYYY-MM-DD`を取得する
        # キャストする理由: 全部nanだとfloat型になって、".str"にアクセスできないため
        df["first_inspection_started_date"] = df["first_inspection_started_datetime"].astype("string").str[:10]

        # bokeh3.0.3では、string型の列を持つpandas.DataFrameを描画できないため、改めてobject型に戻す
        # TODO この問題が解決されたら、削除する
        # https://qiita.com/yuji38kwmt/items/b5da6ed521e827620186
        df["first_inspection_started_date"] = df["first_inspection_started_date"].astype("object")

        # 元に戻す
        df = df.drop(["task_count"], axis=1)

        return df

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
        生産性を検査作業者ごとにプロットする。

        Args:
            df:
            first_inspection_user_id_list:

        Returns:

        """

        if not self._validate_df_for_output(output_file):
            return

        logger.debug(f"{output_file} を出力します。")

        if target_user_id_list is not None:  # noqa: SIM108
            user_id_list = target_user_id_list
        else:
            user_id_list = self.default_user_id_list

        user_id_list = get_plotted_user_id_list(user_id_list)

        line_graph_list = [
            LineGraph(
                title=f"累積の{production_volume_name}と検査作業時間",
                y_axis_label="検査作業時間[時間]",
                tooltip_columns=[
                    "task_id",
                    "first_inspection_user_id",
                    "first_inspection_username",
                    "first_inspection_started_date",
                    production_volume_column,
                    "inspection_worktime_hour",
                    "annotation_count",
                ],
                x_axis_label=production_volume_name,
            ),
        ]

        x_column = f"cumulative_{production_volume_column}"
        columns_list = [
            (x_column, "cumulative_inspection_worktime_hour"),
        ]

        self._plot(line_graph_list, columns_list, user_id_list, output_file, metadata=metadata)


class AcceptorCumulativeProductivity(AbstractPhaseCumulativeProductivity):
    def __init__(self, df: pandas.DataFrame, *, custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None) -> None:
        super().__init__(df, phase=TaskPhase.ACCEPTANCE, custom_production_volume_list=custom_production_volume_list)

    @classmethod
    def from_task(cls, task: Task) -> AcceptorCumulativeProductivity:
        """
        `タスクlist.csv`に相当する情報から、インスタンスを生成します。
        """
        return cls(task.df, custom_production_volume_list=task.custom_production_volume_list)

    def _get_cumulative_dataframe(self) -> pandas.DataFrame:
        """
        最初のアノテーション作業の開始時刻の順にソートして、受入者に関する累計値を算出する
        """
        df = self.df.sort_values(["first_acceptance_user_id", "first_acceptance_started_datetime"]).reset_index(drop=True)
        # タスクの累計数を取得するために設定する
        df["task_count"] = 1

        groupby_obj = df.groupby("first_acceptance_user_id")

        # 作業時間の累積値
        df["cumulative_acceptance_worktime_hour"] = groupby_obj["acceptance_worktime_hour"].cumsum()

        # 生産量
        df["cumulative_task_count"] = groupby_obj["task_count"].cumsum()
        df["cumulative_input_data_count"] = groupby_obj["input_data_count"].cumsum()
        df["cumulative_annotation_count"] = groupby_obj["annotation_count"].cumsum()
        for column in [e.value for e in self.custom_production_volume_list]:
            df[f"cumulative_{column}"] = groupby_obj[column].cumsum()

        # 追加理由：ツールチップでは時間情報は不要なので、作業開始「日」のみ表示するため
        # `YYYY-MM-DDThh:mm:ss.sss+09:00`から`YYYY-MM-DD`を取得する
        # キャストする理由: 全部nanだとfloat型になって、".str"にアクセスできないため
        df["first_acceptance_started_date"] = df["first_acceptance_started_datetime"].astype("string").str[:10]
        # bokeh3.0.3では、string型の列を持つpandas.DataFrameを描画できないため、改めてobject型に戻す
        # TODO この問題が解決されたら、削除する
        # https://qiita.com/yuji38kwmt/items/b5da6ed521e827620186
        df["first_acceptance_started_date"] = df["first_acceptance_started_date"].astype("object")

        # 元に戻す
        df = df.drop(["task_count"], axis=1)

        return df

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
        生産性を受入作業者ごとにプロットする。

        Args:
            df:
            first_acceptance_user_id_list:

        Returns:

        """

        if not self._validate_df_for_output(output_file):
            return

        logger.debug(f"{output_file} を出力します。")

        if target_user_id_list is not None:  # noqa: SIM108
            user_id_list = target_user_id_list
        else:
            user_id_list = self.default_user_id_list

        user_id_list = get_plotted_user_id_list(user_id_list)

        line_graph_list = [
            LineGraph(
                title=f"累積の{production_volume_name}と受入作業時間",
                y_axis_label="受入作業時間[時間]",
                tooltip_columns=[
                    "task_id",
                    "first_acceptance_user_id",
                    "first_acceptance_username",
                    "first_acceptance_started_date",
                    production_volume_column,
                    "acceptance_worktime_hour",
                ],
                x_axis_label=production_volume_name,
            ),
        ]

        x_column = f"cumulative_{production_volume_column}"
        columns_list = [
            (x_column, "cumulative_acceptance_worktime_hour"),
        ]

        self._plot(line_graph_list, columns_list, user_id_list, output_file, metadata=metadata)
