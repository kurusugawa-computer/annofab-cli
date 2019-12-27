# pylint: disable=too-many-lines
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

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

hv.extension("bokeh")


@dataclass
class HistogramName:
    """
    ヒストグラムの名前を表現するデータクラス
    """

    title: str
    """グラフのタイトル"""
    x_axis_label: str
    """X軸のラベル名"""
    column: str
    """pandas.DataFrameにアクセスする列名"""
    y_axis_label: str = "タスク数"
    """Y軸のラベル名"""


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
        Path(f"{outdir}/html").mkdir(exist_ok=True, parents=True)

    @staticmethod
    def _create_hover_tool(tool_tip_items: List[str] = None) -> HoverTool:
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

        fig.line(
            x=x,
            y=y,
            source=source,
            legend_label=username,
            line_color=color,
            line_width=1,
            muted_alpha=0.2,
            muted_color=color,
        )
        fig.circle(
            x=x, y=y, source=source, legend_label=username, muted_alpha=0.0, muted_color=color, color=color,
        )

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

    @staticmethod
    def _create_histogram(df: pd.DataFrame, histogram_name: HistogramName, bins: int = 20) -> hv.Histogram:
        """
        ヒストグラムを生成する。
        Args:
            df:
            histogram_name:
            bins: ヒスグラムの棒の数

        Returns:
            ヒストグラムオブジェクト
        """
        mean = round(df[histogram_name.column].mean(), 3)
        std = round(df[histogram_name.column].std(), 3)
        title = f"{histogram_name.title}: μ={mean}, α={std}, N={len(df)}"

        data = df[histogram_name.column].values

        frequencies, edges = np.histogram(data, bins)
        hist = (
            hv.Histogram((edges, frequencies), kdims=histogram_name.x_axis_label, vdims=histogram_name.y_axis_label)
            .options(width=500, title=title, fontsize={"title": 9})
            .opts(hv.opts(tools=["hover"]))
        )
        return hist

    def write_histogram_for_worktime(self, df: pd.DataFrame):
        """
        作業時間に関する情報をヒストグラムとして表示する。

        Args:
            df: タスク一覧のDataFrame

        """
        if len(df) == 0:
            logger.info("タスク一覧が0件のため出力しない")
            return

        renderer = hv.renderer("bokeh")

        histogram_name_list = [
            HistogramName(column="annotation_worktime_hour", x_axis_label="教師付時間[hour]", title="教師付時間",),
            HistogramName(column="inspection_worktime_hour", x_axis_label="検査時間[hour]", title="検査時間",),
            HistogramName(column="acceptance_worktime_hour", x_axis_label="受入時間[hour]", title="受入時間",),
            HistogramName(
                column="first_annotator_worktime_hour", x_axis_label="1回目の教師付者の作業時間[hour]", title="1回目の教師付者の作業時間",
            ),
            HistogramName(
                column="first_inspector_worktime_hour", x_axis_label="1回目の検査者の作業時間[hour]", title="1回目の検査者の作業時間",
            ),
            HistogramName(
                column="first_acceptor_worktime_hour", x_axis_label="1回目の受入者の作業時間[hour]", title="1回目の受入者の作業時間",
            ),
            HistogramName(column="first_annotation_worktime_hour", x_axis_label="1回目の教師付時間[hour]", title="1回目の教師付時間",),
            HistogramName(column="first_inspection_worktime_hour", x_axis_label="1回目の検査時間[hour]", title="1回目の検査時間",),
            HistogramName(column="first_acceptance_worktime_hour", x_axis_label="1回目の受入時間[hour]", title="1回目の受入時間",),
            HistogramName(column="sum_worktime_hour", x_axis_label="総作業時間[hour]", title="総作業時間"),
        ]

        histograms = []
        for histogram_name in histogram_name_list:
            filtered_df = df[df[histogram_name.column].notnull()]
            hist = self._create_histogram(filtered_df, histogram_name=histogram_name)
            histograms.append(hist)

        # 自動受入したタスクを除外して、受入時間をグラフ化する
        filtered_df = df[df["acceptance_worktime_hour"].notnull()]
        histograms.append(
            self._create_histogram(
                filtered_df[~filtered_df["acceptance_is_skipped"]],
                histogram_name=HistogramName(
                    column="acceptance_worktime_hour", x_axis_label="受入時間[hour]", title="受入時間(自動受入されたタスクを除外)",
                ),
            )
        )

        # 軸範囲が同期しないようにする
        layout = hv.Layout(histograms).options(shared_axes=False).cols(3)
        renderer.save(layout, f"{self.outdir}/html/{self.short_project_id}-ヒストグラム-作業時間")

    def write_histogram_for_other(self, df: pd.DataFrame):
        """
        アノテーション数や、検査コメント数など、作業時間以外の情報をヒストグラムで表示する。

        Args:
            df: タスク一覧のDataFrame

        """
        if len(df) == 0:
            logger.info("タスク一覧が0件のため出力しない")
            return

        renderer = hv.renderer("bokeh")

        histogram_name_list = [
            HistogramName(column="annotation_count", x_axis_label="アノテーション数", title="アノテーション数"),
            HistogramName(column="input_data_count", x_axis_label="画像枚数", title="画像枚数"),
            HistogramName(column="inspection_count", x_axis_label="検査コメント数", title="検査コメント数"),
            HistogramName(column="input_data_count_of_inspection", x_axis_label="指摘を受けた画像枚数", title="指摘を受けた画像枚数",),
            # 経過日数
            HistogramName(
                column="diff_days_to_first_inspection_started", x_axis_label="最初の検査を着手するまでの日数", title="最初の検査を着手するまでの日数",
            ),
            HistogramName(
                column="diff_days_to_first_acceptance_started", x_axis_label="最初の受入を着手するまでの日数", title="最初の受入を着手するまでの日数",
            ),
            HistogramName(column="diff_days_to_task_completed", x_axis_label="受入完了状態になるまでの日数", title="受入完了状態になるまでの日数",),
            # 差し戻し回数
            HistogramName(
                column="number_of_rejections_by_inspection", x_axis_label="検査フェーズでの差し戻し回数", title="検査フェーズでの差し戻し回数",
            ),
            HistogramName(
                column="number_of_rejections_by_acceptance", x_axis_label="受入フェーズでの差し戻し回数", title="受入フェーズでの差し戻し回数",
            ),
        ]

        histograms = []
        for histogram_name in histogram_name_list:
            filtered_df = df[df[histogram_name.column].notnull()]
            hist = self._create_histogram(filtered_df, histogram_name=histogram_name)
            histograms.append(hist)

        # 軸範囲が同期しないようにする
        layout = hv.Layout(histograms).options(shared_axes=False).cols(3)
        renderer.save(layout, f"{self.outdir}/html/{self.short_project_id}-ヒストグラム")

    def write_histogram_for_annotation_count_by_label(self, df: pd.DataFrame) -> None:
        """
        アノテーションラベルごとのアノテーション数をヒストグラムで出力する。
        """
        if len(df) == 0:
            logger.info("タスク一覧が0件のため出力しない")
            return

        renderer = hv.renderer("bokeh")

        histograms = []
        label_columns = [e for e in df.columns if e.startswith("label_")]

        for column in label_columns:
            label_name = column[len("label_") :]
            histogram_name = HistogramName(
                column=column, x_axis_label=f"'{label_name}'のアノテーション数", title=f"{label_name}"
            )
            hist = self._create_histogram(df, histogram_name=histogram_name)

            histograms.append(hist)

        # 軸範囲が同期しないようにする
        layout = hv.Layout(histograms).options(shared_axes=False).cols(3)
        renderer.save(layout, f"{self.outdir}/html/{self.short_project_id}-ヒストグラム-ラベルごとのアノテーション数")

    def create_user_id_list(
        self, df: pd.DataFrame, user_id_column: str, arg_user_id_list: Optional[List[str]] = None,
    ) -> List[str]:
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
            tmp_list: List[str] = df[user_id_column].dropna().unique().tolist()
            tmp_list.sort()
            user_id_list = tmp_list
        else:
            user_id_list = arg_user_id_list

        if len(user_id_list) > max_user_length:
            logger.info(f"表示対象のuser_idの数が多いため、先頭から{max_user_length}個のみグラフ化します")

        return user_id_list[0:max_user_length]

    def write_productivity_line_graph_for_annotator(
        self, df: pd.DataFrame, first_annotation_user_id_list: Optional[List[str]] = None,
    ):
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
                    figure(
                        plot_width=1200,
                        plot_height=600,
                        title=fig_info["title"],
                        x_axis_label=fig_info["x_axis_label"],
                        x_axis_type="datetime",
                        y_axis_label=fig_info["y_axis_label"],
                    )
                )

            for user_index, user_id in enumerate(first_annotation_user_id_list):  # type: ignore
                filtered_df = df[df["first_annotation_user_id"] == user_id]
                if filtered_df.empty:
                    logger.debug(f"dataframe is empty. user_id = {user_id}")
                    continue

                source = ColumnDataSource(data=filtered_df)
                color = self.my_palette[user_index]
                username = filtered_df.iloc[0]["first_annotation_username"]

                for fig, fig_info in zip(figs, fig_info_list):
                    self._plot_line_and_circle(
                        fig, x=fig_info["x"], y=fig_info["y"], source=source, username=username, color=color,
                    )

            hover_tool = self._create_hover_tool(tooltip_item)
            for fig in figs:
                self._set_legend(fig, hover_tool)

            bokeh.plotting.reset_output()
            bokeh.plotting.output_file(
                f"{self.outdir}/html/{self.short_project_id}-{html_title}.html", title=html_title,
            )
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

        first_annotation_user_id_list = self.create_user_id_list(
            df, "first_annotation_user_id", first_annotation_user_id_list
        )
        logger.debug(f"グラフに表示するuser_id = {first_annotation_user_id_list}")

        df["date_first_annotation_started_date"] = df["first_annotation_started_date"].map(
            lambda e: dateutil.parser.parse(e).date()
        )

        fig_info_list_annotation_count = [
            dict(
                x="date_first_annotation_started_date",
                y="first_annotation_worktime_minute/annotation_count",
                title="アノテーションあたり教師付時間(1回目)の折れ線グラフ",
                x_axis_label="1回目の教師付開始日",
                y_axis_label="アノテーションあたり教師付時間(1回目)[min]",
            ),
            dict(
                x="date_first_annotation_started_date",
                y="annotation_worktime_minute/annotation_count",
                title="アノテーションあたり教師付時間の折れ線グラフ",
                x_axis_label="1回目の教師付開始日",
                y_axis_label="アノテーションあたり教師付時間[min]",
            ),
            dict(
                x="date_first_annotation_started_date",
                y="inspection_worktime_minute/annotation_count",
                title="アノテーションあたり検査時間の折れ線グラフ",
                x_axis_label="1回目の教師付開始日",
                y_axis_label="アノテーションあたり検査時間[min]",
            ),
            dict(
                x="date_first_annotation_started_date",
                y="acceptance_worktime_minute/annotation_count",
                title="アノテーションあたり受入時間の折れ線グラフ",
                x_axis_label="1回目の教師付開始日",
                y_axis_label="アノテーションあたり受入時間[min]",
            ),
            dict(
                x="date_first_annotation_started_date",
                y="inspection_count/annotation_count",
                title="アノテーションあたり検査コメント数の折れ線グラフ",
                x_axis_label="1回目の教師付開始日",
                y_axis_label="アノテーションあたり検査コメント数",
            ),
        ]
        write_cumulative_graph(
            fig_info_list_annotation_count, html_title="折れ線-横軸_教師付開始日-縦軸_アノテーションあたりの指標-教師付者用",
        )

        fig_info_list_input_data_count = [
            dict(
                x="date_first_annotation_started_date",
                y="first_annotation_worktime_minute/input_data_count",
                title="画像あたり教師付時間(1回目)の折れ線グラフ",
                x_axis_label="1回目の教師付開始日",
                y_axis_label="画像あたり教師付時間(1回目)[min]",
            ),
            dict(
                x="date_first_annotation_started_date",
                y="annotation_worktime_minute/input_data_count",
                title="画像あたり教師付時間の折れ線グラフ",
                x_axis_label="1回目の教師付開始日",
                y_axis_label="画像あたり教師付時間[min]",
            ),
            dict(
                x="date_first_annotation_started_date",
                y="inspection_worktime_minute/input_data_count",
                title="画像あたり検査時間の折れ線グラフ",
                x_axis_label="1回目の教師付開始日",
                y_axis_label="画像あたり検査時間[min]",
            ),
            dict(
                x="date_first_annotation_started_date",
                y="acceptance_worktime_minute/input_data_count",
                title="画像あたり受入時間の折れ線グラフ",
                x_axis_label="1回目の教師付開始日",
                y_axis_label="画像あたり受入時間[min]",
            ),
            dict(
                x="date_first_annotation_started_date",
                y="inspection_count/input_data_count",
                title="画像あたり検査コメント数の折れ線グラフ",
                x_axis_label="1回目の教師付開始日",
                y_axis_label="画像あたり検査コメント数",
            ),
        ]
        write_cumulative_graph(fig_info_list_input_data_count, html_title="折れ線-横軸_教師付開始日-縦軸_画像あたりの指標-教師付者用")

        fig_info_list_value = [
            dict(
                x="date_first_annotation_started_date",
                y="annotation_count",
                title="作業したアノテーション数の折れ線グラフ",
                x_axis_label="1回目の教師付開始日",
                y_axis_label="アノテーション数",
            ),
            dict(
                x="date_first_annotation_started_date",
                y="input_data_count",
                title="作業した画像数の折れ線グラフ",
                x_axis_label="1回目の教師付開始日",
                y_axis_label="画像数",
            ),
            dict(
                x="date_first_annotation_started_date",
                y="task_count",
                title="作業したタスク数の折れ線グラフ",
                x_axis_label="1回目の教師付開始日",
                y_axis_label="タスク数",
            ),
            dict(
                x="date_first_annotation_started_date",
                y="first_annotation_worktime_hour",
                title="教師付時間(1回目)の折れ線グラフ",
                x_axis_label="1回目の教師付開始日",
                y_axis_label="教師付時間(1回目)[hour]",
            ),
            dict(
                x="date_first_annotation_started_date",
                y="annotation_worktime_hour",
                title="教師付時間の折れ線グラフ",
                x_axis_label="1回目の教師付開始日",
                y_axis_label="教師付時間[hour]",
            ),
        ]
        write_cumulative_graph(fig_info_list_value, html_title="折れ線-横軸_教師付開始日-縦軸_指標-教師付者用")

    def write_cumulative_line_graph_for_annotator(
        self, df: pd.DataFrame, first_annotation_user_id_list: Optional[List[str]] = None,
    ):
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
                    figure(
                        plot_width=1200,
                        plot_height=600,
                        title=fig_info["title"],
                        x_axis_label=fig_info["x_axis_label"],
                        y_axis_label=fig_info["y_axis_label"],
                    )
                )

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
                    self._plot_line_and_circle(
                        fig, x=fig_info["x"], y=fig_info["y"], source=source, username=username, color=color,
                    )

            hover_tool = self._create_hover_tool(tooltip_item)
            for fig in figs:
                self._set_legend(fig, hover_tool)

            bokeh.plotting.reset_output()
            bokeh.plotting.output_file(
                f"{self.outdir}/html/{self.short_project_id}-{html_title}.html", title=html_title,
            )
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

        first_annotation_user_id_list = self.create_user_id_list(
            df, "first_annotation_user_id", first_annotation_user_id_list
        )
        logger.debug(f"グラフに表示するuser_id = {first_annotation_user_id_list}")

        # 横軸が累計のアノテーション数
        fig_info_list_annotation_count = [
            dict(
                x="cumulative_annotation_count",
                y="cumulative_annotation_worktime_hour",
                title="アノテーション数と教師付時間の累積グラフ",
                x_axis_label="アノテーション数",
                y_axis_label="教師付時間[hour]",
            ),
            dict(
                x="cumulative_annotation_count",
                y="cumulative_inspection_worktime_hour",
                title="アノテーション数と検査時間の累積グラフ",
                x_axis_label="アノテーション数",
                y_axis_label="検査時間[hour]",
            ),
            dict(
                x="cumulative_annotation_count",
                y="cumulative_acceptance_worktime_hour",
                title="アノテーション数と受入時間の累積グラフ",
                x_axis_label="アノテーション数",
                y_axis_label="受入時間[hour]",
            ),
            dict(
                x="cumulative_annotation_count",
                y="cumulative_inspection_count",
                title="アノテーション数と検査コメント数の累積グラフ",
                x_axis_label="アノテーション数",
                y_axis_label="検査コメント数",
            ),
        ]
        write_cumulative_graph(fig_info_list_annotation_count, html_title="累計折れ線-横軸_アノテーション数-教師付者用")

        # 横軸が累計の入力データ数
        fig_info_list_input_data_count = [
            dict(
                x="cumulative_input_data_count",
                y="cumulative_annotation_worktime_hour",
                title="入力データ数と教師付時間の累積グラフ",
                x_axis_label="入力データ数",
                y_axis_label="教師付時間[hour]",
            ),
            dict(
                x="cumulative_input_data_count",
                y="cumulative_inspection_worktime_hour",
                title="入力データ数と検査時間の累積グラフ",
                x_axis_label="入力データ数",
                y_axis_label="検査時間[hour]",
            ),
            dict(
                x="cumulative_input_data_count",
                y="cumulative_acceptance_worktime_hour",
                title="入力データ数と受入時間の累積グラフ",
                x_axis_label="入力データ数",
                y_axis_label="受入時間[hour]",
            ),
            dict(
                x="cumulative_input_data_count",
                y="cumulative_inspection_count",
                title="アノテーション数と検査コメント数の累積グラフ",
                x_axis_label="入力データ数",
                y_axis_label="検査コメント数",
            ),
        ]
        write_cumulative_graph(fig_info_list_input_data_count, html_title="累計折れ線-横軸_入力データ数-教師付者用")

        # 横軸が累計のタスク数
        fig_info_list_task_count = [
            dict(
                x="cumulative_task_count",
                y="cumulative_annotation_worktime_hour",
                title="タスク数と教師付時間の累積グラフ",
                x_axis_label="タスク数",
                y_axis_label="教師付時間[hour]",
            ),
            dict(
                x="cumulative_task_count",
                y="cumulative_inspection_worktime_hour",
                title="タスク数と検査時間の累積グラフ",
                x_axis_label="タスク数",
                y_axis_label="検査時間[hour]",
            ),
            dict(
                x="cumulative_task_count",
                y="cumulative_acceptance_worktime_hour",
                title="タスク数と受入時間の累積グラフ",
                x_axis_label="タスク数",
                y_axis_label="受入時間[hour]",
            ),
            dict(
                x="cumulative_task_count",
                y="cumulative_inspection_count",
                title="タスク数と検査コメント数の累積グラフ",
                x_axis_label="タスク数",
                y_axis_label="検査コメント数",
            ),
            dict(
                x="cumulative_task_count",
                y="cumulative_number_of_rejections",
                title="タスク数と差押し戻し回数の累積グラフ",
                x_axis_label="タスク数",
                y_axis_label="差し戻し回数",
            ),
            dict(
                x="cumulative_task_count",
                y="cumulative_number_of_rejections_by_inspection",
                title="タスク数と差押し戻し回数(検査フェーズ)の累積グラフ",
                x_axis_label="タスク数",
                y_axis_label="差し戻し回数(検査フェーズ)",
            ),
            dict(
                x="cumulative_task_count",
                y="cumulative_number_of_rejections_by_acceptance",
                title="タスク数と差押し戻し回数(受入フェーズ)の累積グラフ",
                x_axis_label="タスク数",
                y_axis_label="差し戻し回数(受入フェーズ)",
            ),
        ]
        write_cumulative_graph(fig_info_list_task_count, html_title="累計折れ線-横軸_タスク数-教師付者用")

    def write_cumulative_line_graph_for_inspector(
        self, df: pd.DataFrame, first_inspection_user_id_list: Optional[List[str]] = None,
    ):
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
                    figure(
                        plot_width=1200,
                        plot_height=600,
                        title=fig_info["title"],
                        x_axis_label=fig_info["x_axis_label"],
                        y_axis_label=fig_info["y_axis_label"],
                    )
                )

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
                    self._plot_line_and_circle(
                        fig, x=fig_info["x"], y=fig_info["y"], source=source, username=username, color=color,
                    )

            hover_tool = self._create_hover_tool(tooltip_item)
            for fig in figs:
                self._set_legend(fig, hover_tool)

            bokeh.plotting.reset_output()
            bokeh.plotting.output_file(
                f"{self.outdir}/html/{self.short_project_id}-{html_title}.html", title=html_title,
            )
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

        first_inspection_user_id_list = self.create_user_id_list(
            df, "first_inspection_user_id", first_inspection_user_id_list
        )

        if len(first_inspection_user_id_list) == 0:
            logger.info(f"検査フェーズを担当してユーザがいないため、検査者用のグラフは出力しません。")
            return

        logger.debug(f"グラフに表示するuser_id = {first_inspection_user_id_list}")

        # 横軸が累計のアノテーション数
        fig_info_list_annotation_count = [
            dict(
                x="cumulative_annotation_count",
                y="cumulative_first_inspection_worktime_hour",
                title="アノテーション数と1回目検査時間の累積グラフ",
                x_axis_label="アノテーション数",
                y_axis_label="1回目の検査時間[hour]",
            ),
            dict(
                x="cumulative_annotation_count",
                y="cumulative_inspection_worktime_hour",
                title="アノテーション数と検査時間の累積グラフ",
                x_axis_label="アノテーション数",
                y_axis_label="検査時間[hour]",
            ),
            dict(
                x="cumulative_inspection_count",
                y="cumulative_first_inspection_worktime_hour",
                title="検査コメント数と1回目検査時間の累積グラフ",
                x_axis_label="検査コメント数",
                y_axis_label="1回目の検査時間[hour]",
            ),
            dict(
                x="cumulative_inspection_count",
                y="cumulative_inspection_worktime_hour",
                title="検査コメント数と検査時間の累積グラフ",
                x_axis_label="検査コメント数",
                y_axis_label="検査時間[hour]",
            ),
        ]
        write_cumulative_graph(fig_info_list_annotation_count, html_title="累計折れ線-横軸_アノテーション数-検査者用")

        # 横軸が累計の入力データ数
        fig_info_list_input_data_count = [
            dict(
                x="cumulative_input_data_count",
                y="cumulative_first_inspection_worktime_hour",
                title="アノテーション数と1回目検査時間の累積グラフ",
                x_axis_label="入力データ数",
                y_axis_label="1回目の検査時間[hour]",
            ),
            dict(
                x="cumulative_input_data_count",
                y="cumulative_inspection_worktime_hour",
                title="入力データ数と検査時間の累積グラフ",
                x_axis_label="入力データ数",
                y_axis_label="検査時間[hour]",
            ),
        ]
        write_cumulative_graph(fig_info_list_input_data_count, html_title="累計折れ線-横軸_入力データ数-検査者用")

    def write_cumulative_line_graph_for_acceptor(
        self, df: pd.DataFrame, first_acceptance_user_id_list: Optional[List[str]] = None,
    ):
        """
        受入者用の累積折れ線グラフを出力する。

        Args:
            df:
            first_acceptance_user_id_list: 最初の検査フェーズを担当したuser_idのList. Noneの場合はtask_dfから決まる。

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
                    figure(
                        plot_width=1200,
                        plot_height=600,
                        title=fig_info["title"],
                        x_axis_label=fig_info["x_axis_label"],
                        y_axis_label=fig_info["y_axis_label"],
                    )
                )

            for user_index, user_id in enumerate(first_acceptance_user_id_list):  # type: ignore
                filtered_df = df[df["first_acceptance_user_id"] == user_id]
                if filtered_df.empty:
                    logger.debug(f"dataframe is empty. user_id = {user_id}")
                    continue

                # 列が多すぎるとbokehのグラフが表示されないので絞り込む
                columns = tooltip_item + [
                    "cumulative_annotation_count",
                    "cumulative_input_data_count",
                    "cumulative_task_count",
                    "cumulative_first_acceptance_worktime_hour",
                    "cumulative_acceptance_worktime_hour",
                    "cumulative_inspection_count",
                ]

                filtered_df = filtered_df[columns]
                source = ColumnDataSource(data=filtered_df)
                color = self.my_palette[user_index]
                username = filtered_df.iloc[0]["first_acceptance_username"]

                for fig, fig_info in zip(figs, fig_info_list):
                    self._plot_line_and_circle(
                        fig, x=fig_info["x"], y=fig_info["y"], source=source, username=username, color=color,
                    )

            hover_tool = self._create_hover_tool(tooltip_item)
            for fig in figs:
                self._set_legend(fig, hover_tool)

            bokeh.plotting.reset_output()
            bokeh.plotting.output_file(
                f"{self.outdir}/html/{self.short_project_id}-{html_title}.html", title=html_title,
            )
            bokeh.plotting.save(bokeh.layouts.column(figs))

        tooltip_item = [
            "task_id",
            "phase",
            "status",
            "first_annotation_username",
            "first_annotation_started_datetime",
            "first_inspection_username",
            "first_inspection_started_datetime",
            "first_acceptance_username",
            "first_acceptance_started_datetime",
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

        first_acceptance_user_id_list = self.create_user_id_list(
            df, "first_acceptance_user_id", first_acceptance_user_id_list
        )

        if len(first_acceptance_user_id_list) == 0:
            logger.info(f"受入フェーズを担当してユーザがいないため、受入者用のグラフは出力しません。")
            return

        logger.debug(f"グラフに表示するuser_id = {first_acceptance_user_id_list}")

        # 横軸が累計のアノテーション数
        fig_info_list_annotation_count = [
            dict(
                x="cumulative_annotation_count",
                y="cumulative_first_acceptance_worktime_hour",
                title="アノテーション数と1回目受入時間の累積グラフ",
                x_axis_label="アノテーション数",
                y_axis_label="1回目の受入時間[hour]",
            ),
            dict(
                x="cumulative_annotation_count",
                y="cumulative_acceptance_worktime_hour",
                title="アノテーション数と受入時間の累積グラフ",
                x_axis_label="アノテーション数",
                y_axis_label="受入時間[hour]",
            ),
            dict(
                x="cumulative_inspection_count",
                y="cumulative_first_acceptance_worktime_hour",
                title="検査コメント数と1回目受入時間の累積グラフ",
                x_axis_label="検査コメント数",
                y_axis_label="1回目の受入時間[hour]",
            ),
            dict(
                x="cumulative_inspection_count",
                y="cumulative_acceptance_worktime_hour",
                title="検査コメント数と受入時間の累積グラフ",
                x_axis_label="検査コメント数",
                y_axis_label="受入時間[hour]",
            ),
        ]
        write_cumulative_graph(fig_info_list_annotation_count, html_title="累計折れ線-横軸_アノテーション数-受入者用")

        # 横軸が累計の入力データ数
        fig_info_list_input_data_count = [
            dict(
                x="cumulative_input_data_count",
                y="cumulative_first_acceptance_worktime_hour",
                title="アノテーション数と1回目受入時間の累積グラフ",
                x_axis_label="入力データ数",
                y_axis_label="1回目の受入時間[hour]",
            ),
            dict(
                x="cumulative_input_data_count",
                y="cumulative_acceptance_worktime_hour",
                title="入力データ数と受入時間の累積グラフ",
                x_axis_label="入力データ数",
                y_axis_label="受入時間[hour]",
            ),
        ]
        write_cumulative_graph(fig_info_list_input_data_count, html_title="累計折れ線-横軸_入力データ数-受入者用")
