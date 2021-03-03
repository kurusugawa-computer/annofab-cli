import logging
import math
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

import bokeh
import bokeh.layouts
import bokeh.palettes
import numpy
import pandas
from annofabapi.models import TaskPhase
from bokeh.models import HoverTool
from bokeh.plotting import ColumnDataSource, figure

logger = logging.getLogger(__name__)


class Scatter:
    """
    散布図を出力するクラス

    Args:
        outdir: 出力先のディレクトリ
        palette: 散布図を出力するときのカラーパレット。デフォルトは `bokeh.palettes.Category20[20]`

    """

    my_palette = bokeh.palettes.Category20[20]

    dict_phase_name = {
        TaskPhase.ANNOTATION.value: "教師付",
        TaskPhase.INSPECTION.value: "検査",
        TaskPhase.ACCEPTANCE.value: "受入",
    }

    #############################################
    # Field
    #############################################

    #############################################
    # Private
    #############################################

    def __init__(self, outdir: str, palette: Optional[Sequence[str]] = None):
        self.scatter_outdir = outdir
        Path(self.scatter_outdir).mkdir(exist_ok=True, parents=True)
        if palette is not None:
            self.my_palette = palette

    @staticmethod
    def _set_legend(fig: bokeh.plotting.Figure) -> None:
        """
        凡例の設定。
        """
        fig.legend.location = "top_left"
        fig.legend.click_policy = "mute"
        fig.legend.title = "biography"
        if len(fig.legend) > 0:
            legend = fig.legend[0]
            fig.add_layout(legend, "left")

    @staticmethod
    def _create_hover_tool(tool_tip_items: List[str]) -> HoverTool:
        """
        HoverTool用のオブジェクトを生成する。
        """

        def exclude_phase_name(name: str) -> str:
            tmp = name.split("_")
            return "_".join(tmp[0 : len(tmp) - 1])

        detail_tooltips = [(exclude_phase_name(e), "@{%s}" % e) for e in tool_tip_items]
        hover_tool = HoverTool(tooltips=detail_tooltips)
        return hover_tool

    @staticmethod
    def _scatter(
        fig: bokeh.plotting.Figure,
        source: ColumnDataSource,
        x_column_name: str,
        y_column_name: str,
        legend_label: str,
        color: Any,
    ) -> None:
        """
        丸でプロットして、ユーザ名を表示する。

        Args:
            fig:
            source:
            x_column_name: sourceに対応するX軸の列名
            y_column_name: sourceに対応するY軸の列名
            legend_label: 凡例に表示する名前
            color: 線と点の色

        """
        if legend_label == "":
            legend_label = "none"

        fig.circle(
            x=x_column_name, y=y_column_name, source=source, legend_label=legend_label, color=color, muted_alpha=0.2
        )
        fig.text(
            x=x_column_name,
            y=y_column_name,
            source=source,
            text="username_",
            text_font_size="7pt",
            legend_label=legend_label,
            muted_alpha=0.2,
        )

    @staticmethod
    def _plot_bubble(
        fig: bokeh.plotting.Figure,
        source: ColumnDataSource,
        x_column_name: str,
        y_column_name: str,
        size_column_name: str,
        legend_label: str,
        color: Any,
    ) -> None:
        """
        バブルチャート用にプロットする。

        Args:
            fig:
            source:
            x_column_name: sourceに対応するX軸の列名
            y_column_name: sourceに対応するY軸の列名
            legend_label: 凡例に表示する名前
            color: 線と点の色

        """

        def _worktime_hour_to_scatter_size(worktime_hour: float) -> int:
            """
            作業時間からバブルの大きさに変更する。
            """
            MIN_SCATTER_SIZE = 4
            if worktime_hour <= 0:
                return MIN_SCATTER_SIZE
            tmp = int(math.log2(worktime_hour) * 15 - 50)
            if tmp < MIN_SCATTER_SIZE:
                return MIN_SCATTER_SIZE
            else:
                return tmp

        if legend_label == "":
            legend_label = "none"

        tmp_size_field = f"__size__{size_column_name}"
        source.data[tmp_size_field] = numpy.array(
            list(map(_worktime_hour_to_scatter_size, source.data[size_column_name]))
        )
        fig.scatter(
            x=x_column_name,
            y=y_column_name,
            source=source,
            legend_label=legend_label,
            color=color,
            fill_alpha=0.5,
            muted_alpha=0.2,
            size=tmp_size_field,
        )
        fig.text(
            x=x_column_name,
            y=y_column_name,
            source=source,
            text="username_",
            text_align="center",
            text_baseline="middle",
            text_font_size="7pt",
            legend_label=legend_label,
            muted_alpha=0.2,
        )

    @staticmethod
    def _get_phase_list(df: pandas.DataFrame) -> List[str]:
        columns = list(df.columns)
        phase_list = [TaskPhase.ANNOTATION.value, TaskPhase.INSPECTION.value, TaskPhase.ACCEPTANCE.value]
        if ("monitored_worktime_hour", TaskPhase.INSPECTION.value) not in columns:
            phase_list.remove(TaskPhase.INSPECTION.value)
        if ("monitored_worktime_hour", TaskPhase.ACCEPTANCE.value) not in columns:
            phase_list.remove(TaskPhase.ACCEPTANCE.value)
        return phase_list

    @staticmethod
    def _plot_average_line(fig: bokeh.plotting.Figure, value: Optional[float], dimension: str):
        if value is None:
            return
        span_average_line = bokeh.models.Span(
            location=value,
            dimension=dimension,
            line_color="red",
            line_width=0.5,
        )
        fig.add_layout(span_average_line)

    @staticmethod
    def _plot_quartile_line(fig: bokeh.plotting.Figure, quartile: Optional[Tuple[float, float, float]], dimension: str):
        if quartile is None:
            return

        for value in quartile:
            span_average_line = bokeh.models.Span(
                location=value,
                dimension=dimension,
                line_color="blue",
                line_width=0.5,
            )
            fig.add_layout(span_average_line)

    @staticmethod
    def _get_average_value(df: pandas.DataFrame, numerator_column: Any, denominator_column: Any) -> Optional[float]:
        numerator = df[numerator_column].sum()
        denominator = df[denominator_column].sum()
        if denominator > 0:
            return numerator / denominator
        else:
            return None

    @staticmethod
    def _get_quartile_value(df: pandas.DataFrame, column: Any) -> Optional[Tuple[float, float, float]]:
        tmp = df[column].describe()
        if tmp["count"] > 3:
            return (tmp["25%"], tmp["50%"], tmp["75%"])
        else:
            return None

    @staticmethod
    def _create_div_element() -> bokeh.models.Div:
        """
        HTMLページの先頭に付与するdiv要素を生成する。
        """
        return bokeh.models.Div(
            text="""<h4>グラフの見方</h4>
            <span style="color:red;">赤線</span>：平均値<br>
            <span style="color:blue;">青線</span>：四分位数<br>
            """
        )

    def write_scatter_for_productivity_by_monitored_worktime(self, df: pandas.DataFrame):
        """
        AnnoFab計測時間を元に算出した生産性を、メンバごとにプロットする

        Args:
            df:
            first_annotation_user_id_list: 最初のアノテーションを担当したuser_idのList. Noneの場合はtask_dfから決まる。

        Returns:

        """
        # numpy.inf が含まれていると散布図を出力できないので置換する
        df = df.replace(numpy.inf, numpy.nan)

        def create_figure(title: str) -> bokeh.plotting.Figure:
            return figure(
                plot_width=1200,
                plot_height=800,
                title=title,
                x_axis_label="累計作業時間[hour]",
                y_axis_label="アノテーションあたり作業時間[hour/annotation]",
            )

        html_title = "散布図-アノテーションあたり作業時間と累計作業時間の関係-計測時間"
        output_file = f"{self.scatter_outdir}/{html_title}.html"
        logger.debug(f"{output_file} を出力します。")

        phase_list = self._get_phase_list(df)
        figure_list = [
            create_figure(f"{self.dict_phase_name[phase]}のアノテーションあたり作業時間と累計作業時間の関係(計測時間)") for phase in phase_list
        ]

        df["biography"] = df["biography"].fillna("")

        for biography_index, biography in enumerate(sorted(set(df["biography"]))):
            x_column = "monitored_worktime_hour"
            y_column = "monitored_worktime/annotation_count"
            for fig, phase in zip(figure_list, phase_list):
                filtered_df = df[
                    (df["biography"] == biography) & df[(x_column, phase)].notna() & df[(y_column, phase)].notna()
                ]
                if len(filtered_df) == 0:
                    continue
                source = ColumnDataSource(data=filtered_df)
                self._scatter(
                    fig=fig,
                    source=source,
                    x_column_name=f"{x_column}_{phase}",
                    y_column_name=f"{y_column}_{phase}",
                    legend_label=biography,
                    color=self.my_palette[biography_index],
                )

        for fig, phase in zip(figure_list, phase_list):
            average_value = self._get_average_value(
                df,
                numerator_column=("monitored_worktime_hour", phase),
                denominator_column=("annotation_count", phase),
            )
            self._plot_average_line(fig, average_value, dimension="width")
            quartile = self._get_quartile_value(df, ("monitored_worktime/annotation_count", phase))
            self._plot_quartile_line(fig, quartile, dimension="width")

        for fig, phase in zip(figure_list, phase_list):
            tooltip_item = [
                "user_id_",
                "username_",
                "biography_",
                "last_working_date_",
                f"monitored_worktime_hour_{phase}",
                f"task_count_{phase}",
                f"input_data_count_{phase}",
                f"annotation_count_{phase}",
                f"prediction_actual_worktime_hour_{phase}",
                f"monitored_worktime/input_data_count_{phase}",
                f"monitored_worktime/annotation_count_{phase}",
            ]
            hover_tool = self._create_hover_tool(tooltip_item)
            fig.add_tools(hover_tool)
            self._set_legend(fig)

        div_element = self._create_div_element()
        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=html_title)
        bokeh.plotting.save(bokeh.layouts.column([div_element] + figure_list))

    def write_scatter_for_productivity_by_actual_worktime(self, df: pandas.DataFrame):
        """
        実績作業時間を元に算出した生産性を、メンバごとにプロットする

        Args:
            df:
        Returns:

        """
        # numpy.inf が含まれていると散布図を出力できないので置換する
        df = df.replace(numpy.inf, numpy.nan)

        def create_figure(title: str) -> bokeh.plotting.Figure:
            return figure(
                plot_width=1200,
                plot_height=800,
                title=title,
                x_axis_label="累計作業時間[hour]",
                y_axis_label="アノテーションあたり作業時間[hour/annotation]",
            )

        html_title = "散布図-アノテーションあたり作業時間と累計作業時間の関係-実績時間"
        output_file = f"{self.scatter_outdir}/{html_title}.html"
        logger.debug(f"{output_file} を出力します。")

        phase_list = self._get_phase_list(df)
        figure_list = [
            create_figure(f"{self.dict_phase_name[phase]}のアノテーションあたり作業時間と累計作業時間の関係(実績時間)") for phase in phase_list
        ]

        df["biography"] = df["biography"].fillna("")
        for biography_index, biography in enumerate(sorted(set(df["biography"]))):
            x_column = "prediction_actual_worktime_hour"
            y_column = "actual_worktime/annotation_count"
            for fig, phase in zip(figure_list, phase_list):
                filtered_df = df[
                    (df["biography"] == biography) & df[(x_column, phase)].notna() & df[(y_column, phase)].notna()
                ]
                if len(filtered_df) == 0:
                    continue
                source = ColumnDataSource(data=filtered_df)
                self._scatter(
                    fig=fig,
                    source=source,
                    x_column_name=f"{x_column}_{phase}",
                    y_column_name=f"{y_column}_{phase}",
                    legend_label=biography,
                    color=self.my_palette[biography_index],
                )

        for fig, phase in zip(figure_list, phase_list):
            average_value = self._get_average_value(
                df,
                numerator_column=("prediction_actual_worktime_hour", phase),
                denominator_column=("annotation_count", phase),
            )
            self._plot_average_line(fig, average_value, dimension="width")

            quartile = self._get_quartile_value(df, ("actual_worktime/annotation_count", phase))
            self._plot_quartile_line(fig, quartile, dimension="width")

        for fig, phase in zip(figure_list, phase_list):
            tooltip_item = [
                "user_id_",
                "username_",
                "biography_",
                "last_working_date_",
                f"prediction_actual_worktime_hour_{phase}",
                f"task_count_{phase}",
                f"input_data_count_{phase}",
                f"annotation_count_{phase}",
                f"monitored_worktime_hour_{phase}",
                f"actual_worktime/input_data_count_{phase}",
                f"actual_worktime/annotation_count_{phase}",
            ]
            hover_tool = self._create_hover_tool(tooltip_item)
            fig.add_tools(hover_tool)
            self._set_legend(fig)

        div_element = self._create_div_element()
        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=html_title)
        bokeh.plotting.save(bokeh.layouts.column([div_element] + figure_list))

    def write_scatter_for_quality(self, df: pandas.DataFrame):
        """
        メンバごとに品質を散布図でプロットする

        Args:
            df:
        Returns:

        """
        # numpy.inf が含まれていると散布図を出力できないので置換する
        df = df.replace(numpy.inf, numpy.nan)

        def create_figure(title: str, x_axis_label: str, y_axis_label: str) -> bokeh.plotting.Figure:
            return figure(
                plot_width=1200,
                plot_height=800,
                title=title,
                x_axis_label=x_axis_label,
                y_axis_label=y_axis_label,
            )

        html_title = "散布図-教師付者の品質と作業量の関係"
        output_file = f"{self.scatter_outdir}/{html_title}.html"
        logger.debug(f"{output_file} を出力します。")

        figure_list = [
            create_figure(title=f"タスクあたり差し戻し回数とタスク数の関係", x_axis_label="タスク数", y_axis_label="タスクあたり差し戻し回数"),
            create_figure(
                title=f"アノテーションあたり検査コメント数とアノテーション数の関係", x_axis_label="アノテーション数", y_axis_label="アノテーションあたり検査コメント数"
            ),
        ]
        column_pair_list = [
            ("task_count", "rejected_count/task_count"),
            ("annotation_count", "pointed_out_inspection_comment_count/annotation_count"),
        ]

        phase = "annotation"

        df["biography"] = df["biography"].fillna("")
        for biography_index, biography in enumerate(sorted(set(df["biography"]))):
            for column_pair, fig in zip(column_pair_list, figure_list):
                x_column = column_pair[0]
                y_column = column_pair[1]
                filtered_df = df[
                    (df["biography"] == biography) & df[(x_column, phase)].notna() & df[(y_column, phase)].notna()
                ]
                if len(filtered_df) == 0:
                    continue

                source = ColumnDataSource(data=filtered_df)
                self._scatter(
                    fig=fig,
                    source=source,
                    x_column_name=f"{x_column}_{phase}",
                    y_column_name=f"{y_column}_{phase}",
                    legend_label=biography,
                    color=self.my_palette[biography_index],
                )

        for column_pair, fig in zip(
            [("rejected_count", "task_count"), ("pointed_out_inspection_comment_count", "annotation_count")],
            figure_list,
        ):
            average_value = self._get_average_value(
                df, numerator_column=(column_pair[0], phase), denominator_column=(column_pair[1], phase)
            )
            self._plot_average_line(fig, average_value, dimension="width")

        for column, fig in zip(
            ["rejected_count/task_count", "pointed_out_inspection_comment_count/annotation_count"],
            figure_list,
        ):
            quartile = self._get_quartile_value(df, (column, phase))
            self._plot_quartile_line(fig, quartile, dimension="width")

        for fig in figure_list:
            tooltip_item = [
                "user_id_",
                "username_",
                "biography_",
                "last_working_date_",
                f"monitored_worktime_hour_{phase}",
                f"task_count_{phase}",
                f"input_data_count_{phase}",
                f"annotation_count_{phase}",
                f"rejected_count_{phase}",
                f"pointed_out_inspection_comment_count_{phase}",
                f"rejected_count/task_count_{phase}",
                f"pointed_out_inspection_comment_count/annotation_count_{phase}",
            ]

            hover_tool = self._create_hover_tool(tooltip_item)
            fig.add_tools(hover_tool)
            self._set_legend(fig)

        div_element = self._create_div_element()
        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=html_title)
        bokeh.plotting.save(bokeh.layouts.column([div_element] + figure_list))

    def write_scatter_for_productivity_by_actual_worktime_and_quality(self, df: pandas.DataFrame):
        """
        実績作業時間を元に算出した生産性と品質の関係を、メンバごとにプロットする
        """
        # numpy.inf が含まれていると散布図を出力できないので置換する
        df = df.replace(numpy.inf, numpy.nan)

        def create_figure(title: str, x_axis_label: str, y_axis_label: str) -> bokeh.plotting.Figure:
            return figure(
                plot_width=1200,
                plot_height=800,
                title=title,
                x_axis_label=x_axis_label,
                y_axis_label=y_axis_label,
            )

        html_title = "散布図-アノテーションあたり作業時間と品質の関係-実績時間-教師付者用"
        output_file = f"{self.scatter_outdir}/{html_title}.html"
        logger.debug(f"{output_file} を出力します。")

        figure_list = [
            create_figure(
                title=f"アノテーションあたり作業時間とタスクあたり差し戻し回数の関係", x_axis_label="アノテーションあたり作業時間", y_axis_label="タスクあたり差し戻し回数"
            ),
            create_figure(
                title=f"アノテーションあたり作業時間とアノテーションあたり検査コメント数の関係",
                x_axis_label="アノテーションあたり作業時間",
                y_axis_label="アノテーションあたり検査コメント数",
            ),
        ]
        column_pair_list = [
            ("actual_worktime/annotation_count", "rejected_count/task_count"),
            ("actual_worktime/annotation_count", "pointed_out_inspection_comment_count/annotation_count"),
        ]
        phase = TaskPhase.ANNOTATION.value
        df["biography"] = df["biography"].fillna("")
        for biography_index, biography in enumerate(sorted(set(df["biography"]))):
            for fig, column_pair in zip(figure_list, column_pair_list):
                x_column, y_column = column_pair
                filtered_df = df[
                    (df["biography"] == biography) & df[(x_column, phase)].notna() & df[(y_column, phase)].notna()
                ]
                if len(filtered_df) == 0:
                    continue
                source = ColumnDataSource(data=filtered_df)
                self._plot_bubble(
                    fig=fig,
                    source=source,
                    x_column_name=f"{x_column}_{phase}",
                    y_column_name=f"{y_column}_{phase}",
                    size_column_name=f"prediction_actual_worktime_hour_{phase}",
                    legend_label=biography,
                    color=self.my_palette[biography_index],
                )

        x_average_value = self._get_average_value(
            df,
            numerator_column=("prediction_actual_worktime_hour", phase),
            denominator_column=("annotation_count", phase),
        )
        for column_pair, fig in zip(
            [("rejected_count", "task_count"), ("pointed_out_inspection_comment_count", "annotation_count")],
            figure_list,
        ):
            self._plot_average_line(fig, x_average_value, dimension="height")
            y_average_value = self._get_average_value(
                df,
                numerator_column=(column_pair[0], phase),
                denominator_column=(column_pair[1], phase),
            )
            self._plot_average_line(fig, y_average_value, dimension="width")

        x_quartile = self._get_quartile_value(df, ("actual_worktime/annotation_count", phase))
        for column, fig in zip(
            ["rejected_count/task_count", "pointed_out_inspection_comment_count/annotation_count"],
            figure_list,
        ):
            self._plot_quartile_line(fig, x_quartile, dimension="height")
            quartile = self._get_quartile_value(df, (column, phase))
            self._plot_quartile_line(fig, quartile, dimension="width")

        for fig in figure_list:
            tooltip_item = [
                "user_id_",
                "username_",
                "biography_",
                "last_working_date_",
                f"prediction_actual_worktime_hour_{phase}",
                f"task_count_{phase}",
                f"input_data_count_{phase}",
                f"annotation_count_{phase}",
                f"monitored_worktime_hour_{phase}",
                f"actual_worktime/input_data_count_{phase}",
                f"actual_worktime/annotation_count_{phase}",
                f"rejected_count_{phase}",
                f"pointed_out_inspection_comment_count_{phase}",
                f"rejected_count/task_count_{phase}",
                f"pointed_out_inspection_comment_count/annotation_count_{phase}",
            ]
            hover_tool = self._create_hover_tool(tooltip_item)
            fig.add_tools(hover_tool)
            self._set_legend(fig)

        div_element = self._create_div_element()
        div_element.text += """円の大きさ：実績作業時間（prediction_actual_worktime_hour）<br>"""
        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=html_title)
        bokeh.plotting.save(bokeh.layouts.column([div_element] + figure_list))
