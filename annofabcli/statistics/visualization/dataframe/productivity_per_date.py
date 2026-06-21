"""
日ごとユーザごとの生産性
"""

from __future__ import annotations

import abc
import logging
from pathlib import Path
from typing import Any

import bokeh.layouts
import pandas
from annofabapi.models import TaskPhase
from bokeh.models import CustomJS
from bokeh.models.renderers.glyph_renderer import GlyphRenderer
from bokeh.models.ui import UIElement
from bokeh.models.widgets.inputs import Select
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
from annofabcli.statistics.visualization.dataframe.task_worktime_by_phase_user import TaskWorktimeByPhaseUser
from annofabcli.statistics.visualization.model import ProductionVolumeColumn

logger = logging.getLogger(__name__)


def create_df_productivity_per_date(task_worktime_by_phase_user: TaskWorktimeByPhaseUser, phase: TaskPhase) -> pandas.DataFrame:
    df = task_worktime_by_phase_user.df.copy()
    str_phase = phase.value
    df = df[df["phase"] == str_phase]
    df = df.rename(columns={"pointed_out_inspection_comment_count": "inspection_comment_count", "worktime_hour": f"{str_phase}_worktime_hour"})

    df[f"first_{str_phase}_started_date"] = df["started_datetime"].map(lambda e: datetime_to_date(e) if e is not None and isinstance(e, str) else None)

    # first_annotation_user_id と first_annotation_usernameの両方を指定している理由：
    # first_annotation_username を取得するため
    # , "first_annotation_username" TODO
    group_obj = df.groupby(
        [f"first_{str_phase}_started_date", "user_id"],
        as_index=False,
    )

    production_volume_columns = [
        "input_data_count",
        "annotation_count",
        *[e.value for e in task_worktime_by_phase_user.custom_production_volume_list],
    ]
    sum_df = group_obj[
        [
            f"{str_phase}_worktime_hour",
            "task_count",
            *production_volume_columns,
            "inspection_comment_count",
        ]
    ].sum(numeric_only=True)

    for denominator_column in production_volume_columns:
        for numerator_column in [f"{str_phase}_worktime_hour", "inspection_comment_count"]:
            sum_df[f"{numerator_column}/{denominator_column}"] = sum_df[numerator_column] / sum_df[denominator_column]

    df_user = df.drop_duplicates(subset=["user_id"])[["user_id", "username", "biography"]]
    sum_df = sum_df.merge(df_user, how="left", on="user_id")
    return sum_df


class AbstractPhaseProductivityPerDate(abc.ABC):
    """ロールごとの日ごとの生産性に関する情報を格納する抽象クラス"""

    PLOT_WIDTH = 1200
    PLOT_HEIGHT = 600

    def __init__(self, df: pandas.DataFrame, phase: TaskPhase, *, custom_production_volume_list: list[ProductionVolumeColumn] | None = None) -> None:
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
        metadata: dict[str, Any] | None,
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
        target_user_id_list: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        raise NotImplementedError()

    def plot_production_volume_metrics_with_selector(
        self,
        output_file: Path,
        *,
        target_user_id_list: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """生産量種別を切り替えられる折れ線グラフを出力します。"""
        raise NotImplementedError()

    def _get_production_volume_list_for_plot(self) -> list[ProductionVolumeColumn]:
        """折れ線グラフで切り替えられる生産量種別を取得します。"""
        return [
            ProductionVolumeColumn("annotation_count", "アノテーション"),
            *self.custom_production_volume_list,
            ProductionVolumeColumn("input_data_count", "入力データ"),
        ]

    def _get_df_sequential_date(self, df: pandas.DataFrame) -> pandas.DataFrame:
        """
        グラフにプロットするために、連続した日付のDataFrameを生成する。

        Args:
            df: １人のユーザーに関する生産量や作業時間が格納されたDataFrame（`user_id`などのユーザー情報はすべて同じ値）

        """
        str_phase = self.phase.value

        # 日付の最小と最大から連続した日付のDataFrameを生成する
        df_date = pandas.DataFrame(
            {
                f"first_{str_phase}_started_date": [
                    str(e.date())
                    for e in pandas.date_range(
                        df[f"first_{str_phase}_started_date"].min(),
                        df[f"first_{str_phase}_started_date"].max(),
                    )
                ]
            }
        )

        df2 = df_date.merge(df, how="left", on=f"first_{str_phase}_started_date")
        df2[f"dt_first_{str_phase}_started_date"] = df2[f"first_{str_phase}_started_date"].map(lambda e: parse(e).date())

        # 欠損値にユーザー情報を追加
        assert len(df) > 0
        for user_column in ["user_id", "username", "biography"]:
            df2[user_column] = df[user_column].iloc[0]

        # その他の欠損値（作業時間や生産量）を0で埋める
        df2 = df2.fillna(
            dict.fromkeys(
                [
                    "annotation_worktime_hour",
                    "inspection_worktime_hour",
                    "acceptance_worktime_hour",
                    "task_count",
                    "inspection_comment_count",
                    *self.production_volume_columns,
                ],
                0,
            )
        )

        return df2

    @property
    def columns(self) -> list[str]:
        str_phase = self.phase.value
        production_columns = [
            f"first_{str_phase}_started_date",
            "user_id",
            "username",
            "biography",
            f"{str_phase}_worktime_hour",
            "task_count",
            *self.production_volume_columns,
        ]

        velocity_columns = [f"{numerator}/{denominator}" for numerator in [f"{str_phase}_worktime_hour"] for denominator in self.production_volume_columns]

        columns = production_columns + velocity_columns

        if self.phase == TaskPhase.ANNOTATION:
            # 教師付作業の品質の指標を追加
            quality_columns = [f"inspection_comment_count/{denominator}" for denominator in self.production_volume_columns]
            columns.extend(["inspection_comment_count", *quality_columns])

        return columns


class AnnotatorProductivityPerDate(AbstractPhaseProductivityPerDate):
    """教師付開始日ごとの教師付者の生産性に関する情報"""

    def __init__(self, df: pandas.DataFrame, *, custom_production_volume_list: list[ProductionVolumeColumn] | None = None) -> None:
        super().__init__(df, phase=TaskPhase.ANNOTATION, custom_production_volume_list=custom_production_volume_list)

    @classmethod
    def from_df_wrapper(cls, task_worktime_by_phase_user: TaskWorktimeByPhaseUser) -> AnnotatorProductivityPerDate:
        df = create_df_productivity_per_date(task_worktime_by_phase_user, TaskPhase.ANNOTATION)
        return cls(df, custom_production_volume_list=task_worktime_by_phase_user.custom_production_volume_list)

    @staticmethod
    def _get_glyph_list(line_graph: LineGraph) -> list[GlyphRenderer]:
        """折れ線グラフのY軸列を切り替える対象のGlyphを取得します。"""
        glyph_list: list[GlyphRenderer] = []
        glyph_list.extend(line_graph.line_glyphs.values())
        glyph_list.extend(line_graph.marker_glyphs.values())
        return glyph_list

    @staticmethod
    def _create_select_for_switching_production_volume(
        *,
        production_volume_list: list[ProductionVolumeColumn],
        dependent_line_graph_list: list[LineGraph],
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

        y_column_by_value = {
            production_volume.value: [
                f"annotation_worktime_minute/{production_volume.value}",
                f"annotation_worktime_minute/{production_volume.value}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}",
                f"inspection_comment_count/{production_volume.value}",
                f"inspection_comment_count/{production_volume.value}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}",
            ]
            for production_volume in production_volume_list
        }
        title_by_value = {
            production_volume.value: [
                f"教師付開始日ごとの{production_volume.name}あたり教師付作業時間",
                f"教師付開始日ごとの{production_volume.name}あたり教師付作業時間(1週間移動平均)",
                f"教師付開始日ごとの{production_volume.name}あたり検査コメント数",
                f"教師付開始日ごとの{production_volume.name}あたり検査コメント数(1週間移動平均)",
            ]
            for production_volume in production_volume_list
        }
        y_axis_label_by_value = {
            production_volume.value: [
                f"{production_volume.name}あたり教師付時間[分/{production_volume.name}]",
                f"{production_volume.name}あたり教師付時間[分/{production_volume.name}]",
                f"{production_volume.name}あたり検査コメント数",
                f"{production_volume.name}あたり検査コメント数",
            ]
            for production_volume in production_volume_list
        }

        select.js_on_change(
            "value",
            CustomJS(
                args={
                    "glyphListByGraphIndex": {str(index): AnnotatorProductivityPerDate._get_glyph_list(line_graph) for index, line_graph in enumerate(dependent_line_graph_list)},
                    "figureList": [line_graph.figure for line_graph in dependent_line_graph_list],
                    "titleByValue": title_by_value,
                    "yAxisLabelByValue": y_axis_label_by_value,
                    "yAxisList": [line_graph.figure.yaxis[0] for line_graph in dependent_line_graph_list],
                    "yColumnByValue": y_column_by_value,
                },
                code="""
                const selectedValue = this.value;

                for (const graphIndex in glyphListByGraphIndex) {
                    const yColumn = yColumnByValue[selectedValue][Number(graphIndex)];
                    for (const glyphRenderer of glyphListByGraphIndex[graphIndex]) {
                        for (const glyph of [glyphRenderer.glyph, glyphRenderer.nonselection_glyph, glyphRenderer.muted_glyph]) {
                            if (glyph == null) {
                                continue;
                            }
                            glyph.y = {field: yColumn};
                            glyph.change.emit();
                        }
                        glyphRenderer.change.emit();
                    }
                }

                figureList.forEach((figure, index) => {
                    figure.title.text = titleByValue[selectedValue][index];
                    yAxisList[index].axis_label = yAxisLabelByValue[selectedValue][index];
                    yAxisList[index].change.emit();
                    figure.y_range.change.emit();
                    figure.change.emit();
                });
                """,
            ),
        )
        return select

    @staticmethod
    def _create_line_graph_list_for_production_volume_selector(
        *,
        default_production_volume: ProductionVolumeColumn,
        tooltip_columns: list[str],
        x_axis_label: str,
    ) -> list[LineGraph]:
        """生産量種別を切り替えられる教師付者用折れ線グラフを生成します。"""
        return [
            LineGraph(
                title="教師付開始日ごとの教師付作業時間",
                y_axis_label="教師付作業時間[時間]",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_axis_type="datetime",
            ),
            LineGraph(
                title=f"教師付開始日ごとの{default_production_volume.name}あたり教師付作業時間",
                y_axis_label=f"{default_production_volume.name}あたり教師付時間[分/{default_production_volume.name}]",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_axis_type="datetime",
            ),
            LineGraph(
                title=f"教師付開始日ごとの{default_production_volume.name}あたり教師付作業時間(1週間移動平均)",
                y_axis_label=f"{default_production_volume.name}あたり教師付時間[分/{default_production_volume.name}]",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_axis_type="datetime",
            ),
            LineGraph(
                title=f"教師付開始日ごとの{default_production_volume.name}あたり検査コメント数",
                y_axis_label=f"{default_production_volume.name}あたり検査コメント数",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_axis_type="datetime",
            ),
            LineGraph(
                title=f"教師付開始日ごとの{default_production_volume.name}あたり検査コメント数(1週間移動平均)",
                y_axis_label=f"{default_production_volume.name}あたり検査コメント数",
                tooltip_columns=tooltip_columns,
                x_axis_label=x_axis_label,
                x_axis_type="datetime",
            ),
        ]

    @staticmethod
    def _add_production_volume_metric_columns(df: pandas.DataFrame, production_volume_list: list[ProductionVolumeColumn]) -> pandas.DataFrame:
        """生産量種別ごとの教師付時間と検査コメント数の列を追加します。"""
        df = df.copy()
        for production_volume in production_volume_list:
            production_volume_column = production_volume.value
            df[f"annotation_worktime_minute/{production_volume_column}"] = df["annotation_worktime_hour"] * 60 / df[production_volume_column]
            df[f"annotation_worktime_minute/{production_volume_column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = (
                get_weekly_sum(df["annotation_worktime_hour"]) * 60 / get_weekly_sum(df[production_volume_column])
            )
            df[f"inspection_comment_count/{production_volume_column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = get_weekly_sum(df["inspection_comment_count"]) / get_weekly_sum(
                df[production_volume_column]
            )
        return df

    @staticmethod
    def _add_lines_to_production_volume_selector_graphs(
        *,
        line_graph_list: list[LineGraph],
        source: ColumnDataSource,
        default_production_volume: ProductionVolumeColumn,
        username: str,
        color: str,
    ) -> None:
        """生産量種別セレクタ付きグラフに1ユーザー分の折れ線を追加します。"""
        x_column = "dt_first_annotation_started_date"
        columns_list = [
            (x_column, "annotation_worktime_hour"),
            (x_column, f"annotation_worktime_minute/{default_production_volume.value}"),
            (x_column, f"annotation_worktime_minute/{default_production_volume.value}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"),
            (x_column, f"inspection_comment_count/{default_production_volume.value}"),
            (x_column, f"inspection_comment_count/{default_production_volume.value}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"),
        ]

        for line_graph, (line_x_column, y_column) in zip(line_graph_list, columns_list, strict=False):
            if y_column.endswith(WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX):
                line_graph.add_moving_average_line(
                    source=source,
                    x_column=line_x_column,
                    y_column=y_column,
                    legend_label=username,
                    color=color,
                )
            else:
                line_graph.add_line(
                    source=source,
                    x_column=line_x_column,
                    y_column=y_column,
                    legend_label=username,
                    color=color,
                )

    def _create_layout_for_production_volume_selector_graphs(
        self,
        *,
        line_graph_list: list[LineGraph],
        plotted_users: list[tuple[str, str]],
        production_volume_list: list[ProductionVolumeColumn],
        metadata: dict[str, Any] | None,
    ) -> bokeh.layouts.LayoutDOM:
        """生産量種別セレクタ付きグラフのレイアウトを生成します。"""
        graph_group_list: list[UIElement] = [
            self._create_select_for_switching_production_volume(
                production_volume_list=production_volume_list,
                dependent_line_graph_list=line_graph_list[1:],
            )
        ]
        for line_graph in line_graph_list:
            line_graph.process_after_adding_glyphs()

            widget_list: list[Widget] = []
            hide_all_button = line_graph.create_button_hiding_showing_all_lines(is_hiding=True)
            show_all_button = line_graph.create_button_hiding_showing_all_lines(is_hiding=False)
            widget_list.extend([hide_all_button, show_all_button])

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

        return bokeh.layouts.layout(graph_group_list)

    def plot_production_volume_metrics_with_selector(
        self,
        output_file: Path,
        *,
        target_user_id_list: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """生産量種別を切り替えられる教師付者用の生産性折れ線グラフを出力します。"""
        if not self._validate_df_for_output(output_file):
            return

        df = self.df.copy()

        if target_user_id_list is not None:
            user_id_list = target_user_id_list
        else:
            user_id_list = df.sort_values(by="user_id")["user_id"].dropna().unique().tolist()

        user_id_list = get_plotted_user_id_list(user_id_list)
        production_volume_list = self._get_production_volume_list_for_plot()
        default_production_volume = production_volume_list[0]

        x_axis_label = "教師付開始日"
        production_volume_columns = [production_volume.value for production_volume in production_volume_list]
        tooltip_columns = [
            "user_id",
            "username",
            "biography",
            "first_annotation_started_date",
            "annotation_worktime_hour",
            "task_count",
            *production_volume_columns,
            *[f"annotation_worktime_minute/{production_volume.value}" for production_volume in production_volume_list],
            "inspection_comment_count",
            *[f"inspection_comment_count/{production_volume.value}" for production_volume in production_volume_list],
        ]
        line_graph_list = self._create_line_graph_list_for_production_volume_selector(
            default_production_volume=default_production_volume,
            tooltip_columns=tooltip_columns,
            x_axis_label=x_axis_label,
        )

        logger.debug(f"{output_file} を出力します。")

        line_count = 0
        plotted_users: list[tuple[str, str]] = []
        for user_index, user_id in enumerate(user_id_list):
            df_subset = df[df["user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            df_subset = self._get_df_sequential_date(df_subset)
            df_subset = self._add_production_volume_metric_columns(df_subset, production_volume_list)
            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["username"]

            line_count += 1
            self._add_lines_to_production_volume_selector_graphs(
                line_graph_list=line_graph_list,
                source=source,
                default_production_volume=default_production_volume,
                username=username,
                color=color,
            )
            plotted_users.append((user_id, username))

        if line_count == 0:
            logger.warning(f"プロットするデータがなかっため、'{output_file}'は出力しません。")
            return

        layout = self._create_layout_for_production_volume_selector_graphs(
            line_graph_list=line_graph_list,
            plotted_users=plotted_users,
            production_volume_list=production_volume_list,
            metadata=metadata,
        )
        write_bokeh_graph(layout, output_file)

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
            user_id_list = df.sort_values(by="user_id")["user_id"].dropna().unique().tolist()

        user_id_list = get_plotted_user_id_list(user_id_list)

        x_axis_label = "教師付開始日"
        tooltip_columns = [
            "user_id",
            "username",
            "biography",
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
            df_subset = df[df["user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            df_subset = self._get_df_sequential_date(df_subset)
            df_subset[f"annotation_worktime_minute/{production_volume_column}"] = df_subset["annotation_worktime_hour"] * 60 / df_subset[production_volume_column]
            df_subset[f"annotation_worktime_minute/{production_volume_column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = (
                get_weekly_sum(df_subset["annotation_worktime_hour"]) * 60 / get_weekly_sum(df_subset[production_volume_column])
            )
            df_subset[f"inspection_comment_count/{production_volume_column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = get_weekly_sum(df_subset["inspection_comment_count"]) / get_weekly_sum(
                df_subset[production_volume_column]
            )

            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["username"]

            line_count += 1
            for line_graph, (x_column, y_column) in zip(line_graph_list, columns_list, strict=False):
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

        print_csv(self.df[self.columns], output=str(output_file))


class InspectorProductivityPerDate(AbstractPhaseProductivityPerDate):
    """検査開始日ごとの検査者の生産性に関する情報"""

    def __init__(self, df: pandas.DataFrame, *, custom_production_volume_list: list[ProductionVolumeColumn] | None = None) -> None:
        super().__init__(df, phase=TaskPhase.INSPECTION, custom_production_volume_list=custom_production_volume_list)

    @classmethod
    def from_df_wrapper(cls, task_worktime_by_phase_user: TaskWorktimeByPhaseUser) -> InspectorProductivityPerDate:
        df = create_df_productivity_per_date(task_worktime_by_phase_user, TaskPhase.INSPECTION)
        return cls(df, custom_production_volume_list=task_worktime_by_phase_user.custom_production_volume_list)

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
        アノテーション単位の生産性を受入作業者ごとにプロットする。

        """
        if not self._validate_df_for_output(output_file):
            return

        df = self.df.copy()

        if target_user_id_list is not None:
            user_id_list = target_user_id_list
        else:
            user_id_list = df.sort_values(by="user_id", ascending=False)["user_id"].dropna().unique().tolist()

        user_id_list = get_plotted_user_id_list(user_id_list)

        x_axis_label = "検査開始日"
        tooltip_columns = [
            "user_id",
            "username",
            "biography",
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
            df_subset = df[df["user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            df_subset = self._get_df_sequential_date(df_subset)
            df_subset[f"inspection_worktime_minute/{production_volume_column}"] = df_subset["inspection_worktime_hour"] * 60 / df_subset[production_volume_column]
            df_subset[f"inspection_worktime_minute/{production_volume_column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = (
                get_weekly_sum(df_subset["inspection_worktime_hour"]) * 60 / get_weekly_sum(df_subset[production_volume_column])
            )

            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["username"]

            line_count += 1
            for line_graph, (x_column, y_column) in zip(line_graph_list, columns_list, strict=False):
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

        print_csv(self.df[self.columns], output=str(output_file))


class AcceptorProductivityPerDate(AbstractPhaseProductivityPerDate):
    """受入開始日ごとの受入者の生産性に関する情報"""

    def __init__(self, df: pandas.DataFrame, *, custom_production_volume_list: list[ProductionVolumeColumn] | None = None) -> None:
        super().__init__(df, phase=TaskPhase.ACCEPTANCE, custom_production_volume_list=custom_production_volume_list)

    @classmethod
    def from_df_wrapper(cls, task_worktime_by_phase_user: TaskWorktimeByPhaseUser) -> AcceptorProductivityPerDate:
        df = create_df_productivity_per_date(task_worktime_by_phase_user, TaskPhase.ACCEPTANCE)
        return cls(df, custom_production_volume_list=task_worktime_by_phase_user.custom_production_volume_list)

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
        アノテーション単位の生産性を受入作業者ごとにプロットする。

        """

        if not self._validate_df_for_output(output_file):
            return

        df = self.df.copy()

        if target_user_id_list is not None:
            user_id_list = target_user_id_list
        else:
            user_id_list = df.sort_values(by="user_id", ascending=False)["user_id"].dropna().unique().tolist()

        user_id_list = get_plotted_user_id_list(user_id_list)

        x_axis_label = "受入開始日"
        x_column = "dt_first_acceptance_started_date"
        tooltip_columns = [
            "user_id",
            "username",
            "biography",
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
            df_subset = df[df["user_id"] == user_id]
            if df_subset.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            df_subset = self._get_df_sequential_date(df_subset)
            df_subset[f"acceptance_worktime_minute/{production_volume_column}"] = df_subset["acceptance_worktime_hour"] * 60 / df_subset[production_volume_column]

            df_subset[f"acceptance_worktime_minute/{production_volume_column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = (
                get_weekly_sum(df_subset["acceptance_worktime_hour"]) * 60 / get_weekly_sum(df_subset[production_volume_column])
            )

            source = ColumnDataSource(data=df_subset)
            color = get_color_from_palette(user_index)
            username = df_subset.iloc[0]["username"]

            line_count += 1
            for line_graph, (x_column, y_column) in zip(line_graph_list, columns_list, strict=False):
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

        print_csv(self.df[self.columns], output=str(output_file))
