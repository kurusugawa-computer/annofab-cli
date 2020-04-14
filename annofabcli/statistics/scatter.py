import logging
from pathlib import Path
from typing import Dict, List, Optional

import bokeh
import bokeh.layouts
import bokeh.palettes
import dateutil
import pandas as pd
from bokeh.core.properties import Color
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
        self.scatter_outdir = f"{outdir}/line-graph"
        self.short_project_id = project_id[0:8]
        Path(self.scatter_outdir).mkdir(exist_ok=True, parents=True)

    @staticmethod
    def _create_hover_tool(tool_tip_items: Optional[List[str]] = None) -> HoverTool:
        """
        HoverTool用のオブジェクトを生成する。
        Returns:

        """
        if tool_tip_items is None:
            tool_tip_items = []

        detail_tooltips = [(e, "@{%s}" % e) for e in tool_tip_items]

        hover_tool = HoverTool(tooltips=[("index", "$index"), ("(x,y)", "($x, $y)")] + detail_tooltips)
        return hover_tool

    @staticmethod
    def _plot_line_and_circle(
        fig: bokeh.plotting.Figure,
        source: ColumnDataSource,
        x_column_name: str,
        y_column_name: str,
        legend_label: str,
        color: Color,
    ) -> None:
        """
        線を引いて、プロットした部分に丸を付ける。

        Args:
            fig:
            source:
            x_column_name: sourceに対応するX軸の列名
            y_column_name: sourceに対応するY軸の列名
            legend_label:
            color: 線と点の色

        """
        fig.line(
            x=x_column_name,
            y=y_column_name,
            source=source,
            legend_label=legend_label,
            line_color=color,
            line_width=1,
            muted_alpha=0.2,
            muted_color=color,
        )
        fig.circle(
            x=x_column_name,
            y=y_column_name,
            source=source,
            legend_label=legend_label,
            muted_alpha=0.0,
            muted_color=color,
            color=color,
        )

    @staticmethod
    def _set_legend(fig: bokeh.plotting.Figure, hover_tool: HoverTool) -> None:
        """
        凡例の設定。

        Args:
            fig:
            hover_tool:
        """
        fig.add_tools(hover_tool)
        fig.legend.location = "top_left"
        fig.legend.click_policy = "mute"
        if len(fig.legend) > 0:
            legend = fig.legend[0]
            fig.add_layout(legend, "left")


    def write_scatter_for_productivity(
        self, df: pd.DataFrame
    ):
        """
        メンバごとに生産性を散布図でプロットする

        Args:
            df:
            first_annotation_user_id_list: 最初のアノテーションを担当したuser_idのList. Noneの場合はtask_dfから決まる。

        Returns:

        """

        html_title = "アノテーションあたり作業時間と作業時間の関係（教師付）"
        output_file = f"{self.scatter_outdir}/{self.short_project_id}-{html_title}.html"
        logger.debug(f"{output_file} を出力します。")

        source = ColumnDataSource(data=df)
        fig = figure(
            plot_width=1200,
            plot_height=600,
            title=html_title,
            x_axis_label="annofab_worktime/annotation_count[hour/annotation]",
            y_axis_label="annofab_worktime",
        )

        fig.circle(
            x=("annofab_worktime_hour","annotation"),
            y=("annofab_worktime/annotation_count","annotation"),
            source=source,
            # legend_label=legend_label,
            # muted_alpha=0.0,
            # muted_color=color,
            # color=color,
        )

        #
        # for user_index, user_id in enumerate(first_inspection_user_id_list):  # type: ignore
        #     filtered_df = df[df["first_inspection_user_id"] == user_id]
        #     if filtered_df.empty:
        #         logger.debug(f"dataframe is empty. user_id = {user_id}")
        #         continue
        #
        #     color = self.my_palette[user_index]
        #     username = filtered_df.iloc[0]["first_inspection_username"]
        #
        #     for fig, fig_info in zip(figs, fig_info_list):
        #         self._plot_line_and_circle(
        #             fig,
        #             x_column_name=fig_info["x"],
        #             y_column_name=fig_info["y"],
        #             source=source,
        #             legend_label=username,
        #             color=color,
        #         )
        #
        # hover_tool = self._create_hover_tool(tooltip_item)
        # for fig in figs:
        #     self._set_legend(fig, hover_tool)

        figs = [fig]
        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=html_title)
        bokeh.plotting.save(bokeh.layouts.column(figs))


