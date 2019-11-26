import logging
from typing import Any, Dict, List, Optional  # pylint: disable=unused-import

import bokeh
import bokeh.layouts
import bokeh.palettes
import dateutil
import holoviews as hv
import numpy as np
import pandas as pd
from bokeh.models import HoverTool
from bokeh.plotting import ColumnDataSource, figure

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

    def __init__(self, outdir: str, project_id: str):
        self.outdir = outdir
        self.short_project_id = project_id[0:8]

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

    def write_プロジェクト全体のヒストグラム(self, df: pd.DataFrame):
        """
        以下の情報をヒストグラムで出力する。
        作業時間関係、検査コメント数関係、アノテーション数

        Args:
            df: タスク一覧のDataFrame. Noneならば新たに生成する

        """

        if len(df) == 0:
            logger.info("タスク一覧が0件のため出力しない")
            return

        renderer = hv.renderer('bokeh')

        columns = [
            ("annotation_count", "アノテーション数"),
            ("sum_worktime_hour", "総作業時間[hour]"),
            ("annotation_worktime_hour", "教師付時間[hour]"),
            ("inspection_worktime_hour", "検査時間[hour]"),
            ("acceptance_worktime_hour", "受入時間[hour]"),
            ("inspection_count", "検査コメント数"),
            ("input_data_count_of_inspection", "指摘を受けた画像枚数"),
            ("input_data_count", "画像枚数"),
            # 経過時間
            ("diff_days_to_first_inspection_started", "最初の検査を着手するまでの日数"),
            ("diff_days_to_first_acceptance_started", "最初の受入を着手するまでの日数"),
            ("diff_days_to_task_completed", "受入完了状態になるまでの日数"),
        ]

        histograms1 = []
        for col, y_axis_name in columns:
            filtered_df = df[df[col].notnull()]

            mean = round(filtered_df[col].mean(), 2)
            std = round(filtered_df[col].std(), 2)
            title = f"{y_axis_name}: μ={mean}, α={std}, N={len(filtered_df)}"

            data = filtered_df[col].values
            bins = 20

            frequencies, edges = np.histogram(data, bins)
            hist = hv.Histogram((edges, frequencies), kdims=y_axis_name, vdims="タスク数", label=title).options(width=500)
            histograms1.append(hist)

        # 軸範囲が同期しないようにする
        layout1 = hv.Layout(histograms1).options(shared_axes=False)
        renderer.save(layout1, f"{self.outdir}/{self.short_project_id}_プロジェクト全体のヒストグラム")

    def wirte_ラベルごとのアノテーション数(self, df: pd.DataFrame):
        """
        アノテーションラベルごとの個数を出力
        """
        if len(df) == 0:
            logger.info("タスク一覧が0件のため出力しない")
            return

        renderer = hv.renderer('bokeh')

        histograms2 = []
        label_columns = [e for e in df.columns if e.startswith("label_")]

        for column in label_columns:
            label_name = column[len("label_"):]
            mean = round(df[column].mean(), 2)
            std = round(df[column].std(), 2)
            title = f"{label_name}(mean = {mean}, std = {std})"
            axis_name = f"アノテーション数_{label_name}"

            data = df[column].values
            frequencies, edges = np.histogram(data, 20)
            hist = hv.Histogram((edges, frequencies), kdims=axis_name, vdims="タスク数", label=title).options(width=400)
            histograms2.append(hist)

        # 軸範囲が同期しないようにする
        layout2 = hv.Layout(histograms2).options(shared_axes=False)
        renderer.save(layout2, f"{self.outdir}/{self.short_project_id}_ラベルごとのアノテーション数のヒストグラム")

    def create_user_id_list(self, df: pd.DataFrame, user_id_column: str,
                            arg_user_id_list: Optional[List[str]] = None) -> List[str]:
        """
        グラフに表示するユーザのuser_idを生成する。

        Args:
            df:
            user_id_column: user_idが格納されている列の名前
            arg_first_annotation_user_id_list: 指定されたuser_idのList

        Returns:
            グラフに表示するユーザのuser_idのList

        """
        max_user_length = len(self.my_palette)
        if arg_user_id_list is None or len(arg_user_id_list) == 0:
            tmp_list: List[str] = df[user_id_column].dropna().unique().tolist()[0:max_user_length]
            tmp_list.sort()
            user_id_list = tmp_list
        else:
            user_id_list = arg_user_id_list

        if len(user_id_list) > max_user_length:
            logger.debug(f"表示対象のuser_idの数が多いため、先頭から{max_user_length}個のみグラフ化します")

        return user_id_list[0:max_user_length]

    def write_productivity_line_graph_for_annotator(self, df: pd.DataFrame,
                                                    first_annotation_user_id_list: Optional[List[str]] = None):
        """
        生産性を教師付作業者ごとにプロットする。

        Args:
            df:
            first_annotation_user_id_list:

        Returns:

        """
        def write_cumulative_graph(fig_info_list: List[Dict[str, str]], html_title: str):
            """

            Args:
                fig_info_list:
                html_title:

            Returns:

            """
            figs: List[bokeh.plotting.Figure] = []
            for fig_info in fig_info_list:
                figs.append(
                    figure(plot_width=1200, plot_height=600, title=fig_info["title"],
                           x_axis_label=fig_info["x_axis_label"], x_axis_type="datetime",
                           y_axis_label=fig_info["y_axis_label"]))

            for user_index, user_id in enumerate(first_annotation_user_id_list):  # type: ignore
                filtered_df = df[df["first_annotation_user_id"] == user_id]
                if filtered_df.empty:
                    logger.debug(f"dataframe is empty. user_id = {user_id}")
                    continue

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
            "first_annotation_user_id",
            "first_annotation_username",
            "first_annotation_started_date",
            "first_annotation_worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
            "annotation_count",
            "input_data_count",
            "task_count",
            "inspection_count",
        ]

        if len(df) == 0:
            logger.info("データが0件のため出力しない")
            return

        first_annotation_user_id_list = self.create_user_id_list(df, "first_annotation_user_id",
                                                                 first_annotation_user_id_list)
        logger.debug(f"グラフに表示するuser_id = {first_annotation_user_id_list}")

        df["date_first_annotation_started_date"] = df["first_annotation_started_date"].map(
            lambda e: dateutil.parser.parse(e).date())

        fig_info_list_annotation_count = [
            dict(x="date_first_annotation_started_date", y="first_annotation_worktime_minute/annotation_count",
                 title="アノテーションあたり教師付時間(1回目)の折れ線グラフ", x_axis_label="1回目の教師付開始日",
                 y_axis_label="アノテーションあたり教師付時間(1回目)[min]"),
            dict(x="date_first_annotation_started_date", y="annotation_worktime_minute/annotation_count",
                 title="アノテーションあたり教師付時間の折れ線グラフ", x_axis_label="1回目の教師付開始日", y_axis_label="アノテーションあたり教師付時間[min]"),
            dict(x="date_first_annotation_started_date", y="inspection_worktime_minute/annotation_count",
                 title="アノテーションあたり検査時間の折れ線グラフ", x_axis_label="1回目の教師付開始日", y_axis_label="アノテーションあたり検査時間[min]"),
            dict(x="date_first_annotation_started_date", y="acceptance_worktime_minute/annotation_count",
                 title="アノテーションあたり受入時間の折れ線グラフ", x_axis_label="1回目の教師付開始日", y_axis_label="アノテーションあたり受入時間[min]"),
            dict(x="date_first_annotation_started_date", y="inspection_count/annotation_count",
                 title="アノテーションあたり検査コメント数の折れ線グラフ", x_axis_label="1回目の教師付開始日", y_axis_label="アノテーションあたり検査コメント数"),
        ]
        write_cumulative_graph(fig_info_list_annotation_count, html_title="アノテーション単位の日毎の折れ線グラフ")

        fig_info_list_input_data_count = [
            dict(x="date_first_annotation_started_date", y="first_annotation_worktime_minute/input_data_count",
                 title="画像あたり教師付時間(1回目)の折れ線グラフ", x_axis_label="1回目の教師付開始日", y_axis_label="画像あたり教師付時間(1回目)[min]"),
            dict(x="date_first_annotation_started_date", y="annotation_worktime_minute/input_data_count",
                 title="画像あたり教師付時間の折れ線グラフ", x_axis_label="1回目の教師付開始日", y_axis_label="画像あたり教師付時間[min]"),
            dict(x="date_first_annotation_started_date", y="inspection_worktime_minute/input_data_count",
                 title="画像あたり検査時間の折れ線グラフ", x_axis_label="1回目の教師付開始日", y_axis_label="画像あたり検査時間[min]"),
            dict(x="date_first_annotation_started_date", y="acceptance_worktime_minute/input_data_count",
                 title="画像あたり受入時間の折れ線グラフ", x_axis_label="1回目の教師付開始日", y_axis_label="画像あたり受入時間[min]"),
            dict(x="date_first_annotation_started_date", y="inspection_count/input_data_count",
                 title="画像あたり検査コメント数の折れ線グラフ", x_axis_label="1回目の教師付開始日", y_axis_label="画像あたり検査コメント数"),
        ]
        write_cumulative_graph(fig_info_list_input_data_count, html_title="画像単位の日毎の折れ線グラフ")

        fig_info_list_value = [
            dict(x="date_first_annotation_started_date", y="annotation_count", title="作業したアノテーション数の折れ線グラフ",
                 x_axis_label="1回目の教師付開始日", y_axis_label="アノテーション数"),
            dict(x="date_first_annotation_started_date", y="input_data_count", title="作業した画像数の折れ線グラフ",
                 x_axis_label="1回目の教師付開始日", y_axis_label="画像数"),
            dict(x="date_first_annotation_started_date", y="task_count", title="作業したタスク数の折れ線グラフ",
                 x_axis_label="1回目の教師付開始日", y_axis_label="タスク数"),
            dict(x="date_first_annotation_started_date", y="first_annotation_worktime_hour", title="教師付時間(1回目)の折れ線グラフ",
                 x_axis_label="1回目の教師付開始日", y_axis_label="教師付時間(1回目)[hour]"),
            dict(x="date_first_annotation_started_date", y="annotation_worktime_hour", title="教師付時間の折れ線グラフ",
                 x_axis_label="1回目の教師付開始日", y_axis_label="教師付時間[hour]"),
        ]
        write_cumulative_graph(fig_info_list_value, html_title="日毎の折れ線グラフ")

    def write_cumulative_line_graph_for_annotator(self, df: pd.DataFrame,
                                                  first_annotation_user_id_list: Optional[List[str]] = None):
        """
        教師付作業者用の累積折れ線グラフを出力する。

        Args:
            df:
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

        if len(df) == 0:
            logger.info("タスク一覧が0件のため出力しない")
            return

        first_annotation_user_id_list = self.create_user_id_list(df, "first_annotation_user_id",
                                                                 first_annotation_user_id_list)
        logger.debug(f"グラフに表示するuser_id = {first_annotation_user_id_list}")

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

    def write_cumulative_line_graph_for_inspector(self, df: pd.DataFrame,
                                                  first_inspection_user_id_list: Optional[List[str]] = None):
        """
        検査作業者用の累積折れ線グラフを出力する。

        Args:
            df:
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

        if len(df) == 0:
            logger.info("タスク一覧が0件のため出力しない")
            return

        first_inspection_user_id_list = self.create_user_id_list(df, "first_inspection_user_id",
                                                                 first_inspection_user_id_list)

        if len(first_inspection_user_id_list) == 0:
            logger.info(f"検査フェーズを担当してユーザがいないため、検査者用のグラフは出力しません。")
            return

        logger.debug(f"グラフに表示するuser_id = {first_inspection_user_id_list}")

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
