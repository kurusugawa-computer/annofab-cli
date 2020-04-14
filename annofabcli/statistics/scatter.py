import logging
from pathlib import Path
from typing import List

import bokeh
import bokeh.layouts
import bokeh.palettes
import pandas
from annofabapi.models import TaskPhase
from bokeh.models import HoverTool
from bokeh.plotting import ColumnDataSource, figure

logger = logging.getLogger(__name__)


class Scatter:
    """
    散布図を出力するクラス
    """

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

    @staticmethod
    def _create_hover_tool(tool_tip_items: List[str]) -> HoverTool:
        """
        HoverTool用のオブジェクトを生成する。
        """
        detail_tooltips = [(e, "@{%s}" % e) for e in tool_tip_items]
        hover_tool = HoverTool(tooltips=detail_tooltips)
        return hover_tool

    @staticmethod
    def _plot_circle_text(
        fig: bokeh.plotting.Figure, source: ColumnDataSource, x_column_name: str, y_column_name: str,
    ) -> None:
        """
        丸でプロットして、ユーザ名を表示する。

        Args:
            fig:
            source:
            x_column_name: sourceに対応するX軸の列名
            y_column_name: sourceに対応するY軸の列名
            legend_label:
            color: 線と点の色

        """
        fig.circle(
            x=x_column_name, y=y_column_name, source=source,
        )
        fig.text(x=x_column_name, y=y_column_name, source=source, text="username_", text_font_size="7pt")

    @staticmethod
    def _get_phase_list(df: pandas.DataFrame) -> List[str]:
        columns = list(df.columns)
        phase_list = [TaskPhase.ANNOTATION.value, TaskPhase.INSPECTION.value, TaskPhase.ACCEPTANCE.value]
        if ("annofab_worktime_hour", TaskPhase.INSPECTION.value) not in columns:
            phase_list.remove(TaskPhase.INSPECTION.value)
        if ("annofab_worktime_hour", TaskPhase.ACCEPTANCE.value) not in columns:
            phase_list.remove(TaskPhase.ACCEPTANCE.value)
        return phase_list

    def write_scatter_for_productivity(self, df: pandas.DataFrame):
        """
        メンバごとに生産性を散布図でプロットする

        Args:
            df:
            first_annotation_user_id_list: 最初のアノテーションを担当したuser_idのList. Noneの場合はtask_dfから決まる。

        Returns:

        """

        def create_figure(title: str) -> bokeh.plotting.Figure:
            return figure(
                plot_width=600,
                plot_height=600,
                title=title,
                x_axis_label="累計作業時間[hour]",
                y_axis_label="アノテーションあたり作業時間[hour/annotation]",
            )

        html_title = "散布図-アノテーションあたり作業時間と累計作業時間の関係"
        output_file = f"{self.scatter_outdir}/{self.short_project_id}-{html_title}.html"
        logger.debug(f"{output_file} を出力します。")

        phase_list = self._get_phase_list(df)

        source = ColumnDataSource(data=df)
        figure_list = [create_figure(f"アノテーションあたり作業時間と累計作業時間の関係（{phase}）") for phase in phase_list]

        for fig, phase in zip(figure_list, phase_list):
            self._plot_circle_text(
                fig=fig,
                source=source,
                x_column_name=f"annofab_worktime_hour_{phase}",
                y_column_name=f"annofab_worktime/annotation_count_{phase}",
            )
            tooltip_item = [
                "username_",
                "biography_",
                f"annofab_worktime_hour_{phase}",
                f"task_count_{phase}",
                f"input_data_count_{phase}",
                f"annotation_count_{phase}",
                f"prediction_annowork_worktime_hour_{phase}",
                f"annofab_worktime/input_data_count_{phase}",
                f"annofab_worktime/annotation_count_{phase}",
            ]

            hover_tool = self._create_hover_tool(tooltip_item)
            fig.add_tools(hover_tool)

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
                plot_width=600, plot_height=600, title=title, x_axis_label=x_axis_label, y_axis_label=y_axis_label,
            )

        html_title = "散布図-教師付者の品質と累計作業時間の関係"
        output_file = f"{self.scatter_outdir}/{self.short_project_id}-{html_title}.html"
        logger.debug(f"{output_file} を出力します。")

        source = ColumnDataSource(data=df)

        figure_list = [
            create_figure(title=f"タスクあたり差し戻し回数と累計作業時間の関係", x_axis_label="累計作業時間[hour]", y_axis_label="タスクあたり差し戻し回数"),
            create_figure(
                title=f"アノテーションあたり検査コメント数と累計作業時間の関係", x_axis_label="累計作業時間[hour]", y_axis_label="アノテーションあたり検査コメント数"
            ),
        ]

        phase = "annotation"

        self._plot_circle_text(
            fig=figure_list[0],
            source=source,
            x_column_name=f"annofab_worktime_hour_{phase}",
            y_column_name=f"rejected_count/task_count_{phase}",
        )

        self._plot_circle_text(
            fig=figure_list[1],
            source=source,
            x_column_name=f"annofab_worktime_hour_{phase}",
            y_column_name=f"pointed_out_inspection_comment_count/annotation_count_{phase}",
        )

        for fig in figure_list:
            tooltip_item = [
                "username_",
                "biography_",
                f"annofab_worktime_hour_{phase}",
                f"task_count_{phase}",
                f"input_data_count_{phase}",
                f"annotation_count_{phase}",
                f"rejected_count_{phase}" f"pointed_out_inspection_comment_count_{phase}",
                f"rejected_count/task_count_{phase}" f"pointed_out_inspection_comment_count/annotation_count_{phase}",
            ]

            hover_tool = self._create_hover_tool(tooltip_item)
            fig.add_tools(hover_tool)

        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=html_title)
        bokeh.plotting.save(bokeh.layouts.column(figure_list))
