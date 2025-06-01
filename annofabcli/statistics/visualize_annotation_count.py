from __future__ import annotations

import argparse
import collections
import logging
import math
import sys
import tempfile
from collections import defaultdict
from collections.abc import Collection, Sequence
from functools import partial
from pathlib import Path
from typing import Any, Optional

import bokeh
import numpy
import pandas
from annofabapi.models import ProjectMemberRole
from bokeh.models import LayoutDOM
from bokeh.models.widgets.markups import Div
from bokeh.plotting import figure

import annofabcli
import annofabcli.common.cli
from annofabcli.common.bokeh import convert_1d_figure_list_to_2d, create_pretext_from_metadata
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.download import DownloadingFile
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery
from annofabcli.statistics.histogram import create_histogram_figure, get_bin_edges, get_sub_title_from_series
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

BIN_COUNT = 20


def _get_y_axis_label(group_by: GroupBy) -> str:
    if group_by == GroupBy.TASK_ID:
        return "タスク数"
    elif group_by == GroupBy.INPUT_DATA_ID:
        return "入力データ数"
    else:
        raise RuntimeError(f"group_by='{group_by}'が対象外です。")


def convert_to_2d_figure_list(figures_dict: dict[tuple[str, str], list[figure]], *, ncols: int = 4) -> list[list[Optional[LayoutDOM]]]:
    """
    grid layout用に2次元のfigureリストに変換する。
    """
    row_list: list[list[Optional[LayoutDOM]]] = []

    for (label_name, attribute_name), figure_list in figures_dict.items():
        row_list.append([Div(text=f"<h3>ラベル名='{label_name}', 属性名='{attribute_name}'</h3>")])

        for i in range(math.ceil(len(figure_list) / ncols)):
            start = i * ncols
            end = (i + 1) * ncols
            row: list[Optional[LayoutDOM]] = []
            row.extend(figure_list[start:end])
            if len(row) < ncols:
                row.extend([None] * (ncols - len(row)))
            row_list.append(row)

    return row_list


def get_only_selective_attribute(columns: list[AttributeValueKey]) -> list[AttributeValueKey]:
    """
    選択肢系の属性に対応する列のみ抽出する。
    属性値の個数が多い場合、非選択肢系の属性（トラッキングIDやアノテーションリンクなど）の可能性があるため、それらを除外する。
    CSVの列数を増やしすぎないための対策。
    """
    SELECTIVE_ATTRIBUTE_VALUE_MAX_COUNT = 20  # noqa: N806
    attribute_name_list: list[AttributeNameKey] = []
    for label, attribute_name, _ in columns:
        attribute_name_list.append((label, attribute_name))

    non_selective_attribute_names = {key for key, value in collections.Counter(attribute_name_list).items() if value > SELECTIVE_ATTRIBUTE_VALUE_MAX_COUNT}

    if len(non_selective_attribute_names) > 0:
        logger.debug(f"以下の属性は値の個数が{SELECTIVE_ATTRIBUTE_VALUE_MAX_COUNT}を超えていたため、集計しません。 :: {non_selective_attribute_names}")

    return [(label, attribute_name, attribute_value) for (label, attribute_name, attribute_value) in columns if (label, attribute_name) not in non_selective_attribute_names]


def plot_label_histogram(
    counter_list: Sequence[AnnotationCounter],
    group_by: GroupBy,
    output_file: Path,
    *,
    prior_keys: Optional[list[str]] = None,
    bin_width: Optional[int] = None,
    exclude_empty_value: bool = False,
    arrange_bin_edge: bool = False,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """
    ラベルごとのアノテーション数のヒストグラムを出力する。

    Args:
        prior_keys: 優先して表示するcounter_listのキーlist
        bin_width: ビンの幅
        exclude_empty_value: Trueならば、すべての値が0である列のヒストグラムを描画しません。
        arrange_bin_edge: Trueならば、ヒストグラムの範囲をすべてのヒストグラムで一致させます。
        metadata: HTMLファイルの上部に表示するメタデータです。
    """

    def create_df() -> pandas.DataFrame:
        all_label_key_set = {key for c in counter_list for key in c.annotation_count_by_label}
        if prior_keys is not None:
            remaining_columns = sorted(all_label_key_set - set(prior_keys))
            columns = prior_keys + remaining_columns
        else:
            columns = sorted(all_label_key_set)

        df = pandas.DataFrame([e.annotation_count_by_label for e in counter_list], columns=columns)
        df.fillna(0, inplace=True)
        return df

    df = create_df()

    if arrange_bin_edge:
        histogram_range = (
            df.min(numeric_only=True).min(),
            df.max(numeric_only=True).max(),
        )
    else:
        histogram_range = None

    y_axis_label = _get_y_axis_label(group_by)

    if exclude_empty_value:
        # すべての値が0である列を除外する
        columns = [col for col in df.columns if df[col].sum() > 0]
        if len(columns) < len(df.columns):
            logger.debug(f"以下のラベルは、すべてのタスクでアノテーション数が0であるためヒストグラムを描画しません。 :: {set(df.columns) - set(columns)}")
    else:
        columns = df.columns

    max_annotation_count = df.max(numeric_only=True).max()

    figure_list_2d: list[list[Optional[LayoutDOM]]] = [
        [
            Div(text="<h3>アノテーション数の分布（ラベル名ごと）</h3>"),
        ]
    ]

    if metadata is not None:
        figure_list_2d.append([create_pretext_from_metadata(metadata)])

    logger.debug(f"{len(columns)}個のラベルごとのヒストグラムが描画されたhtmlファイルを出力します。")
    histogram_list: list[figure] = []
    for col in columns:
        if bin_width is not None:
            if arrange_bin_edge:
                bin_edges = get_bin_edges(min_value=0, max_value=max_annotation_count, bin_width=bin_width)
            else:
                bin_edges = get_bin_edges(min_value=0, max_value=df[col].max(), bin_width=bin_width)

            hist, bin_edges = numpy.histogram(df[col], bins=bin_edges, range=histogram_range)
        else:
            hist, bin_edges = numpy.histogram(df[col], bins=BIN_COUNT, range=histogram_range)

        fig = create_histogram_figure(
            hist,
            bin_edges,
            x_axis_label="アノテーション数",
            y_axis_label=y_axis_label,
            title=str(col),
            sub_title=get_sub_title_from_series(df[col], decimals=2),
        )
        histogram_list.append(fig)

    figure_list_2d.extend(convert_1d_figure_list_to_2d(histogram_list))
    bokeh_obj = bokeh.layouts.gridplot(figure_list_2d)
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()

    html_title = "アノテーション数の分布（ラベル名ごと）"
    if metadata is not None and "project_title" in metadata:
        html_title = f"{html_title}({metadata['project_title']})"

    bokeh.plotting.output_file(output_file, title=html_title)
    bokeh.plotting.save(bokeh_obj)
    logger.info(f"'{output_file}'を出力しました。")


def plot_attribute_histogram(  # noqa: PLR0915
    counter_list: Sequence[AnnotationCounter],
    group_by: GroupBy,
    output_file: Path,
    *,
    prior_keys: Optional[list[AttributeValueKey]] = None,
    bin_width: Optional[int] = None,
    exclude_empty_value: bool = False,
    arrange_bin_edge: bool = False,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """
    属性値ごとのアノテーション数のヒストグラムを出力する。

    Args:
        prior_keys: 優先して表示するcounter_listのキーlist
        exclude_empty_value: Trueならば、すべての値が0である列のヒストグラムを描画しません。
        arrange_bin_edge: Trueならば、ヒストグラムの範囲をすべてのヒストグラムで一致させます。
        metadata: HTMLファイルの上部に表示するメタデータです。

    """

    def create_df() -> pandas.DataFrame:
        all_key_set = {key for c in counter_list for key in c.annotation_count_by_attribute}
        if prior_keys is not None:
            remaining_columns = list(all_key_set - set(prior_keys))
            remaining_columns_selective_attribute = sorted(get_only_selective_attribute(remaining_columns))
            columns = prior_keys + remaining_columns_selective_attribute
        else:
            remaining_columns_selective_attribute = sorted(get_only_selective_attribute(list(all_key_set)))
            columns = remaining_columns_selective_attribute

        df = pandas.DataFrame([e.annotation_count_by_attribute for e in counter_list], columns=columns)
        df.fillna(0, inplace=True)

        return df

    df = create_df()
    y_axis_label = _get_y_axis_label(group_by)

    if arrange_bin_edge:
        histogram_range = (
            df.min(numeric_only=True).min(),
            df.max(numeric_only=True).max(),
        )
    else:
        histogram_range = None

    if exclude_empty_value:
        # すべての値が0である列を除外する
        columns = [col for col in df.columns if df[col].sum() > 0]
        if len(columns) < len(df.columns):
            logger.debug(f"以下の属性値は、すべてのタスクでアノテーション数が0であるためヒストグラムを描画しません。 :: {set(df.columns) - set(columns)}")
    else:
        columns = df.columns

    max_annotation_count = df.max(numeric_only=True).max()

    figure_list_2d: list[list[Optional[LayoutDOM]]] = [
        [
            Div(text="<h3>アノテーション数の分布（属性値ごと）</h3>"),
        ]
    ]

    if metadata is not None:
        figure_list_2d.append([create_pretext_from_metadata(metadata)])

    figures_dict = defaultdict(list)
    logger.debug(f"{len(columns)}個の属性値ごとのヒストグラムが描画されたhtmlファイルを出力します。")
    for col in columns:
        header = (str(col[0]), str(col[1]))  # ラベル名, 属性名

        if bin_width is not None:
            if arrange_bin_edge:
                bin_edges = get_bin_edges(min_value=0, max_value=max_annotation_count, bin_width=bin_width)
            else:
                bin_edges = get_bin_edges(min_value=0, max_value=df[col].max(), bin_width=bin_width)

            hist, bin_edges = numpy.histogram(df[col], bins=bin_edges, range=histogram_range)
        else:
            hist, bin_edges = numpy.histogram(df[col], bins=BIN_COUNT, range=histogram_range)

        fig = create_histogram_figure(
            hist,
            bin_edges,
            x_axis_label="アノテーション数",
            y_axis_label=y_axis_label,
            title=f"{col[0]},{col[1]},{col[2]}",
            sub_title=get_sub_title_from_series(df[col], decimals=2),
        )
        figures_dict[header].append(fig)

    figure_list_2d.extend(convert_to_2d_figure_list(figures_dict))
    bokeh_obj = bokeh.layouts.gridplot(figure_list_2d)
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()
    html_title = "アノテーション数の分布（属性値ごと）"
    if metadata is not None and "project_title" in metadata:
        html_title = f"{html_title}({metadata['project_title']})"

    bokeh.plotting.output_file(output_file, title=html_title)
    bokeh.plotting.save(bokeh_obj)
    logger.info(f"'{output_file}'を出力しました。")


class VisualizeAnnotationCount(CommandLine):
    COMMON_MESSAGE = "annofabcli statistics visualize_annotation_count: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.project_id is None and args.annotation is None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --project_id: '--annotation'が未指定のときは、'--project_id' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def visualize_annotation_count(
        self,
        group_by: GroupBy,
        annotation_path: Path,
        output_dir: Path,
        *,
        bin_width: Optional[int] = None,
        project_id: Optional[str] = None,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
        exclude_empty_value: bool = False,
        arrange_bin_edge: bool = False,
    ) -> None:
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

        project_title = None
        if project_id is not None:
            project, _ = self.service.api.get_project(project_id)
            project_title = project["title"]

        metadata = {
            "project_id": project_id,
            "project_title": project_title,
            "task_query": {k: v for k, v in task_query.to_dict(encode_json=True).items() if v is not None and v is not False} if task_query is not None else None,
            "target_task_ids": target_task_ids,
        }

        plot_label_histogram(
            counter_list,
            group_by=group_by,
            output_file=labels_count_html,
            bin_width=bin_width,
            prior_keys=label_keys,
            exclude_empty_value=exclude_empty_value,
            arrange_bin_edge=arrange_bin_edge,
            metadata=metadata,
        )
        plot_attribute_histogram(
            counter_list,
            group_by=group_by,
            output_file=attributes_count_html,
            bin_width=bin_width,
            prior_keys=attribute_value_keys,
            exclude_empty_value=exclude_empty_value,
            arrange_bin_edge=arrange_bin_edge,
            metadata=metadata,
        )

    def main(self) -> None:
        args = self.args

        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id: Optional[str] = args.project_id
        if project_id is not None:
            super().validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        output_dir: Path = args.output_dir
        annotation_path = Path(args.annotation) if args.annotation is not None else None

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None

        group_by = GroupBy(args.group_by)

        func = partial(
            self.visualize_annotation_count,
            project_id=project_id,
            group_by=group_by,
            output_dir=output_dir,
            target_task_ids=task_id_list,
            task_query=task_query,
            bin_width=args.bin_width,
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
        help="アノテーションzip、またはzipを展開したディレクトリを指定します。指定しない場合はAnnofabからダウンロードします。",
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
        "--bin_width",
        type=int,
        help=f"ヒストグラムのビンの幅を指定します。指定しない場合は、ビンの個数が{BIN_COUNT}になるようにビンの幅が調整されます。",
    )

    parser.add_argument(
        "--exclude_empty_value",
        action="store_true",
        help="指定すると、すべてのタスクでアノテーション数が0であるヒストグラムを描画しません。",
    )

    parser.add_argument(
        "--arrange_bin_edge",
        action="store_true",
        help="指定すると、ヒストグラムのデータの範囲とビンの幅がすべてのヒストグラムで一致します。",
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

    parser.add_argument(
        "--temp_dir",
        type=Path,
        help="指定したディレクトリに、アノテーションZIPなどの一時ファイルをダウンロードします。",
    )

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    VisualizeAnnotationCount(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "visualize_annotation_count"
    subcommand_help = "各ラベル、各属性値のアノテーション数をヒストグラムで可視化します。"
    description = "各ラベル、各属性値のアノテーション数をヒストグラムで可視化したファイルを出力します。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog)
    parse_args(parser)
    return parser
