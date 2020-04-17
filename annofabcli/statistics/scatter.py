import logging
from pathlib import Path
from typing import List

import bokeh
import bokeh.layouts
import bokeh.palettes
import pandas
from annofabapi.models import TaskPhase
from bokeh.core.properties import Color
from bokeh.models import HoverTool
from bokeh.plotting import ColumnDataSource, figure

logger = logging.getLogger(__name__)


class Scatter:
    """
    散布図を出力するクラス
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

    def __init__(self, outdir: str, project_id: str):
        self.outdir = outdir
        self.scatter_outdir = f"{outdir}/scatter"
        self.short_project_id = project_id[0:8]
        Path(self.scatter_outdir).mkdir(exist_ok=True, parents=True)

    #
    # @staticmethod
    # def _plot_line_and_circle(
    #     fig: bokeh.plotting.Figure,
    #     source: ColumnDataSource,
    #     x_column_name: str,
    #     y_column_name: str,
    #     legend_label: str,
    #     color: Color,
    # ) -> None:
    #     """
    #     線を引いて、プロットした部分に丸を付ける。
    #
    #     Args:
    #         fig:
    #         source:
    #         x_column_name: sourceに対応するX軸の列名
    #         y_column_name: sourceに対応するY軸の列名
    #         legend_label:
    #         color: 線と点の色
    #
    #     """
    #
    #     fig.line(
    #         x=x_column_name,
    #         y=y_column_name,
    #         source=source,
    #         legend_label=legend_label,
    #         line_color=color,
    #         line_width=1,
    #         muted_alpha=0.2,
    #         muted_color=color,
    #     )
    #     fig.circle(
    #         x=x_column_name,
    #         y=y_column_name,
    #         source=source,
    #         legend_label=legend_label,
    #         muted_alpha=0.0,
    #         muted_color=color,
    #         color=color,
    #     )

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
        color: Color,
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
        print(f"legend_label={legend_label}")
        if legend_label == "":
            print("legend_label is none")
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
    def _get_phase_list(df: pandas.DataFrame) -> List[str]:
        columns = list(df.columns)
        phase_list = [TaskPhase.ANNOTATION.value, TaskPhase.INSPECTION.value, TaskPhase.ACCEPTANCE.value]
        if ("monitored_worktime_hour", TaskPhase.INSPECTION.value) not in columns:
            phase_list.remove(TaskPhase.INSPECTION.value)
        if ("monitored_worktime_hour", TaskPhase.ACCEPTANCE.value) not in columns:
            phase_list.remove(TaskPhase.ACCEPTANCE.value)
        return phase_list

    def write_scatter_for_productivity_by_monitored_worktime(self, df: pandas.DataFrame):
        """
        AnnoFab計測時間を元に算出した生産性を、メンバごとにプロットする

        Args:
            df:
            first_annotation_user_id_list: 最初のアノテーションを担当したuser_idのList. Noneの場合はtask_dfから決まる。

        Returns:

        """

        def create_figure(title: str) -> bokeh.plotting.Figure:
            return figure(
                plot_width=800,
                plot_height=600,
                title=title,
                x_axis_label="累計作業時間[hour]",
                y_axis_label="アノテーションあたり作業時間[hour/annotation]",
            )

        html_title = "散布図-アノテーションあたり作業時間と累計作業時間の関係-計測時間"
        output_file = f"{self.scatter_outdir}/{self.short_project_id}-{html_title}.html"
        logger.debug(f"{output_file} を出力します。")

        phase_list = self._get_phase_list(df)
        figure_list = [
            create_figure(f"{self.dict_phase_name[phase]}のアノテーションあたり作業時間と累計作業時間の関係(計測時間)") for phase in phase_list
        ]

        df["biography"] = df["biography"].fillna("")
        for biography_index, biography in enumerate(df["biography"].unique()):
            print(f"biography={biography}")

            filtered_df = df[df["biography"] == biography]
            source = ColumnDataSource(data=filtered_df)
            for fig, phase in zip(figure_list, phase_list):
                self._scatter(
                    fig=fig,
                    source=source,
                    x_column_name=f"monitored_worktime_hour_{phase}",
                    y_column_name=f"monitored_worktime/annotation_count_{phase}",
                    legend_label=biography,
                    color=self.my_palette[biography_index],
                )

        for fig, phase in zip(figure_list, phase_list):
            tooltip_item = [
                "username_",
                "biography_",
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

        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=html_title)
        bokeh.plotting.save(bokeh.layouts.column(figure_list))

    def write_scatter_for_productivity_by_actual_worktime(self, df: pandas.DataFrame):
        """
        実績作業時間を元に算出した生産性を、メンバごとにプロットする

        Args:
            df:
        Returns:

        """

        def create_figure(title: str) -> bokeh.plotting.Figure:
            return figure(
                plot_width=800,
                plot_height=600,
                title=title,
                x_axis_label="累計作業時間[hour]",
                y_axis_label="アノテーションあたり作業時間[hour/annotation]",
            )

        html_title = "散布図-アノテーションあたり作業時間と累計作業時間の関係-実績時間"
        output_file = f"{self.scatter_outdir}/{self.short_project_id}-{html_title}.html"
        logger.debug(f"{output_file} を出力します。")

        phase_list = self._get_phase_list(df)
        figure_list = [
            create_figure(f"{self.dict_phase_name[phase]}のアノテーションあたり作業時間と累計作業時間の関係(実績時間)") for phase in phase_list
        ]

        df["biography"] = df["biography"].fillna("")
        for biography_index, biography in enumerate(df["biography"].unique()):
            print(f"biography={biography}")

            filtered_df = df[df["biography"] == biography]
            source = ColumnDataSource(data=filtered_df)
            for fig, phase in zip(figure_list, phase_list):
                self._scatter(
                    fig=fig,
                    source=source,
                    x_column_name=f"prediction_actual_worktime_hour_{phase}",
                    y_column_name=f"actual_worktime/annotation_count_{phase}",
                    legend_label=biography,
                    color=self.my_palette[biography_index],
                )

        for fig, phase in zip(figure_list, phase_list):
            tooltip_item = [
                "username_",
                "biography_",
                f"prediction_actual_worktime_hour_{phase}",
                f"task_count_{phase}",
                f"input_data_count_{phase}",
                f"annotation_count_{phase}",
                f"monitored_worktime_hour_{phase}",
                f"prediction_actual_worktime/input_data_count_{phase}",
                f"prediction_actual_worktime/annotation_count_{phase}",
            ]
            hover_tool = self._create_hover_tool(tooltip_item)
            fig.add_tools(hover_tool)
            self._set_legend(fig)

        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=html_title)
        bokeh.plotting.save(bokeh.layouts.column(figure_list))

    def write_scatter_for_quality(self, df: pandas.DataFrame):
        """
        メンバごとに品質を散布図でプロットする

        Args:
            df:
        Returns:

        """

        def create_figure(title: str, x_axis_label: str, y_axis_label: str) -> bokeh.plotting.Figure:
            return figure(
                plot_width=800, plot_height=600, title=title, x_axis_label=x_axis_label, y_axis_label=y_axis_label,
            )

        html_title = "散布図-教師付者の品質と作業量の関係"
        output_file = f"{self.scatter_outdir}/{self.short_project_id}-{html_title}.html"
        logger.debug(f"{output_file} を出力します。")

        figure_list = [
            create_figure(title=f"タスクあたり差し戻し回数とタスク数の関係", x_axis_label="タスク数", y_axis_label="タスクあたり差し戻し回数"),
            create_figure(
                title=f"アノテーションあたり検査コメント数とアノテーション数の関係", x_axis_label="アノテーション数", y_axis_label="アノテーションあたり検査コメント数"
            ),
        ]

        phase = "annotation"

        df["biography"] = df["biography"].fillna("")
        for biography_index, biography in enumerate(df["biography"].unique()):
            filtered_df = df[df["biography"] == biography]
            source = ColumnDataSource(data=filtered_df)

            self._scatter(
                fig=figure_list[0],
                source=source,
                x_column_name=f"task_count_{phase}",
                y_column_name=f"rejected_count/task_count_{phase}",
                legend_label=biography,
                color=self.my_palette[biography_index],
            )

            self._scatter(
                fig=figure_list[1],
                source=source,
                x_column_name=f"annotation_count_{phase}",
                y_column_name=f"pointed_out_inspection_comment_count/annotation_count_{phase}",
                legend_label=biography,
                color=self.my_palette[biography_index],
            )

        for fig in figure_list:
            tooltip_item = [
                "username_",
                "biography_",
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

        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=html_title)
        bokeh.plotting.save(bokeh.layouts.column(figure_list))
