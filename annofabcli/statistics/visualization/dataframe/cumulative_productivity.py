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
from annofabcli.statistics.visualization.dataframe.task_worktime_by_phase_user import TaskWorktimeByPhaseUser
from annofabcli.statistics.visualization.model import ProductionVolumeColumn

logger = logging.getLogger(__name__)


def _create_cumulative_dataframe(task_worktime_by_phase_user: TaskWorktimeByPhaseUser, phase: TaskPhase) -> pandas.DataFrame:
    """
    累積情報が格納されたDataFrameを生成する。
    """
    df = task_worktime_by_phase_user.df.copy()
    str_phase = phase.value
    df = df[df["phase"] == str_phase]
    df = df.rename(columns={"pointed_out_inspection_comment_count": "inspection_comment_count", "worktime_hour": f"{str_phase}_worktime_hour"})

    # 教師付の開始時刻でソートして、indexを更新する

    df = df.sort_values(["user_id", "started_datetime"]).reset_index(drop=True)

    groupby_obj = df.groupby("user_id")
    df[f"cumulative_{str_phase}_worktime_hour"] = groupby_obj[f"{str_phase}_worktime_hour"].cumsum()

    # 生産量の累積値を算出
    df["cumulative_task_count"] = groupby_obj["task_count"].cumsum()
    df["cumulative_input_data_count"] = groupby_obj["input_data_count"].cumsum()
    df["cumulative_annotation_count"] = groupby_obj["annotation_count"].cumsum()
    for column in [e.value for e in task_worktime_by_phase_user.custom_production_volume_list]:
        df[f"cumulative_{column}"] = groupby_obj[column].cumsum()

    # タスク完了数、差し戻し数など
    df["cumulative_inspection_comment_count"] = groupby_obj["inspection_comment_count"].cumsum()

    # 追加理由：ツールチップでは時間情報は不要なので、作業開始「日」のみ表示するため
    # `YYYY-MM-DDThh:mm:ss.sss+09:00`から`YYYY-MM-DD`を取得する
    # キャストする理由: 全部nanだとfloat型になって、".str"にアクセスできないため
    df[f"first_{str_phase}_started_date"] = df["started_datetime"].astype("string").str[:10]
    # bokeh3.0.3では、string型の列を持つpandas.DataFrameを描画できないため、改めてobject型に戻す
    # TODO この問題が解決されたら、削除する
    # https://qiita.com/yuji38kwmt/items/b5da6ed521e827620186
    df[f"first_{str_phase}_started_date"] = df[f"first_{str_phase}_started_date"].astype("object")
    return df


class AbstractPhaseCumulativeProductivity(abc.ABC):
    """ロールごとの累積の生産性をプロットするための抽象クラス"""

    def __init__(self, df: pandas.DataFrame, phase: TaskPhase, *, custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None) -> None:
        self.df = df
        self.phase = phase
        self.phase_name = self._get_phase_name(phase)
        self.default_user_id_list = self._get_default_user_id_list()
        self.custom_production_volume_list = custom_production_volume_list if custom_production_volume_list is not None else []

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
        """
        プロット対象ユーザーのuser_idのリストを取得します。
        """
        array = self.df["user_id"].dropna().unique()
        return sorted(array)

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False

        if len(self.default_user_id_list) == 0:
            logger.info(f"{self.phase_name}作業したタスクが0件なので（'first_{self.phase.value}_user_id'がすべて空欄）、{output_file} を出力しません。")
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
            tooltip_columns = set(itertools.chain.from_iterable(line_graph.tooltip_columns for line_graph in line_graph_list if line_graph.tooltip_columns is not None))
            return list(xy_columns | tooltip_columns)

        df = self.df
        required_columns = get_required_columns()

        line_count = 0
        plotted_users: list[tuple[str, str]] = []

        for user_index, user_id in enumerate(user_id_list):
            df_subset = df[df["user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            source = ColumnDataSource(df_subset[required_columns])
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["username"]

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
    def from_df_wrapper(cls, task_worktime_by_phase_user: TaskWorktimeByPhaseUser) -> AnnotatorCumulativeProductivity:
        df = _create_cumulative_dataframe(task_worktime_by_phase_user, TaskPhase.ANNOTATION)
        return cls(df, custom_production_volume_list=task_worktime_by_phase_user.custom_production_volume_list)

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

        """

        if not self._validate_df_for_output(output_file):
            return

        logger.debug(f"{output_file} を出力します。")

        if target_user_id_list is not None:
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
                    "user_id",
                    "username",
                    "biography",
                    "first_annotation_started_date",
                    "task_count",
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
                    "user_id",
                    "username",
                    "biography",
                    "first_annotation_started_date",
                    "task_count",
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
    def from_df_wrapper(cls, task_worktime_by_phase_user: TaskWorktimeByPhaseUser) -> InspectorCumulativeProductivity:
        df = _create_cumulative_dataframe(task_worktime_by_phase_user, TaskPhase.INSPECTION)
        return cls(df, custom_production_volume_list=task_worktime_by_phase_user.custom_production_volume_list)

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

        """

        if not self._validate_df_for_output(output_file):
            return

        logger.debug(f"{output_file} を出力します。")

        if target_user_id_list is not None:
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
                    "user_id",
                    "username",
                    "biography",
                    "first_inspection_started_date",
                    "task_count",
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
    def from_df_wrapper(cls, task_worktime_by_phase_user: TaskWorktimeByPhaseUser) -> AcceptorCumulativeProductivity:
        df = _create_cumulative_dataframe(task_worktime_by_phase_user, TaskPhase.ACCEPTANCE)
        return cls(df, custom_production_volume_list=task_worktime_by_phase_user.custom_production_volume_list)

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

        """

        if not self._validate_df_for_output(output_file):
            return

        logger.debug(f"{output_file} を出力します。")

        if target_user_id_list is not None:
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
                    "user_id",
                    "username",
                    "biography",
                    "first_acceptance_started_date",
                    "task_count",
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
