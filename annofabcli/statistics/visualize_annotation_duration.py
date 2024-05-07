from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from collections import defaultdict
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Collection, Optional, Sequence

import bokeh
import numpy
import pandas
from annofabapi.models import DefaultAnnotationType, InputDataType, ProjectMemberRole
from bokeh.models import HoverTool
from bokeh.models.annotations.labels import Title
from bokeh.plotting import ColumnDataSource, figure

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.download import DownloadingFile
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery
from annofabcli.statistics.histogram import get_bin_edges, get_sub_title_from_series
from annofabcli.statistics.list_annotation_duration import (
    AnnotationDuration,
    AnnotationSpecs,
    AttributeNameKey,
    AttributeValueKey,
    ListAnnotationDurationByInputData,
)
from annofabcli.statistics.visualize_annotation_count import convert_to_2d_figure_list, get_only_selective_attribute

logger = logging.getLogger(__name__)

BIN_COUNT = 20


class TimeUnit(Enum):
    SECOND = "second"
    MINUTE = "minute"


def plot_annotation_duration_histogram_by_label(
    annotation_duration_list: list[AnnotationDuration],
    output_file: Path,
    *,
    time_unit: TimeUnit,
    bin_width: Optional[float] = None,
    prior_keys: Optional[list[str]] = None,
    exclude_empty_value: bool = False,
    arrange_bin_edge: bool = False,
) -> None:
    """
    ラベルごとの区間アノテーションの長さのヒストグラムを出力します。

    Args:
        time_unit: ヒストグラムに表示する時間の単位
        prior_keys: 優先して表示するcounter_listのキーlist
        exclude_empty_value: Trueならば、すべての値が0である列のヒストグラムは描画しません。
        arrange_bin_edge: Trueならば、ヒストグラムの範囲をすべてのヒストグラムで一致させます。
    """

    all_label_key_set = {key for c in annotation_duration_list for key in c.annotation_duration_second_by_label.keys()}
    if prior_keys is not None:
        remaining_columns = sorted(all_label_key_set - set(prior_keys))
        columns = prior_keys + remaining_columns
    else:
        columns = sorted(all_label_key_set)

    df = pandas.DataFrame([e.annotation_duration_second_by_label for e in annotation_duration_list], columns=columns)
    df.fillna(0, inplace=True)
    if time_unit == TimeUnit.MINUTE:
        df = df / 60

    figure_list = []

    max_duration = df.max(numeric_only=True).max()
    if arrange_bin_edge:
        histogram_range = (
            df.min(numeric_only=True).min(),
            max_duration,
        )
    else:
        histogram_range = None

    if exclude_empty_value:
        # すべての値が0である列を除外する
        columns = [col for col in df.columns if df[col].sum() > 0]
        if len(columns) < len(df.columns):
            logger.debug(
                f"以下の属性値は、すべてのタスクで区間アノテーションの長さが0であるためヒストグラムを描画しません。 :: "
                f"{set(df.columns) - set(columns)}"
            )
    else:
        columns = df.columns

    if bin_width is not None:
        if time_unit == TimeUnit.MINUTE:
            bin_width = bin_width / 60

    x_axis_label = "区間アノテーションの長さ[分]" if time_unit == TimeUnit.MINUTE else "区間アノテーションの長さ[秒]"

    logger.debug(f"{len(df.columns)}個のラベルごとのヒストグラムを出力します。")
    for col in columns:
        if bin_width is not None:
            if arrange_bin_edge:
                bin_edges = get_bin_edges(min_value=0, max_value=max_duration, bin_width=bin_width)
            else:
                bin_edges = get_bin_edges(min_value=0, max_value=df[col].max(), bin_width=bin_width)

            hist, bin_edges = numpy.histogram(df[col], bins=bin_edges, range=histogram_range)
        else:
            hist, bin_edges = numpy.histogram(df[col], bins=BIN_COUNT, range=histogram_range)

        df_histogram = pandas.DataFrame({"frequency": hist, "left": bin_edges[:-1], "right": bin_edges[1:]})
        df_histogram["interval"] = [f"{left:.1f} to {right:.1f}" for left, right in zip(df_histogram["left"], df_histogram["right"])]

        source = ColumnDataSource(df_histogram)
        fig = figure(
            width=400,
            height=300,
            x_axis_label=x_axis_label,
            y_axis_label="タスク数",
        )

        fig.add_layout(Title(text=get_sub_title_from_series(df[col], decimals=2), text_font_size="11px"), "above")
        fig.add_layout(Title(text=str(col)), "above")

        hover = HoverTool(tooltips=[("interval", "@interval"), ("frequency", "@frequency")])

        fig.quad(source=source, top="frequency", bottom=0, left="left", right="right", line_color="white")

        fig.add_tools(hover)
        figure_list.append(fig)

    bokeh_obj = bokeh.layouts.gridplot(figure_list, ncols=4)  # type: ignore[arg-type]
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()
    bokeh.plotting.output_file(output_file, title=output_file.stem)
    bokeh.plotting.save(bokeh_obj)
    logger.info(f"'{output_file}'を出力しました。")


def plot_annotation_duration_histogram_by_attribute(
    annotation_duration_list: Sequence[AnnotationDuration],
    output_file: Path,
    *,
    prior_keys: Optional[list[AttributeValueKey]] = None,
    bins: int = 20,
    exclude_empty_value: bool = False,
    arrange_bin_edge: bool = False,
) -> None:
    """
    属性値ごとの区間アノテーションの長さのヒストグラムを出力します。

    Args:
        prior_keys: 優先して表示するcounter_listのキーlist
        exclude_empty_value: Trueならば、すべての値が0である列のヒストグラムは生成しません。
        arrange_bin_edge: Trueならば、ヒストグラムの範囲をすべてのヒストグラムで一致させます。
    """
    all_key_set = {key for c in annotation_duration_list for key in c.annotation_duration_second_by_attribute.keys()}
    if prior_keys is not None:
        remaining_columns = list(all_key_set - set(prior_keys))
        remaining_columns_selective_attribute = sorted(get_only_selective_attribute(remaining_columns))
        columns = prior_keys + remaining_columns_selective_attribute
    else:
        remaining_columns_selective_attribute = sorted(get_only_selective_attribute(list(all_key_set)))
        columns = remaining_columns_selective_attribute

    df = pandas.DataFrame([e.annotation_duration_second_by_attribute for e in annotation_duration_list], columns=columns)
    df.fillna(0, inplace=True)

    logger.debug(f"{len(df.columns)}個の属性値ごとのヒストグラムで出力します。")

    if arrange_bin_edge:
        histogram_range = (df.min(numeric_only=True).min(), df.max(numeric_only=True).max())
    else:
        histogram_range = None

    if exclude_empty_value:
        # すべての値が0である列を除外する
        columns = [col for col in df.columns if df[col].sum() > 0]
        if len(columns) < len(df.columns):
            logger.debug(
                f"以下のラベルは、すべてのタスクで区間アノテーションの長さが0であるためヒストグラムを描画しません。 :: "
                f"{set(df.columns) - set(columns)}"
            )
    else:
        columns = df.columns

    figures_dict = defaultdict(list)
    for col in columns:
        header = (str(col[0]), str(col[1]))  # ラベル名, 属性名
        hist, bin_edges = numpy.histogram(df[col], bins=bins, range=histogram_range)

        df_histogram = pandas.DataFrame({"frequency": hist, "left": bin_edges[:-1], "right": bin_edges[1:]})
        df_histogram["interval"] = [f"{left:.1f} to {right:.1f}" for left, right in zip(df_histogram["left"], df_histogram["right"])]

        source = ColumnDataSource(df_histogram)
        fig = figure(
            width=400,
            height=300,
            x_axis_label="区間アノテーションの長さ[秒]",
            y_axis_label="タスク数",
        )
        fig.add_layout(Title(text=get_sub_title_from_series(df[col], decimals=2), text_font_size="11px"), "above")
        fig.add_layout(Title(text=f"{col[0]},{col[1]},{col[2]}"), "above")

        hover = HoverTool(tooltips=[("interval", "@interval"), ("frequency", "@frequency")])

        fig.quad(source=source, top="frequency", bottom=0, left="left", right="right", line_color="white")

        fig.add_tools(hover)

        figures_dict[header].append(fig)

    grid_layout_figures = convert_to_2d_figure_list(figures_dict)

    bokeh_obj = bokeh.layouts.gridplot(grid_layout_figures)  # type: ignore[arg-type]
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()
    bokeh.plotting.output_file(output_file, title=output_file.stem)
    bokeh.plotting.save(bokeh_obj)
    logger.info(f"'{output_file}'を出力しました。")


class VisualizeAnnotationDuration(AbstractCommandLineInterface):
    COMMON_MESSAGE = "annofabcli statistics visualize_annotation_duration: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.project_id is None and args.annotation is None:
            print(
                f"{self.COMMON_MESSAGE} argument --project_id: '--annotation'が未指定のときは、'--project_id' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def visualize_annotation_duration(
        self,
        annotation_path: Path,
        output_dir: Path,
        bins: int,
        *,
        project_id: Optional[str] = None,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
        exclude_empty_value: bool = False,
        arrange_bin_edge: bool = False,
    ) -> None:
        duration_by_label_html = output_dir / "annotation_duration_by_label.html"
        duration_by_attribute_html = output_dir / "annotation_duration_by_attribute.html"

        # 集計対象の属性を、選択肢系の属性にする
        annotation_specs: Optional[AnnotationSpecs] = None
        non_selective_attribute_name_keys: Optional[list[AttributeNameKey]] = None
        if project_id is not None:
            annotation_specs = AnnotationSpecs(self.service, project_id, annotation_type=DefaultAnnotationType.RANGE.value)
            non_selective_attribute_name_keys = annotation_specs.non_selective_attribute_name_keys()

        annotation_duration_list = ListAnnotationDurationByInputData(
            non_target_attribute_names=non_selective_attribute_name_keys,
        ).get_annotation_duration_list(
            annotation_path,
            target_task_ids=target_task_ids,
            task_query=task_query,
        )

        label_keys: Optional[list[str]] = None
        attribute_value_keys: Optional[list[AttributeValueKey]] = None
        if annotation_specs is not None:
            label_keys = annotation_specs.label_keys()
            attribute_value_keys = annotation_specs.selective_attribute_value_keys()

        plot_annotation_duration_histogram_by_label(
            annotation_duration_list,
            output_file=duration_by_label_html,
            bins=bins,
            prior_keys=label_keys,
            exclude_empty_value=exclude_empty_value,
            arrange_bin_edge=arrange_bin_edge,
        )
        plot_annotation_duration_histogram_by_attribute(
            annotation_duration_list,
            output_file=duration_by_attribute_html,
            bins=bins,
            prior_keys=attribute_value_keys,
            exclude_empty_value=exclude_empty_value,
            arrange_bin_edge=arrange_bin_edge,
        )

    def main(self) -> None:
        args = self.args

        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id: Optional[str] = args.project_id
        if project_id is not None:
            super().validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
            project, _ = self.service.api.get_project(project_id)
            if project["input_data_type"] != InputDataType.MOVIE.value:
                logger.warning(
                    f"project_id='{project_id}'であるプロジェクトは、動画プロジェクトでないので、出力される区間アノテーションの長さはすべて0秒になります。"
                )

        output_dir: Path = args.output_dir
        annotation_path = Path(args.annotation) if args.annotation is not None else None

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None

        func = partial(
            self.visualize_annotation_duration,
            project_id=project_id,
            output_dir=output_dir,
            target_task_ids=task_id_list,
            task_query=task_query,
            exclude_empty_value=args.exclude_empty_value,
            arrange_bin_edge=args.arrange_bin_edge,
        )

        if annotation_path is None:
            assert project_id is not None
            downloading_obj = DownloadingFile(self.service)
            if args.temp_dir is not None:
                annotation_path = args.temp_dir / f"{project_id}__annotation.zip"
                downloading_obj.download_annotation_zip(
                    project_id,
                    dest_path=annotation_path,
                    is_latest=args.latest,
                )
                func(annotation_path=annotation_path)
            else:
                # `NamedTemporaryFile`を使わない理由: Windowsで`PermissionError`が発生するため
                # https://qiita.com/yuji38kwmt/items/c6f50e1fc03dafdcdda0 参考
                with tempfile.TemporaryDirectory() as str_temp_dir:
                    annotation_path = Path(str_temp_dir) / f"{project_id}__annotation.zip"
                    downloading_obj.download_annotation_zip(
                        project_id,
                        dest_path=str(annotation_path),
                        is_latest=args.latest,
                    )
                    func(annotation_path=annotation_path)

        else:
            func(annotation_path=annotation_path)


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    parser.add_argument(
        "--annotation",
        type=str,
        required=False,
        help="アノテーションzip、またはzipを展開したディレクトリを指定します。" "指定しない場合はAnnofabからダウンロードします。",
    )

    parser.add_argument(
        "-p",
        "--project_id",
        type=str,
        required=False,
        help="project_id。``--annotation`` が未指定のときは必須です。``--annotation`` が指定されているときに ``--project_id`` を指定すると、アノテーション仕様を参照して、集計対象の属性やグラフの順番が決まります。",  # noqa: E501
    )

    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力先ディレクトリのパス")

    parser.add_argument(
        "--exclude_empty_value",
        action="store_true",
        help="指定すると、すべてのタスクで区間アノテーションの長さが0であるヒストグラムを描画しません。",
    )

    parser.add_argument(
        "--arrange_bin_edge",
        action="store_true",
        help="指定すると、ヒストグラムのデータの範囲とビンの幅がすべてのヒストグラムで一致します。",
    )

    parser.add_argument(
        "--bin_width",
        type=int,
        help=f"ヒストグラムのビンの幅を指定します。単位は「秒」です。指定しない場合は、ビンの個数が{BIN_COUNT}になるようにビンの幅が調整されます。",
    )

    parser.add_argument(
        "--time_unit",
        type=str,
        default=TimeUnit.SECOND.value,
        choices=[e.value for e in TimeUnit],
        help="動画の長さの時間単位を指定します。",
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
        help="``--annotation`` を指定しないとき、最新のアノテーションzipを参照します。このオプションを指定すると、アノテーションzipを更新するのに数分待ちます。",  # noqa: E501
    )

    parser.add_argument(
        "--temp_dir",
        type=Path,
        help="指定したディレクトリに、アノテーションZIPなどの一時ファイルをダウンロードします。",
    )

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    VisualizeAnnotationDuration(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "visualize_annotation_duration"
    subcommand_help = "ラベルごとまたは属性値ごとに区間アノテーションの長さをヒストグラムで可視化したファイルを出力します。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
