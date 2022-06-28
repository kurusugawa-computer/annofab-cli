from __future__ import annotations

import argparse
import logging
import tempfile
from pathlib import Path
from typing import Any, Collection, Optional, Sequence

import bokeh
import numpy
import pandas
from bokeh.models import HoverTool, Title
from bokeh.plotting import ColumnDataSource, figure

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery
from annofabcli.statistics.histogram import get_sub_title_from_series
from annofabcli.statistics.list_annotation_count import (
    AnnotationCounter,
    AttributesKey,
    GroupBy,
    ListAnnotationCounterByInputData,
    ListAnnotationCounterByTask,
    ListAnnotationCountMain,
)

logger = logging.getLogger(__name__)


def _get_y_axis_label(group_by: GroupBy) -> str:
    if group_by == GroupBy.TASK_ID:
        return "タスク数"
    elif group_by == GroupBy.INPUT_DATA_ID:
        return "入力データ数"
    else:
        raise RuntimeError(f"group_by='{group_by}'が対象外です。")


def plot_label_histogram(
    counter_list: Sequence[AnnotationCounter],
    group_by: GroupBy,
    output_file: Path,
    target_labels: Optional[list[Any]] = None,
    bins: int = 20,
):
    df = pandas.DataFrame([e.annotation_count_by_label for e in counter_list])
    if target_labels is not None:
        df = df[target_labels]
    df.fillna(0, inplace=True)

    figure_list = []

    y_axis_label = _get_y_axis_label(group_by)
    for col in df.columns:
        # numpy.histogramで20のビンに分割
        hist, bin_edges = numpy.histogram(df[col], bins)

        df_histogram = pandas.DataFrame({"frequency": hist, "left": bin_edges[:-1], "right": bin_edges[1:]})
        df_histogram["interval"] = [
            f"{left:.1f} to {right:.1f}" for left, right in zip(df_histogram["left"], df_histogram["right"])
        ]

        source = ColumnDataSource(df_histogram)
        fig = figure(
            plot_width=400,
            plot_height=300,
            x_axis_label="アノテーション数",
            y_axis_label=y_axis_label,
        )

        fig.add_layout(Title(text=get_sub_title_from_series(df[col], decimals=2), text_font_size="11px"), "above")
        fig.add_layout(Title(text=str(col)), "above")

        hover = HoverTool(tooltips=[("interval", "@interval"), ("frequency", "@frequency")])

        fig.quad(source=source, top="frequency", bottom=0, left="left", right="right", line_color="white")

        fig.add_tools(hover)
        figure_list.append(fig)

    bokeh_obj = bokeh.layouts.gridplot(figure_list, ncols=4)
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()
    bokeh.plotting.output_file(output_file, title=output_file.stem)
    bokeh.plotting.save(bokeh_obj)


def plot_attribute_histogram(
    counter_list: Sequence[AnnotationCounter],
    group_by: GroupBy,
    output_file: Path,
    target_attributes: Optional[list[AttributesKey]] = None,
    bins: int = 20,
):
    df = pandas.DataFrame([e.annotation_count_by_attribute for e in counter_list])
    if target_attributes is not None:
        df = df[target_attributes]
    df.fillna(0, inplace=True)

    figure_list = []
    y_axis_label = _get_y_axis_label(group_by)

    for col in sorted(df.columns):
        hist, bin_edges = numpy.histogram(df[col], bins)

        df_histogram = pandas.DataFrame({"frequency": hist, "left": bin_edges[:-1], "right": bin_edges[1:]})
        df_histogram["interval"] = [
            f"{left:.1f} to {right:.1f}" for left, right in zip(df_histogram["left"], df_histogram["right"])
        ]

        source = ColumnDataSource(df_histogram)
        fig = figure(
            plot_width=400,
            plot_height=300,
            x_axis_label="アノテーション数",
            y_axis_label=y_axis_label,
        )
        fig.add_layout(Title(text=get_sub_title_from_series(df[col], decimals=2), text_font_size="11px"), "above")
        fig.add_layout(Title(text=f"{col[0]},{col[1]},{col[2]}"), "above")

        hover = HoverTool(tooltips=[("interval", "@interval"), ("frequency", "@frequency")])

        fig.quad(source=source, top="frequency", bottom=0, left="left", right="right", line_color="white")

        fig.add_tools(hover)
        figure_list.append(fig)

    bokeh_obj = bokeh.layouts.gridplot(figure_list, ncols=4)
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()
    bokeh.plotting.output_file(output_file, title=output_file.stem)
    bokeh.plotting.save(bokeh_obj)


class VisualizeAnnotationCount(AbstractCommandLineInterface):
    def visualize_annotation_count(
        self,
        project_id: str,
        group_by: GroupBy,
        annotation_path: Path,
        output_dir: Path,
        bins: int,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
    ):
        labels_count_html = output_dir / "labels_count.html"
        attributes_count_html = output_dir / "attributes_count.html"

        main_obj = ListAnnotationCountMain(self.service)

        # 集計対象の属性を、選択肢系の属性にする
        _, attribute_columns = main_obj.get_target_columns(project_id)

        counter_list: Sequence[AnnotationCounter] = []
        if group_by == GroupBy.INPUT_DATA_ID:
            counter_list = ListAnnotationCounterByInputData.get_annotation_counter_list(
                annotation_path,
                target_task_ids=target_task_ids,
                task_query=task_query,
                target_attributes=attribute_columns,
            )

        elif group_by == GroupBy.TASK_ID:
            counter_list = ListAnnotationCounterByTask.get_annotation_counter_list(
                annotation_path,
                target_task_ids=target_task_ids,
                task_query=task_query,
                target_attributes=attribute_columns,
            )

        else:
            raise RuntimeError(f"group_by='{group_by}'が対象外です。")

        plot_label_histogram(counter_list, group_by=group_by, output_file=labels_count_html, bins=bins)
        if len(attribute_columns) == 0:
            logger.info(f"アノテーション仕様に集計対象の属性が定義されていないため、{attributes_count_html} は出力しません。")
        else:
            plot_attribute_histogram(counter_list, group_by=group_by, output_file=attributes_count_html, bins=bins)

    def main(self):
        args = self.args

        project_id = args.project_id
        output_dir: Path = args.output_dir
        super().validate_project(project_id, project_member_roles=None)

        annotation_path = Path(args.annotation) if args.annotation is not None else None

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = (
            TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query))
            if args.task_query is not None
            else None
        )

        group_by = GroupBy(args.group_by)

        if annotation_path is None:
            with tempfile.NamedTemporaryFile() as f:
                annotation_path = Path(f.name)
                downloading_obj = DownloadingFile(self.service)
                downloading_obj.download_annotation_zip(
                    project_id,
                    dest_path=str(annotation_path),
                    is_latest=args.latest,
                )
                self.visualize_annotation_count(
                    project_id=project_id,
                    annotation_path=annotation_path,
                    group_by=group_by,
                    output_dir=output_dir,
                    target_task_ids=task_id_list,
                    task_query=task_query,
                    bins=args.bins,
                )
        else:
            self.visualize_annotation_count(
                project_id=project_id,
                annotation_path=annotation_path,
                group_by=group_by,
                output_dir=output_dir,
                target_task_ids=task_id_list,
                task_query=task_query,
                bins=args.bins,
            )


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    parser.add_argument(
        "--annotation", type=str, help="アノテーションzip、またはzipを展開したディレクトリを指定します。" "指定しない場合はAnnofabからダウンロードします。"
    )
    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力先ディレクトリのパス")

    parser.add_argument(
        "--group_by",
        type=str,
        choices=[GroupBy.TASK_ID.value, GroupBy.INPUT_DATA_ID.value],
        default=GroupBy.TASK_ID.value,
        help="アノテーションの個数をどの単位で集約するかを指定します。",
    )

    parser.add_argument(
        "--bins",
        type=int,
        default=20,
        help="ヒストグラムのビンの数を指定します。",
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
        help="``--annotation`` を指定しないとき、最新のアノテーションzipを参照します。このオプションを指定すると、アノテーションzipを更新するのに数分待ちます。",
    )

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    VisualizeAnnotationCount(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "visualize_annotation_count"
    subcommand_help = "各ラベル、各属性値のアノテーション数をヒストグラムで可視化します。"
    description = "各ラベル、各属性値のアノテーション数をヒストグラムで可視化したファイルを出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
