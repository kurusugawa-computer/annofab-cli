import logging
from typing import Any, Dict, List, Optional  # pylint: disable=unused-import

import bokeh
import bokeh.layouts
import bokeh.palettes
import holoviews as hv
import numpy as np
import pandas as pd
from bokeh.models import HoverTool
from bokeh.plotting import ColumnDataSource, figure

from annofabcli.statistics.table import Table

logger = logging.getLogger(__name__)

hv.extension('bokeh')


class Graph:
    """
    グラフを出力するクラス
    """

    #############################################
    # Field
    #############################################
    my_palette = bokeh.palettes.Category20[20]

    #############################################
    # Private
    #############################################

    def __init__(self, table: Table, outdir: str):
        self.table = table
        self.outdir = outdir
        self.short_project_id = table.project_id[0:8]

    @staticmethod
    def _create_hover_tool(tool_tip_items: List[str] = None) -> HoverTool:
        """
        HoverTool用のオブジェクトを生成する。
        Returns:

        """
        if tool_tip_items is None:
            tool_tip_items = []

        detail_tooltips = [(e, "@{%s}" % e) for e in tool_tip_items]

        hover_tool = HoverTool(tooltips=[
            ("index", "$index"),
            ("(x,y)", "($x, $y)"),
        ] + detail_tooltips)
        return hover_tool

    @staticmethod
    def _plot_line_and_circle(fig, x, y, source: ColumnDataSource, username: str, color):
        """
        線を引いて、プロットした部分に丸を付ける。
        Args:
            fig:
            x:
            y:
            source:
            username:
            color:

        Returns:

        """

        fig.line(x=x, y=y, source=source, legend_label=username, line_color=color, line_width=1, muted_alpha=0.2,
                 muted_color=color)
        fig.circle(x=x, y=y, source=source, legend_label=username, muted_alpha=0.0, muted_color=color, color=color)

    @staticmethod
    def _set_legend(fig: bokeh.plotting.Figure, hover_tool: HoverTool):
        """
        凡例の設定。
        Args:
            fig:
            hover_tool:

        Returns:

        """
        fig.add_tools(hover_tool)
        fig.legend.location = "top_left"
        fig.legend.click_policy = "mute"
        if len(fig.legend) > 0:
            legend = fig.legend[0]
            fig.add_layout(legend, "left")

    def write_プロジェクト全体のヒストグラム(self, arg_df: pd.DataFrame = None):
        """
        以下の情報をヒストグラムで出力する。
        作業時間関係、検査コメント数関係、アノテーション数
        Args:
            arg_df: タスク一覧のDataFrame. Noneならば新たに生成する

        """

        df = self.table.create_task_df() if arg_df is None else arg_df
        if len(df) == 0:
            logger.info("タスク一覧が0件のため出力しない")
            return

        renderer = hv.renderer('bokeh')

        columns = [("annotation_count", "アノテーション数", "アノテーション数"), ("sum_worktime_hour", "総作業時間[hour]", "総作業時間"),
                   ("annotation_worktime_hour", "教師付作業時間[hour]", "教師付作業時間"),
                   ("inspection_worktime_hour", "中間検査作業時間[hour]", "中間検査作業時間"),
                   ("acceptance_worktime_hour", "受入作業時間[hour]", "受入作業時間"),
                   ("inspection_count", "検査コメント数", "検査コメント数別タスク数"),
                   ("input_data_count_of_inspection", "指摘を受けた画像枚数", "指摘を受けた画像枚数"), ("input_data_count", "画像枚数", "画像枚数")]

        histograms1 = []
        for col, col_name, title_name in columns:
            mean = round(df[col].mean(), 2)
            std = round(df[col].std(), 2)
            title = f"{title_name}(mean = {mean}, std = {std})"

            data = df[col].values
            bins = 20

            frequencies, edges = np.histogram(data, bins)
            hist = hv.Histogram((edges, frequencies), kdims=col_name, vdims="タスク数", label=title).options(width=500)
            histograms1.append(hist)

        # 軸範囲が同期しないようにする
        layout1 = hv.Layout(histograms1).options(shared_axes=False)
        renderer.save(layout1, f"{self.outdir}/{self.short_project_id}_プロジェクト全体のヒストグラム")

    def wirte_ラベルごとのアノテーション数(self, arg_df: pd.DataFrame = None):
        """
        アノテーションラベルごとの個数を出力
        """
        df = self.table.create_task_for_annotation_df() if arg_df is None else arg_df
        if len(df) == 0:
            logger.info("タスク一覧が0件のため出力しない")
            return

        renderer = hv.renderer('bokeh')

        histograms2 = []
        for label_name in self.table.label_dict.values():
            mean = round(df[label_name].mean(), 2)
            std = round(df[label_name].std(), 2)
            title = f"{label_name}(mean = {mean}, std = {std})"
            axis_name = f"アノテーション数_{label_name}"

            data = df[label_name].values
            frequencies, edges = np.histogram(data, 20)
            hist = hv.Histogram((edges, frequencies), kdims=axis_name, vdims="タスク数", label=title).options(width=400)
            histograms2.append(hist)

        # 軸範囲が同期しないようにする
        layout2 = hv.Layout(histograms2).options(shared_axes=False)
        renderer.save(layout2, f"{self.outdir}/{self.short_project_id}_ラベルごとのアノテーション数のヒストグラム")

    def write_cumulative_line_graph_for_annotator(self, task_df: Optional[pd.DataFrame] = None,
                                                  first_annotation_user_id_list: Optional[List[str]] = None):
        """
        教師付作業者用の累積折れ線グラフを出力する。

        Args:
            task_df:
            first_annotation_user_id_list: 最初のアノテーションを担当したuser_idのList. Noneの場合はtask_dfから決まる。

        Returns:

        """
        def write_cumulative_graph(fig_info_list: List[Dict[str, str]], html_title: str):
            """
            累計グラフを出力する。

            Args:
                fig_info_list:
                html_title:

            Returns:

            """
            figs: List[bokeh.plotting.Figure] = []
            for fig_info in fig_info_list:
                figs.append(
                    figure(plot_width=1200, plot_height=600, title=fig_info["title"],
                           x_axis_label=fig_info["x_axis_label"], y_axis_label=fig_info["y_axis_label"]))

            for user_index, user_id in enumerate(first_annotation_user_id_list):  # type: ignore
                filtered_df = df[df["first_annotation_user_id"] == user_id]
                if filtered_df.empty:
                    logger.debug(f"dataframe is empty. user_id = {user_id}")
                    continue

                # 列が多すぎるとbokehのグラフが表示されないので絞り込む
                columns = tooltip_item + [
                    "cumulative_annotation_count",
                    "cumulative_input_data_count",
                    "cumulative_task_count",
                    "cumulative_annotation_worktime_hour",
                    "cumulative_inspection_worktime_hour",
                    "cumulative_acceptance_worktime_hour",
                    "cumulative_inspection_count",
                    "cumulative_number_of_rejections",
                    "cumulative_number_of_rejections_by_inspection",
                    "cumulative_number_of_rejections_by_acceptance",
                ]

                filtered_df = filtered_df[columns]
                source = ColumnDataSource(data=filtered_df)
                color = self.my_palette[user_index]
                username = filtered_df.iloc[0]["first_annotation_username"]

                for fig, fig_info in zip(figs, fig_info_list):
                    self._plot_line_and_circle(fig, x=fig_info["x"], y=fig_info["y"], source=source, username=username,
                                               color=color)

            hover_tool = self._create_hover_tool(tooltip_item)
            for fig in figs:
                self._set_legend(fig, hover_tool)

            bokeh.plotting.reset_output()
            bokeh.plotting.output_file(f"{self.outdir}/{self.short_project_id}_{html_title}.html", title=html_title)
            bokeh.plotting.save(bokeh.layouts.column(figs))

        tooltip_item = [
            "task_id",
            "phase",
            "status",
            "first_annotation_user_id",
            "first_annotation_username",
            "first_annotation_started_datetime",
            "updated_datetime",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
            "annotation_count",
            "input_data_count",
            "inspection_count",
        ]

        task_df = self.table.create_task_df() if task_df is None else task_df
        if len(task_df) == 0:
            logger.info("タスク一覧が0件のため出力しない")
            return

        max_user_length = len(self.my_palette)
        if first_annotation_user_id_list is None or len(first_annotation_user_id_list) == 0:
            tmp_list: List[str] = task_df["first_annotation_user_id"].dropna().unique().tolist()[0:max_user_length]
            tmp_list.sort()
            first_annotation_user_id_list = tmp_list

        if len(first_annotation_user_id_list) > max_user_length:
            logger.debug(f"表示対象のuser_idの数が多いため、先頭から{max_user_length}個のみグラフ化します")
            first_annotation_user_id_list = first_annotation_user_id_list[0:max_user_length]

        logger.debug(f"グラフに表示するuser_id = {first_annotation_user_id_list}")

        # 累計値を計算
        df = self.table.create_cumulative_df_by_first_annotator(task_df)

        # 横軸が累計のアノテーション数
        fig_info_list_annotation_count = [
            dict(x="cumulative_annotation_count", y="cumulative_annotation_worktime_hour", title="アノテーション数と教師付時間の累積グラフ",
                 x_axis_label="アノテーション数", y_axis_label="教師付時間[hour]"),
            dict(x="cumulative_annotation_count", y="cumulative_inspection_worktime_hour", title="アノテーション数と検査時間の累積グラフ",
                 x_axis_label="アノテーション数", y_axis_label="検査時間[hour]"),
            dict(x="cumulative_annotation_count", y="cumulative_acceptance_worktime_hour", title="アノテーション数と受入時間の累積グラフ",
                 x_axis_label="アノテーション数", y_axis_label="受入時間[hour]"),
            dict(x="cumulative_annotation_count", y="cumulative_inspection_count", title="アノテーション数と検査コメント数の累積グラフ",
                 x_axis_label="アノテーション数", y_axis_label="検査コメント数"),
        ]
        write_cumulative_graph(fig_info_list_annotation_count, html_title="アノテーション単位の累計グラフ")

        # 横軸が累計の入力データ数
        fig_info_list_input_data_count = [
            dict(x="cumulative_input_data_count", y="cumulative_annotation_worktime_hour", title="入力データ数と教師付時間の累積グラフ",
                 x_axis_label="入力データ数", y_axis_label="教師付時間[hour]"),
            dict(x="cumulative_input_data_count", y="cumulative_inspection_worktime_hour", title="入力データ数と検査時間の累積グラフ",
                 x_axis_label="入力データ数", y_axis_label="検査時間[hour]"),
            dict(x="cumulative_input_data_count", y="cumulative_acceptance_worktime_hour", title="入力データ数と受入時間の累積グラフ",
                 x_axis_label="入力データ数", y_axis_label="受入時間[hour]"),
            dict(x="cumulative_input_data_count", y="cumulative_inspection_count", title="アノテーション数と検査コメント数の累積グラフ",
                 x_axis_label="入力データ数", y_axis_label="検査コメント数"),
        ]
        write_cumulative_graph(fig_info_list_input_data_count, html_title="入力データ単位の累計グラフ")

        # 横軸が累計のタスク数
        fig_info_list_task_count = [
            dict(x="cumulative_task_count", y="cumulative_annotation_worktime_hour", title="タスク数と教師付時間の累積グラフ",
                 x_axis_label="タスク数", y_axis_label="教師付時間[hour]"),
            dict(x="cumulative_task_count", y="cumulative_inspection_worktime_hour", title="タスク数と検査時間の累積グラフ",
                 x_axis_label="タスク数", y_axis_label="検査時間[hour]"),
            dict(x="cumulative_task_count", y="cumulative_acceptance_worktime_hour", title="タスク数と受入時間の累積グラフ",
                 x_axis_label="タスク数", y_axis_label="受入時間[hour]"),
            dict(x="cumulative_task_count", y="cumulative_inspection_count", title="タスク数と検査コメント数の累積グラフ",
                 x_axis_label="タスク数", y_axis_label="検査コメント数"),
            dict(x="cumulative_task_count", y="cumulative_number_of_rejections", title="タスク数と差押し戻し回数の累積グラフ",
                 x_axis_label="タスク数", y_axis_label="差し戻し回数"),
            dict(x="cumulative_task_count", y="cumulative_number_of_rejections_by_inspection",
                 title="タスク数と差押し戻し回数(検査フェーズ)の累積グラフ", x_axis_label="タスク数", y_axis_label="差し戻し回数(検査フェーズ)"),
            dict(x="cumulative_task_count", y="cumulative_number_of_rejections_by_acceptance",
                 title="タスク数と差押し戻し回数(受入フェーズ)の累積グラフ", x_axis_label="タスク数", y_axis_label="差し戻し回数(受入フェーズ)"),
        ]
        write_cumulative_graph(fig_info_list_task_count, html_title="タスク単位の累計グラフ")

    def write_cumulative_line_graph_for_inspector(self, task_df: Optional[pd.DataFrame] = None,
                                                  first_inspection_user_id_list: Optional[List[str]] = None):
        """
        検査作業者用の累積折れ線グラフを出力する。

        Args:
            task_df:
            first_inspection_user_id_list: 最初の検査フェーズを担当したuser_idのList. Noneの場合はtask_dfから決まる。

        Returns:

        """
        def write_cumulative_graph(fig_info_list: List[Dict[str, str]], html_title: str):
            """
            累計グラフを出力する。

            Args:
                fig_info_list:
                html_title:

            Returns:

            """
            figs: List[bokeh.plotting.Figure] = []
            for fig_info in fig_info_list:
                figs.append(
                    figure(plot_width=1200, plot_height=600, title=fig_info["title"],
                           x_axis_label=fig_info["x_axis_label"], y_axis_label=fig_info["y_axis_label"]))

            for user_index, user_id in enumerate(first_inspection_user_id_list):  # type: ignore
                filtered_df = df[df["first_inspection_user_id"] == user_id]
                if filtered_df.empty:
                    logger.debug(f"dataframe is empty. user_id = {user_id}")
                    continue

                # 列が多すぎるとbokehのグラフが表示されないので絞り込む
                columns = tooltip_item + [
                    "cumulative_annotation_count",
                    "cumulative_input_data_count",
                    "cumulative_task_count",
                    "cumulative_first_inspection_worktime_hour",
                    "cumulative_inspection_worktime_hour",
                    "cumulative_acceptance_worktime_hour",
                    "cumulative_inspection_count",
                ]

                filtered_df = filtered_df[columns]
                source = ColumnDataSource(data=filtered_df)
                color = self.my_palette[user_index]
                username = filtered_df.iloc[0]["first_inspection_username"]

                for fig, fig_info in zip(figs, fig_info_list):
                    self._plot_line_and_circle(fig, x=fig_info["x"], y=fig_info["y"], source=source, username=username,
                                               color=color)

            hover_tool = self._create_hover_tool(tooltip_item)
            for fig in figs:
                self._set_legend(fig, hover_tool)

            bokeh.plotting.reset_output()
            bokeh.plotting.output_file(f"{self.outdir}/{self.short_project_id}_{html_title}.html", title=html_title)
            bokeh.plotting.save(bokeh.layouts.column(figs))

        tooltip_item = [
            "task_id",
            "phase",
            "status",
            "first_annotation_username",
            "first_annotation_started_datetime",
            "first_inspection_username",
            "first_inspection_started_datetime",
            "updated_datetime",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
            "annotation_count",
            "input_data_count",
            "inspection_count",
        ]

        task_df = self.table.create_task_df() if task_df is None else task_df
        if len(task_df) == 0:
            logger.info("タスク一覧が0件のため出力しない")
            return

        max_user_length = len(self.my_palette)
        if first_inspection_user_id_list is None or len(first_inspection_user_id_list) == 0:
            tmp_list: List[str] = task_df["first_inspection_user_id"].dropna().unique().tolist()[0:max_user_length]
            tmp_list.sort()
            first_inspection_user_id_list = tmp_list

        if len(first_inspection_user_id_list) > max_user_length:
            logger.debug(f"表示対象のuser_idの数が多いため、先頭から{max_user_length}個のみグラフ化します")
            first_inspection_user_id_list = first_inspection_user_id_list[0:max_user_length]

        logger.debug(f"グラフに表示するuser_id = {first_inspection_user_id_list}")

        # 累計値を計算
        df = self.table.create_cumulative_df_by_first_inspector(task_df)

        # 横軸が累計のアノテーション数
        fig_info_list_annotation_count = [
            dict(x="cumulative_annotation_count", y="cumulative_first_inspection_worktime_hour",
                 title="アノテーション数と1回目検査時間の累積グラフ", x_axis_label="アノテーション数", y_axis_label="1回目の検査時間[hour]"),
            dict(x="cumulative_annotation_count", y="cumulative_inspection_worktime_hour", title="アノテーション数と検査時間の累積グラフ",
                 x_axis_label="アノテーション数", y_axis_label="検査時間[hour]"),
            dict(x="cumulative_inspection_count", y="cumulative_first_inspection_worktime_hour",
                 title="検査コメント数と1回目検査時間の累積グラフ", x_axis_label="検査コメント数", y_axis_label="1回目の検査時間[hour]"),
            dict(x="cumulative_inspection_count", y="cumulative_inspection_worktime_hour", title="検査コメント数と検査時間の累積グラフ",
                 x_axis_label="検査コメント数", y_axis_label="検査時間[hour]"),
        ]
        write_cumulative_graph(fig_info_list_annotation_count, html_title="検査者用_アノテーション単位の累計グラフ")

        # 横軸が累計の入力データ数
        fig_info_list_input_data_count = [
            dict(x="cumulative_input_data_count", y="cumulative_first_inspection_worktime_hour",
                 title="アノテーション数と1回目検査時間の累積グラフ", x_axis_label="入力データ数", y_axis_label="1回目の検査時間[hour]"),
            dict(x="cumulative_input_data_count", y="cumulative_inspection_worktime_hour", title="入力データ数と検査時間の累積グラフ",
                 x_axis_label="入力データ数", y_axis_label="検査時間[hour]"),
        ]
        write_cumulative_graph(fig_info_list_input_data_count, html_title="検査者用_入力データ単位の累計グラフ")
