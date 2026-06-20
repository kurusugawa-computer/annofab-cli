# pylint: disable=too-many-lines
"""
累積の生産性に関する内容
"""

from __future__ import annotations

import abc
import itertools
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import bokeh.layouts
import pandas
from annofabapi.models import TaskPhase
from bokeh.models import CustomJS
from bokeh.models.renderers.glyph_renderer import GlyphRenderer
from bokeh.models.ui import UIElement
from bokeh.models.widgets.inputs import Select
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


@dataclass(frozen=True)
class _CumulativeLineGraphSpec:
    """累積折れ線グラフ1個分の定義。"""

    title_template: str
    y_axis_label: str
    y_column: str
    tooltip_columns: list[str]


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
    return df


class AbstractPhaseCumulativeProductivity(abc.ABC):
    """ロールごとの累積の生産性をプロットするための抽象クラス"""

    def __init__(self, df: pandas.DataFrame, phase: TaskPhase, *, custom_production_volume_list: list[ProductionVolumeColumn] | None = None) -> None:
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

    def _get_production_volume_list_for_plot(self, *, include_input_data_count: bool) -> list[ProductionVolumeColumn]:
        """累積折れ線グラフで切り替えられる生産量種別を取得します。"""
        production_volume_list = [
            ProductionVolumeColumn("annotation_count", "アノテーション数"),
            *self.custom_production_volume_list,
        ]
        if include_input_data_count:
            production_volume_list.append(ProductionVolumeColumn("input_data_count", "入力データ数"))

        return production_volume_list

    def _get_user_id_list_for_plot(self, target_user_id_list: list[str] | None) -> list[str]:
        """累積折れ線グラフにプロットするユーザーIDのリストを取得します。"""
        user_id_list = target_user_id_list if target_user_id_list is not None else self.default_user_id_list
        return get_plotted_user_id_list(user_id_list)

    @staticmethod
    def _create_line_graph_list(
        production_volume_column: str,
        production_volume_name: str,
        graph_spec_list: list[_CumulativeLineGraphSpec],
        *,
        additional_tooltip_columns: list[str] | None = None,
    ) -> tuple[list[LineGraph], list[tuple[str, str]]]:
        """1種類の生産量に対応する折れ線グラフのリストを生成します。"""
        if additional_tooltip_columns is None:
            additional_tooltip_columns = [production_volume_column]

        line_graph_list = [
            LineGraph(
                title=graph_spec.title_template.format(production_volume_name=production_volume_name),
                y_axis_label=graph_spec.y_axis_label,
                tooltip_columns=[*graph_spec.tooltip_columns, *additional_tooltip_columns],
                x_axis_label=production_volume_name,
            )
            for graph_spec in graph_spec_list
        ]

        x_column = f"cumulative_{production_volume_column}"
        columns_list = [(x_column, graph_spec.y_column) for graph_spec in graph_spec_list]
        return line_graph_list, columns_list

    @staticmethod
    def _get_glyph_list(line_graph_list: list[LineGraph]) -> list[GlyphRenderer]:
        """折れ線グラフのX軸列を切り替える対象のGlyphを取得します。"""
        glyph_list: list[GlyphRenderer] = []
        for line_graph in line_graph_list:
            glyph_list.extend(line_graph.line_glyphs.values())
            glyph_list.extend(line_graph.marker_glyphs.values())

        return glyph_list

    @staticmethod
    def _create_select_for_switching_production_volume(
        *,
        production_volume_list: list[ProductionVolumeColumn],
        line_graph_list: list[LineGraph],
    ) -> Select:
        """生産量種別を切り替えるためのSelectを生成します。"""
        default_production_volume = production_volume_list[0]
        options: list[str | tuple[Any, str]] = [(production_volume.value, production_volume.name) for production_volume in production_volume_list]
        select = Select(
            title="生産量種別:",
            value=default_production_volume.value,
            options=options,
            width=300,
        )

        title_by_value = {
            production_volume.value: [line_graph.title.replace(default_production_volume.name, production_volume.name) for line_graph in line_graph_list]
            for production_volume in production_volume_list
        }
        x_axis_label_by_value = {production_volume.value: production_volume.name for production_volume in production_volume_list}
        x_column_by_value = {production_volume.value: f"cumulative_{production_volume.value}" for production_volume in production_volume_list}

        select.js_on_change(
            "value",
            CustomJS(
                args={
                    "glyphList": AbstractPhaseCumulativeProductivity._get_glyph_list(line_graph_list),
                    "figureList": [line_graph.figure for line_graph in line_graph_list],
                    "titleByValue": title_by_value,
                    "xAxisLabelByValue": x_axis_label_by_value,
                    "xColumnByValue": x_column_by_value,
                },
                code="""
                const selectedValue = this.value;
                const xColumn = xColumnByValue[selectedValue];

                for (const glyphRenderer of glyphList) {
                    for (const glyph of [glyphRenderer.glyph, glyphRenderer.nonselection_glyph, glyphRenderer.muted_glyph]) {
                        if (glyph == null) {
                            continue;
                        }
                        glyph.x = {field: xColumn};
                        glyph.change.emit();
                    }
                    glyphRenderer.change.emit();
                }

                figureList.forEach((figure, index) => {
                    figure.title.text = titleByValue[selectedValue][index];
                    figure.xaxis[0].axis_label = xAxisLabelByValue[selectedValue];
                    figure.x_range.change.emit();
                    figure.change.emit();
                });
                """,
            ),
        )
        return select

    def _plot(
        self,
        line_graph_list: list[LineGraph],
        columns_list: list[tuple[str, str]],
        user_id_list: list[str],
        output_file: Path,
        *,
        metadata: dict[str, Any] | None,
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
            for line_graph, (x_column, y_column) in zip(line_graph_list, columns_list, strict=False):
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

    def _plot_with_production_volume_selector(
        self,
        graph_spec_list: list[_CumulativeLineGraphSpec],
        production_volume_list: list[ProductionVolumeColumn],
        user_id_list: list[str],
        output_file: Path,
        *,
        metadata: dict[str, Any] | None,
    ) -> None:
        """
        生産量種別を切り替えられる累積折れ線グラフを、HTMLファイルに出力します。

        Args:
            graph_spec_list: 描画する折れ線グラフの定義リスト。
            production_volume_list: 切り替え対象の生産量種別。
            user_id_list: 折れ線グラフに表示するユーザーのIDリスト。
            output_file: 出力先HTMLファイル。
            metadata: HTMLファイルの上部に表示するメタデータです。
        """
        if len(production_volume_list) == 0:
            logger.warning(f"生産量種別が0件のため、'{output_file}'は出力しません。")
            return

        default_production_volume = production_volume_list[0]
        line_graph_list, columns_list = self._create_line_graph_list(
            default_production_volume.value,
            default_production_volume.name,
            graph_spec_list,
            additional_tooltip_columns=[production_volume.value for production_volume in production_volume_list],
        )
        assert len(line_graph_list) == len(columns_list)

        xy_columns = set(itertools.chain.from_iterable(columns for columns in columns_list))
        xy_columns.update(f"cumulative_{production_volume.value}" for production_volume in production_volume_list)
        tooltip_columns = set(itertools.chain.from_iterable(graph_spec.tooltip_columns for graph_spec in graph_spec_list))
        tooltip_columns.update(production_volume.value for production_volume in production_volume_list)
        required_columns = list(xy_columns | tooltip_columns)

        line_count = 0
        plotted_users: list[tuple[str, str]] = []
        for user_index, user_id in enumerate(user_id_list):
            df_subset = self.df[self.df["user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            source = ColumnDataSource(df_subset[required_columns])
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["username"]

            line_count += 1
            for line_graph, (x_column, y_column) in zip(line_graph_list, columns_list, strict=False):
                line_graph.add_line(source, x_column=x_column, y_column=y_column, legend_label=username, color=color)

            plotted_users.append((user_id, username))

        if line_count == 0:
            logger.warning(f"プロットするデータがなかっため、'{output_file}'は出力しません。")
            return

        graph_group_list: list[UIElement] = [
            self._create_select_for_switching_production_volume(
                production_volume_list=production_volume_list,
                line_graph_list=line_graph_list,
            )
        ]
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
        target_user_id_list: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    def _get_graph_spec_list(self) -> list[_CumulativeLineGraphSpec]:
        """累積折れ線グラフの定義リストを取得します。"""
        raise NotImplementedError()

    def plot_production_volume_metrics_with_selector(
        self,
        output_file: Path,
        *,
        target_user_id_list: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        include_input_data_count: bool = True,
    ) -> None:
        """
        生産量種別を切り替えられる累積折れ線グラフを出力します。

        Args:
            output_file: 出力先HTMLファイル。
            target_user_id_list: 折れ線グラフに表示するユーザーのIDリスト。
            metadata: HTMLファイルの上部に表示するメタデータです。
            include_input_data_count: 入力データ数を切り替え対象に含めるかどうか。
        """
        if not self._validate_df_for_output(output_file):
            return

        logger.debug(f"{output_file} を出力します。")
        self._plot_with_production_volume_selector(
            self._get_graph_spec_list(),
            self._get_production_volume_list_for_plot(include_input_data_count=include_input_data_count),
            self._get_user_id_list_for_plot(target_user_id_list),
            output_file,
            metadata=metadata,
        )


class AnnotatorCumulativeProductivity(AbstractPhaseCumulativeProductivity):
    def __init__(self, df: pandas.DataFrame, *, custom_production_volume_list: list[ProductionVolumeColumn] | None = None) -> None:
        super().__init__(df, phase=TaskPhase.ANNOTATION, custom_production_volume_list=custom_production_volume_list)

    @classmethod
    def from_df_wrapper(cls, task_worktime_by_phase_user: TaskWorktimeByPhaseUser) -> AnnotatorCumulativeProductivity:
        df = _create_cumulative_dataframe(task_worktime_by_phase_user, TaskPhase.ANNOTATION)
        return cls(df, custom_production_volume_list=task_worktime_by_phase_user.custom_production_volume_list)

    def _get_graph_spec_list(self) -> list[_CumulativeLineGraphSpec]:
        return [
            _CumulativeLineGraphSpec(
                title_template="累積の{production_volume_name}と教師付作業時間",
                y_axis_label="教師付作業時間[時間]",
                y_column="cumulative_annotation_worktime_hour",
                tooltip_columns=[
                    "task_id",
                    "user_id",
                    "username",
                    "biography",
                    "first_annotation_started_date",
                    "task_count",
                    "annotation_worktime_hour",
                ],
            ),
            _CumulativeLineGraphSpec(
                title_template="累積の{production_volume_name}と検査コメント数",
                y_axis_label="検査コメント数",
                y_column="cumulative_inspection_comment_count",
                tooltip_columns=[
                    "task_id",
                    "user_id",
                    "username",
                    "biography",
                    "first_annotation_started_date",
                    "task_count",
                    "inspection_comment_count",
                ],
            ),
        ]

    def plot_production_volume_metrics(
        self,
        production_volume_column: str,
        production_volume_name: str,
        output_file: Path,
        *,
        target_user_id_list: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
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

        line_graph_list, columns_list = self._create_line_graph_list(production_volume_column, production_volume_name, self._get_graph_spec_list())
        self._plot(line_graph_list, columns_list, user_id_list, output_file, metadata=metadata)


class InspectorCumulativeProductivity(AbstractPhaseCumulativeProductivity):
    def __init__(self, df: pandas.DataFrame, *, custom_production_volume_list: list[ProductionVolumeColumn] | None = None) -> None:
        super().__init__(df, phase=TaskPhase.INSPECTION, custom_production_volume_list=custom_production_volume_list)

    @classmethod
    def from_df_wrapper(cls, task_worktime_by_phase_user: TaskWorktimeByPhaseUser) -> InspectorCumulativeProductivity:
        df = _create_cumulative_dataframe(task_worktime_by_phase_user, TaskPhase.INSPECTION)
        return cls(df, custom_production_volume_list=task_worktime_by_phase_user.custom_production_volume_list)

    def _get_graph_spec_list(self) -> list[_CumulativeLineGraphSpec]:
        return [
            _CumulativeLineGraphSpec(
                title_template="累積の{production_volume_name}と検査作業時間",
                y_axis_label="検査作業時間[時間]",
                y_column="cumulative_inspection_worktime_hour",
                tooltip_columns=[
                    "task_id",
                    "user_id",
                    "username",
                    "biography",
                    "first_inspection_started_date",
                    "task_count",
                    "inspection_worktime_hour",
                    "annotation_count",
                ],
            ),
        ]

    def plot_production_volume_metrics(
        self,
        production_volume_column: str,
        production_volume_name: str,
        output_file: Path,
        *,
        target_user_id_list: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
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

        line_graph_list, columns_list = self._create_line_graph_list(production_volume_column, production_volume_name, self._get_graph_spec_list())

        self._plot(line_graph_list, columns_list, user_id_list, output_file, metadata=metadata)


class AcceptorCumulativeProductivity(AbstractPhaseCumulativeProductivity):
    def __init__(self, df: pandas.DataFrame, *, custom_production_volume_list: list[ProductionVolumeColumn] | None = None) -> None:
        super().__init__(df, phase=TaskPhase.ACCEPTANCE, custom_production_volume_list=custom_production_volume_list)

    @classmethod
    def from_df_wrapper(cls, task_worktime_by_phase_user: TaskWorktimeByPhaseUser) -> AcceptorCumulativeProductivity:
        df = _create_cumulative_dataframe(task_worktime_by_phase_user, TaskPhase.ACCEPTANCE)
        return cls(df, custom_production_volume_list=task_worktime_by_phase_user.custom_production_volume_list)

    def _get_graph_spec_list(self) -> list[_CumulativeLineGraphSpec]:
        return [
            _CumulativeLineGraphSpec(
                title_template="累積の{production_volume_name}と受入作業時間",
                y_axis_label="受入作業時間[時間]",
                y_column="cumulative_acceptance_worktime_hour",
                tooltip_columns=[
                    "task_id",
                    "user_id",
                    "username",
                    "biography",
                    "first_acceptance_started_date",
                    "task_count",
                    "acceptance_worktime_hour",
                ],
            ),
        ]

    def plot_production_volume_metrics(
        self,
        production_volume_column: str,
        production_volume_name: str,
        output_file: Path,
        *,
        target_user_id_list: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
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

        line_graph_list, columns_list = self._create_line_graph_list(production_volume_column, production_volume_name, self._get_graph_spec_list())

        self._plot(line_graph_list, columns_list, user_id_list, output_file, metadata=metadata)
