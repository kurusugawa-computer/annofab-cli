from __future__ import annotations

import argparse
import collections
import logging
import sys
import tempfile
from pathlib import Path
from typing import Collection, Optional, Sequence

import bokeh
import numpy
import pandas
from annofabapi.models import ProjectMemberRole
from bokeh.models import HoverTool, Title
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
from annofabcli.statistics.histogram import get_sub_title_from_series
from annofabcli.statistics.list_annotation_count import (
    AnnotationCounter,
    AnnotationSpecs,
    AttributeNameKey,
    AttributeValueKey,
    GroupBy,
    ListAnnotationCounterByInputData,
    ListAnnotationCounterByTask,
)

logger = logging.getLogger(__name__)


def _get_y_axis_label(group_by: GroupBy) -> str:
    if group_by == GroupBy.TASK_ID:
        return "タスク数"
    elif group_by == GroupBy.INPUT_DATA_ID:
        return "入力データ数"
    else:
        raise RuntimeError(f"group_by='{group_by}'が対象外です。")


def _only_selective_attribute(columns: list[AttributeValueKey]) -> list[AttributeValueKey]:
    """
    選択肢系の属性に対応する列のみ抽出する。
    属性値の個数が多い場合、非選択肢系の属性（トラッキングIDやアノテーションリンクなど）の可能性があるため、それらを除外する。
    CSVの列数を増やしすぎないための対策。
    """
    SELECTIVE_ATTRIBUTE_VALUE_MAX_COUNT = 20
    attribute_name_list: list[AttributeNameKey] = []
    for (label, attribute_name, _) in columns:
        attribute_name_list.append((label, attribute_name))

    non_selective_attribute_names = {
        key
        for key, value in collections.Counter(attribute_name_list).items()
        if value > SELECTIVE_ATTRIBUTE_VALUE_MAX_COUNT
    }

    if len(non_selective_attribute_names) > 0:
        logger.debug(
            f"以下の属性は値の個数が{SELECTIVE_ATTRIBUTE_VALUE_MAX_COUNT}を超えていたため、集計しません。 :: " f"{non_selective_attribute_names}"
        )

    return [
        (label, attribute_name, attribute_value)
        for (label, attribute_name, attribute_value) in columns
        if (label, attribute_name) not in non_selective_attribute_names
    ]


def plot_label_histogram(
    counter_list: Sequence[AnnotationCounter],
    group_by: GroupBy,
    output_file: Path,
    *,
    prior_keys: Optional[list[str]] = None,
    bins: int = 20,
):
    """
    ラベルごとのアノテーション数のヒストグラムを出力する。

    Args:
        prior_keys: 優先して表示するcounter_listのキーlist
    """
    all_label_key_set = {key for c in counter_list for key in c.annotation_count_by_label}
    if prior_keys is not None:
        remaining_columns = sorted(all_label_key_set - set(prior_keys))
        columns = prior_keys + remaining_columns
    else:
        columns = sorted(all_label_key_set)

    df = pandas.DataFrame([e.annotation_count_by_label for e in counter_list], columns=columns)
    df.fillna(0, inplace=True)

    figure_list = []

    y_axis_label = _get_y_axis_label(group_by)

    logger.debug(f"{len(df.columns)}個のラベルごとのヒストグラムを出力します。")
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
    logger.info(f"'{output_file}'を出力しました。")


def plot_attribute_histogram(
    counter_list: Sequence[AnnotationCounter],
    group_by: GroupBy,
    output_file: Path,
    *,
    prior_keys: Optional[list[AttributeValueKey]] = None,
    bins: int = 20,
):

    all_key_set = {key for c in counter_list for key in c.annotation_count_by_attribute}
    if prior_keys is not None:
        remaining_columns = list(all_key_set - set(prior_keys))
        remaining_columns_selective_attribute = sorted(_only_selective_attribute(remaining_columns))
        columns = prior_keys + remaining_columns_selective_attribute
    else:
        remaining_columns_selective_attribute = sorted(_only_selective_attribute(list(all_key_set)))
        columns = remaining_columns_selective_attribute

    df = pandas.DataFrame([e.annotation_count_by_attribute for e in counter_list], columns=columns)
    df.fillna(0, inplace=True)

    figure_list = []
    y_axis_label = _get_y_axis_label(group_by)

    logger.debug(f"{len(df.columns)}個の属性値ごとのヒストグラムを出力します。")
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
    logger.info(f"'{output_file}'を出力しました。")


class VisualizeAnnotationCount(AbstractCommandLineInterface):
    COMMON_MESSAGE = "annofabcli statistics list_annotation_count: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.project_id is None and args.annotation is None:
            print(
                f"{self.COMMON_MESSAGE} argument --project_id: '--annotation'が未指定のときは、'--project_id' を指定してください。",  # noqa: E501
                file=sys.stderr,
            )
            return False

        return True

    def visualize_annotation_count(
        self,
        group_by: GroupBy,
        annotation_path: Path,
        output_dir: Path,
        bins: int,
        *,
        project_id: Optional[str] = None,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
    ):
        labels_count_html = output_dir / "labels_count.html"
        attributes_count_html = output_dir / "attributes_count.html"

        # 集計対象の属性を、選択肢系の属性にする
        annotation_specs: Optional[AnnotationSpecs] = None
        non_selective_attribute_name_keys: Optional[list[AttributeNameKey]] = None
        if project_id is not None:
            annotation_specs = AnnotationSpecs(self.service, project_id)
            non_selective_attribute_name_keys = annotation_specs.non_selective_attribute_name_keys()

        counter_list: Sequence[AnnotationCounter] = []
        if group_by == GroupBy.INPUT_DATA_ID:
            counter_list = ListAnnotationCounterByInputData(
                non_target_attribute_names=non_selective_attribute_name_keys,
            ).get_annotation_counter_list(
                annotation_path,
                target_task_ids=target_task_ids,
                task_query=task_query,
            )

        elif group_by == GroupBy.TASK_ID:
            counter_list = ListAnnotationCounterByTask(
                non_target_attribute_names=non_selective_attribute_name_keys,
            ).get_annotation_counter_list(
                annotation_path,
                target_task_ids=target_task_ids,
                task_query=task_query,
            )

        else:
            raise RuntimeError(f"group_by='{group_by}'が対象外です。")

        label_keys: Optional[list[str]] = None
        attribute_value_keys: Optional[list[AttributeValueKey]] = None
        if annotation_specs is not None:
            label_keys = annotation_specs.label_keys()
            attribute_value_keys = annotation_specs.selective_attribute_value_keys()

        plot_label_histogram(
            counter_list, group_by=group_by, output_file=labels_count_html, bins=bins, prior_keys=label_keys
        )
        plot_attribute_histogram(
            counter_list,
            group_by=group_by,
            output_file=attributes_count_html,
            bins=bins,
            prior_keys=attribute_value_keys,
        )

    def main(self):
        args = self.args

        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id: Optional[str] = args.project_id
        if project_id is not None:
            super().validate_project(
                project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER]
            )

        output_dir: Path = args.output_dir
        annotation_path = Path(args.annotation) if args.annotation is not None else None

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = (
            TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query))
            if args.task_query is not None
            else None
        )

        group_by = GroupBy(args.group_by)

        if annotation_path is None:
            assert project_id is not None
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
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog
    )
    parse_args(parser)
    return parser
