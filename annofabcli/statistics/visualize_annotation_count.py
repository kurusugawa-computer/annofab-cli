from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any, List, Optional

import annofabapi
import bokeh
import numpy
import pandas
from bokeh.models import HoverTool
from bokeh.plotting import ColumnDataSource, figure

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.statistics.list_annotation_count import AnnotationCounterByInputData, GroupBy

logger = logging.getLogger(__name__)


def create_hover_tool(tool_tip_items: Optional[List[str]] = None) -> HoverTool:
    """
    HoverTool用のオブジェクトを生成する。
    """
    if tool_tip_items is None:
        tool_tip_items = []

    detail_tooltips = [(e, f"@{{{e}}}") for e in tool_tip_items]
    hover_tool = HoverTool(tooltips=[("index", "$index"), ("(x,y)", "($x, $y)")] + detail_tooltips)
    return hover_tool


class VisualizeAnnotationCountMain:
    def __init__(self, service: annofabapi.Resource):
        self.service = service

    @classmethod
    def plot_label_histogram_by_input_data(
        cls,
        counter_list: list[AnnotationCounterByInputData],
        output_file: Path,
        target_labels: Optional[list[Any]] = None,
    ):
        # 正規分布に基づく1000個の数値の要素からなる配列

        df = pandas.DataFrame([e.labels_counter for e in counter_list])
        if target_labels is not None:
            df = df[target_labels]
        df.fillna(0, inplace=True)

        figure_list = []

        for col in df.columns[0:1]:
            # numpy.histogramで20のビンに分割
            hist, bin_edges = numpy.histogram(df[col], 20)

            df_histogram = pandas.DataFrame({"frequency ": hist, "left": bin_edges[:-1], "right": bin_edges[1:]})
            df_histogram["bottom"] = 0
            df_histogram["interval"] = [
                "%d to %d" % (left, right) for left, right in zip(df_histogram["left"], df_histogram["right"])
            ]

            print(df_histogram)
            source = ColumnDataSource(df_histogram)
            fig = figure(
                plot_width=500,
                plot_height=500,
                title=col,
                x_axis_label="アノテーション数",
                y_axis_label="入力データ数",
            )

            hover = HoverTool(tooltips=[("interval", "@interval"), ("frequency", "@frequency")])

            fig.quad(source=source, top="frequency", bottom="bottom", left="left", right="right")
            # fig.add_tools(hover)
            figure_list.append(fig)

        bokeh_obj = bokeh.layouts.gridplot(figure_list, ncols=4, merge_tools=False)
        output_file.parent.mkdir(exist_ok=True, parents=True)
        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=output_file.stem)
        bokeh.plotting.save(bokeh_obj)


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    parser.add_argument(
        "--annotation", type=str, help="アノテーションzip、またはzipを展開したディレクトリを指定します。" "指定しない場合はAnnoFabからダウンロードします。"
    )
    parser.add_argument("-o", "--output_dir", type=str, required=True, help="出力ディレクトリのパス")

    parser.add_argument(
        "--group_by",
        type=str,
        choices=[GroupBy.TASK_ID.value, GroupBy.INPUT_DATA_ID.value],
        default=GroupBy.TASK_ID.value,
        help="アノテーションの個数をどの単位で集約するかを指定してます。デフォルトは'task_id'です。",
    )

    parser.add_argument(
        "-tq",
        "--task_query",
        type=str,
        help="集計対象タスクを絞り込むためのクエリ条件をJSON形式で指定します。使用できるキーは task_id, status, phase, phase_stage です。"
        " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
    )
    argument_parser.add_task_id(required=False)

    parser.add_argument(
        "--latest",
        action="store_true",
        help="'--annotation'を指定しないとき、最新のアノテーションzipを参照します。このオプションを指定すると、アノテーションzipを更新するのに数分待ちます。",
    )

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAnnotationCount(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "visualize_annotation_count"
    subcommand_help = "各ラベル、各属性値のアノテーション数をヒストグラムで可視化します。"
    description = "各ラベル、各属性値のアノテーション数をヒストグラムで可視化します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
