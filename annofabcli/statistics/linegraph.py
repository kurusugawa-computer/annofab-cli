# pylint: disable=too-many-lines
import logging
from pathlib import Path
from typing import Dict, List, Optional

import bokeh
import bokeh.layouts
import bokeh.palettes
import dateutil
import pandas
from bokeh.core.properties import Color
from bokeh.models import HoverTool
from bokeh.plotting import ColumnDataSource, figure

logger = logging.getLogger(__name__)


class LineGraph:
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

    def __init__(self, outdir: str):
        self.line_graph_outdir = outdir
        Path(self.line_graph_outdir).mkdir(exist_ok=True, parents=True)

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
    def _plot_moving_average(
        fig: bokeh.plotting.Figure,
        source: ColumnDataSource,
        x_column_name: str,
        y_column_name: str,
        legend_label: str,
        color: Color,
    ) -> None:
        """
        移動平均用にプロットする

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
            line_dash="dashed",
            line_alpha=0.6,
            muted_alpha=0.2,
            muted_color=color,
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

    def create_user_id_list(
        self,
        df: pandas.DataFrame,
        user_id_column: str,
        datetime_column: str,
        arg_user_id_list: Optional[List[str]] = None,
    ) -> List[str]:
        """
        グラフに表示するユーザのuser_idを生成する。

        Args:
            df:
            user_id_column: user_idが格納されている列の名前
            datetime_column: 日時列の降順でソートする
            arg_first_annotation_user_id_list: 指定されたuser_idのList

        Returns:
            グラフに表示するユーザのuser_idのList

        """
        max_user_length = len(self.my_palette)
        tmp_user_id_list: List[str] = df.sort_values(by=datetime_column, ascending=False)[
            user_id_column
        ].dropna().unique().tolist()

        if arg_user_id_list is None or len(arg_user_id_list) == 0:
            user_id_list = tmp_user_id_list
        else:
            user_id_list = [user_id for user_id in tmp_user_id_list if user_id in arg_user_id_list]

        if len(user_id_list) > max_user_length:
            logger.info(f"表示対象のuser_idの数が多いため、先頭から{max_user_length}個のみグラフ化します")

        return user_id_list[0:max_user_length]

    def write_productivity_line_graph_for_annotator(
        self, df: pandas.DataFrame, first_annotation_user_id_list: Optional[List[str]] = None,
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
            output_file = f"{self.line_graph_outdir}/{html_title}.html"
            logger.debug(f"{output_file} を出力します。")

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
                        fig,
                        x_column_name=fig_info["x"],
                        y_column_name=fig_info["y"],
                        source=source,
                        legend_label=username,
                        color=color,
                    )

            hover_tool = self._create_hover_tool(tooltip_item)
            for fig in figs:
                self._set_legend(fig, hover_tool)

            bokeh.plotting.reset_output()
            bokeh.plotting.output_file(output_file, title=html_title)
            bokeh.plotting.save(bokeh.layouts.column(figs))

        tooltip_item = [
            "first_annotation_user_id",
            "first_annotation_username",
            "first_annotation_started_datetime",
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
            df,
            "first_annotation_user_id",
            datetime_column="first_annotation_started_date",
            arg_user_id_list=first_annotation_user_id_list,
        )
        logger.debug(f"教師付者用の折れ線グラフに表示する、教師付者のuser_id = {first_annotation_user_id_list}")

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
        self, df: pandas.DataFrame, first_annotation_user_id_list: Optional[List[str]] = None,
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
            output_file = f"{self.line_graph_outdir}/{html_title}.html"
            logger.debug(f"{output_file} を出力します。")

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

                source = ColumnDataSource(data=filtered_df)
                color = self.my_palette[user_index]
                username = filtered_df.iloc[0]["first_annotation_username"]

                for fig, fig_info in zip(figs, fig_info_list):
                    self._plot_line_and_circle(
                        fig,
                        x_column_name=fig_info["x"],
                        y_column_name=fig_info["y"],
                        source=source,
                        legend_label=username,
                        color=color,
                    )

            hover_tool = self._create_hover_tool(tooltip_item)
            for fig in figs:
                self._set_legend(fig, hover_tool)

            bokeh.plotting.reset_output()
            bokeh.plotting.output_file(output_file, title=html_title)
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
            df,
            "first_annotation_user_id",
            datetime_column="first_annotation_started_datetime",
            arg_user_id_list=first_annotation_user_id_list,
        )
        logger.debug(f"教師付者用の累積折れ線グラフに表示する、教師付者のuser_id = {first_annotation_user_id_list}")

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
                y="cumulative_first_annotation_worktime_hour",
                title="アノテーション数と1回目の教師付時間の累積グラフ",
                x_axis_label="アノテーション数",
                y_axis_label="1回目の教師付時間[hour]",
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
        write_cumulative_graph(fig_info_list_annotation_count, html_title="累積折れ線-横軸_アノテーション数-教師付者用")

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
        write_cumulative_graph(fig_info_list_input_data_count, html_title="累積折れ線-横軸_入力データ数-教師付者用")

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
                title="タスク数と差し戻し回数の累積グラフ",
                x_axis_label="タスク数",
                y_axis_label="差し戻し回数",
            ),
            dict(
                x="cumulative_task_count",
                y="cumulative_number_of_rejections_by_inspection",
                title="タスク数と差し戻し回数(検査フェーズ)の累積グラフ",
                x_axis_label="タスク数",
                y_axis_label="差し戻し回数(検査フェーズ)",
            ),
            dict(
                x="cumulative_task_count",
                y="cumulative_number_of_rejections_by_acceptance",
                title="タスク数と差し戻し回数(受入フェーズ)の累積グラフ",
                x_axis_label="タスク数",
                y_axis_label="差し戻し回数(受入フェーズ)",
            ),
        ]
        write_cumulative_graph(fig_info_list_task_count, html_title="累積折れ線-横軸_タスク数-教師付者用")

    def write_cumulative_line_graph_for_inspector(
        self, df: pandas.DataFrame, first_inspection_user_id_list: Optional[List[str]] = None,
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
            output_file = f"{self.line_graph_outdir}/{html_title}.html"
            logger.debug(f"{output_file} を出力します。")

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

                source = ColumnDataSource(data=filtered_df)
                color = self.my_palette[user_index]
                username = filtered_df.iloc[0]["first_inspection_username"]

                for fig, fig_info in zip(figs, fig_info_list):
                    self._plot_line_and_circle(
                        fig,
                        x_column_name=fig_info["x"],
                        y_column_name=fig_info["y"],
                        source=source,
                        legend_label=username,
                        color=color,
                    )

            hover_tool = self._create_hover_tool(tooltip_item)
            for fig in figs:
                self._set_legend(fig, hover_tool)

            bokeh.plotting.reset_output()
            bokeh.plotting.output_file(output_file, title=html_title)
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
            df,
            "first_inspection_user_id",
            datetime_column="first_inspection_started_datetime",
            arg_user_id_list=first_inspection_user_id_list,
        )

        if len(first_inspection_user_id_list) == 0:
            logger.info(f"検査フェーズを担当してユーザがいないため、検査者用のグラフは出力しません。")
            return

        logger.debug(f"検査者用の累積折れ線グラフに表示する、検査者のuser_id = {first_inspection_user_id_list}")

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
        write_cumulative_graph(fig_info_list_annotation_count, html_title="累積折れ線-横軸_アノテーション数-検査者用")

        # 横軸が累計の入力データ数
        fig_info_list_input_data_count = [
            dict(
                x="cumulative_input_data_count",
                y="cumulative_first_inspection_worktime_hour",
                title="入力データ数と1回目検査時間の累積グラフ",
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
        write_cumulative_graph(fig_info_list_input_data_count, html_title="累積折れ線-横軸_入力データ数-検査者用")

    def write_cumulative_line_graph_for_acceptor(
        self, df: pandas.DataFrame, first_acceptance_user_id_list: Optional[List[str]] = None,
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
            output_file = f"{self.line_graph_outdir}/{html_title}.html"
            logger.debug(f"{output_file} を出力します。")

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

                source = ColumnDataSource(data=filtered_df)
                color = self.my_palette[user_index]
                username = filtered_df.iloc[0]["first_acceptance_username"]

                for fig, fig_info in zip(figs, fig_info_list):
                    self._plot_line_and_circle(
                        fig,
                        x_column_name=fig_info["x"],
                        y_column_name=fig_info["y"],
                        source=source,
                        legend_label=username,
                        color=color,
                    )

            hover_tool = self._create_hover_tool(tooltip_item)
            for fig in figs:
                self._set_legend(fig, hover_tool)

            bokeh.plotting.reset_output()
            bokeh.plotting.output_file(output_file, title=html_title)
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
            df,
            "first_acceptance_user_id",
            datetime_column="first_acceptance_started_datetime",
            arg_user_id_list=first_acceptance_user_id_list,
        )

        if len(first_acceptance_user_id_list) == 0:
            logger.info(f"受入フェーズを担当してユーザがいないため、受入者用のグラフは出力しません。")
            return

        logger.debug(f"受入者用の累積折れ線グラフに表示する、受入者のuser_id = {first_acceptance_user_id_list}")

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
        write_cumulative_graph(fig_info_list_annotation_count, html_title="累積折れ線-横軸_アノテーション数-受入者用")

        # 横軸が累計の入力データ数
        fig_info_list_input_data_count = [
            dict(
                x="cumulative_input_data_count",
                y="cumulative_first_acceptance_worktime_hour",
                title="入力データ数と1回目受入時間の累積グラフ",
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
        write_cumulative_graph(fig_info_list_input_data_count, html_title="累積折れ線-横軸_入力データ数-受入者用")

    def write_cumulative_line_graph_by_date(
        self, df: pandas.DataFrame, user_id_list: Optional[List[str]] = None
    ) -> None:
        """
        ユーザごとの作業時間を、日単位でプロットする。

        Args:
            user_id_list: プロットするユーザのuser_id


        """
        tooltip_item = [
            "user_id",
            "username",
            "date",
            "worktime_hour",
        ]

        if len(df) == 0:
            logger.info("データが0件のため出力ません。")
            return

        html_title = "累積折れ線-横軸_日-縦軸_作業時間"
        output_file = f"{self.line_graph_outdir}/{html_title}.html"

        user_id_list = self.create_user_id_list(df, "user_id", datetime_column="date", arg_user_id_list=user_id_list)
        if len(user_id_list) == 0:
            logger.info(f"作業しているユーザがいないため、{html_title} グラフは出力しません。")
            return

        logger.debug(f"{html_title} グラフに表示するユーザのuser_id = {user_id_list}")

        # 日付変換
        df["date_date"] = df["date"].map(lambda e: dateutil.parser.parse(e).date())

        fig_info_list = [
            dict(
                x="date_date",
                y="cumulative_worktime_hour",
                title="累積作業時間",
                x_axis_label="日",
                y_axis_label="作業時間[hour]",
            )
        ]

        logger.debug(f"{output_file} を出力します。")

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

        for user_index, user_id in enumerate(user_id_list):  # type: ignore
            filtered_df = df[df["user_id"] == user_id]
            if filtered_df.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            source = ColumnDataSource(data=filtered_df)
            color = self.my_palette[user_index]
            username = filtered_df.iloc[0]["username"]

            for fig, fig_info in zip(figs, fig_info_list):
                self._plot_line_and_circle(
                    fig,
                    x_column_name=fig_info["x"],
                    y_column_name=fig_info["y"],
                    source=source,
                    legend_label=username,
                    color=color,
                )

        hover_tool = self._create_hover_tool(tooltip_item)
        for fig in figs:
            self._set_legend(fig, hover_tool)

        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=html_title)
        bokeh.plotting.save(bokeh.layouts.column(figs))

    def write_cumulative_line_graph_overall(self, df: pandas.DataFrame) -> None:
        """
        プロジェクト全体に対して、累積作業時間の折れ線グラフを出力する。

        Args:
            df: タスク一覧のDataFrame
        """

        tooltip_item = [
            "task_id",
            "phase",
            "status",
            "first_annotation_started_datetime",
            "updated_datetime",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
            "sum_worktime_hour",
            "annotation_count",
            "input_data_count",
            "inspection_count",
        ]
        if len(df) == 0:
            logger.info("データが0件のため出力ません。")
            return

        html_title = "累積折れ線-横軸_アノテーション数-縦軸_作業時間-全体"
        output_file = f"{self.line_graph_outdir}/{html_title}.html"

        logger.debug(f"{output_file} を出力します。")

        fig = figure(
            plot_width=1200,
            plot_height=600,
            title="アノテーション数と作業時間の累積グラフ",
            x_axis_label="アノテーション数",
            y_axis_label="作業時間[hour]",
        )

        fig_info_list = [
            dict(x="cumulative_annotation_count", y="cumulative_sum_worktime_hour", legend_label="sum"),
            dict(x="cumulative_annotation_count", y="cumulative_annotation_worktime_hour", legend_label="annotation"),
            dict(x="cumulative_annotation_count", y="cumulative_inspection_worktime_hour", legend_label="inspection"),
            dict(x="cumulative_annotation_count", y="cumulative_acceptance_worktime_hour", legend_label="acceptance"),
        ]

        source = ColumnDataSource(data=df)

        for index, fig_info in enumerate(fig_info_list):
            color = self.my_palette[index]

            self._plot_line_and_circle(
                fig,
                x_column_name=fig_info["x"],
                y_column_name=fig_info["y"],
                source=source,
                legend_label=fig_info["legend_label"],
                color=color,
            )
        hover_tool = self._create_hover_tool(tooltip_item)
        self._set_legend(fig, hover_tool)

        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=html_title)
        bokeh.plotting.save(bokeh.layouts.column([fig]))

    def write_whole_productivity_line_graph(self, df: pandas.DataFrame):
        """
        全体の生産量や生産性をプロットする


        Args:
            df:

        Returns:

        """

        def create_figure(title: str, y_axis_label: str) -> bokeh.plotting.Figure:
            return figure(
                plot_width=1200,
                plot_height=600,
                title=title,
                x_axis_label="日",
                x_axis_type="datetime",
                y_axis_label=y_axis_label,
            )

        def plot_and_moving_average(fig, y_column_name: str, legend_name: str, source):
            x_column_name = "dt_date"
            color = self.my_palette[0]

            # 値をプロット
            self._plot_line_and_circle(
                fig,
                x_column_name=x_column_name,
                y_column_name=y_column_name,
                source=source,
                color=color,
                legend_label=legend_name,
            )

            # 移動平均をプロット
            self._plot_moving_average(
                fig,
                x_column_name=x_column_name,
                y_column_name=f"{y_column_name}__lastweek",
                source=source,
                color=color,
                legend_label=f"{legend_name}の1週間移動平均",
            )

        if len(df) == 0:
            logger.info("データが0件のため出力しない")
            return

        df["dt_date"] = df["date"].map(lambda e: dateutil.parser.parse(e).date())

        html_title = "折れ線-横軸_日-全体"
        output_file = f"{self.line_graph_outdir}/{html_title}.html"
        logger.debug(f"{output_file} を出力します。")

        fig_list = [
            create_figure(title="日ごとのタスク数", y_axis_label="タスク数"),
            create_figure(title="日ごとの入力データ数", y_axis_label="入力データ数"),
            create_figure(title="日ごとの実績作業時間", y_axis_label="実績作業時間[hour]"),
            create_figure(title="日ごとのタスクあたり実績作業時間", y_axis_label="タスクあたり実績作業時間[task/hour]"),
            create_figure(title="日ごとの入力データあたり実績作業時間", y_axis_label="入力データあたり実績作業時間[input_data/hour]"),
            create_figure(title="日ごとのアノテーションあたり実績作業時間", y_axis_label="アノテーションあたり実績作業時間[annotation/hour]"),
        ]

        fig_info_list = [
            dict(x="dt_date", y="task_count", legend_name="タスク数"),
            dict(x="dt_date", y="input_data_count", legend_name="入力データ数"),
            dict(x="dt_date", y="actual_worktime_hour", legend_name="実績作業時間"),
            dict(x="dt_date", y="actual_worktime_hour/task_count", legend_name="タスクあたり実績作業時間"),
            dict(x="dt_date", y="actual_worktime_hour/input_data_count", legend_name="入力データあたり実績作業時間"),
            dict(x="dt_date", y="actual_worktime_hour/annotation_count", legend_name="アノテーションあたり実績作業時間"),
        ]

        MOVING_WINDOW_SIZE = 7
        for column in ["task_count", "input_data_count", "actual_worktime_hour"]:
            df[f"{column}__lastweek"] = df[column].rolling(MOVING_WINDOW_SIZE).mean()

        source = ColumnDataSource(data=df)

        for fig, fig_info in zip(fig_list, fig_info_list):
            plot_and_moving_average(
                fig=fig, y_column_name=fig_info["y"], legend_name=fig_info["legend_name"], source=source,
            )

        tooltip_item = [
            "date",
            "task_count",
            "input_data_count",
            "actual_worktime_hour",
            "cumsum_task_count",
            "cumsum_input_data_count",
            "cumsum_actual_worktime_hour",
            "actual_worktime_hour/task_count",
            "actual_worktime_hour/input_data_count",
            "actual_worktime_hour/annotation_count",
        ]
        hover_tool = self._create_hover_tool(tooltip_item)
        for fig in fig_list:
            self._set_legend(fig, hover_tool)

        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=html_title)
        bokeh.plotting.save(bokeh.layouts.column(fig_list))
