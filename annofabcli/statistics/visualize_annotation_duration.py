from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from collections import defaultdict
from collections.abc import Collection, Sequence
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any, Optional

import bokeh
import numpy
import pandas
from annofabapi.models import DefaultAnnotationType, InputDataType, ProjectMemberRole
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
"""ヒストグラムのビンの個数"""


class TimeUnit(Enum):
    SECOND = "second"
    MINUTE = "minute"


def plot_annotation_duration_histogram_by_label(  # noqa: PLR0915
    annotation_duration_list: list[AnnotationDuration],
    output_file: Path,
    *,
    time_unit: TimeUnit,
    bin_width: Optional[float] = None,
    prior_keys: Optional[list[str]] = None,
    exclude_empty_value: bool = False,
    arrange_bin_edge: bool = False,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """
    ラベルごとの区間アノテーションの長さのヒストグラムを出力します。

    Args:
        time_unit: ヒストグラムに表示する時間の単位
        bin_width: ビンの幅（単位は秒）
        prior_keys: 優先して表示するcounter_listのキーlist
        exclude_empty_value: Trueならば、すべての値が0である列のヒストグラムは描画しません。
        arrange_bin_edge: Trueならば、ヒストグラムの範囲をすべてのヒストグラムで一致させます。
        metadata: HTMLファイルの上部に表示するメタデータです。
    """

    def create_df() -> pandas.DataFrame:
        all_label_key_set = {key for c in annotation_duration_list for key in c.annotation_duration_second_by_label.keys()}  # noqa: SIM118
        if prior_keys is not None:
            remaining_columns = sorted(all_label_key_set - set(prior_keys))
            columns = prior_keys + remaining_columns
        else:
            columns = sorted(all_label_key_set)

        df = pandas.DataFrame([e.annotation_duration_second_by_label for e in annotation_duration_list], columns=columns)
        df.fillna(0, inplace=True)
        if time_unit == TimeUnit.MINUTE:
            df = df / 60
        return df

    def get_histogram_range(df: pandas.DataFrame) -> Optional[tuple[float, float]]:
        if arrange_bin_edge:
            return (
                df.min(numeric_only=True).min(),
                df.max(numeric_only=True).max(),
            )
        return None

    df = create_df()
    histogram_list: list[figure] = []

    max_duration = df.max(numeric_only=True).max()

    figure_list_2d: list[list[Optional[LayoutDOM]]] = [
        [
            Div(text="<h3>区間アノテーションの長さの分布（ラベル名ごと）</h3>"),
        ]
    ]

    if metadata is not None:
        figure_list_2d.append([create_pretext_from_metadata(metadata)])

    if exclude_empty_value:
        # すべての値が0である列を除外する
        columns = [col for col in df.columns if df[col].sum() > 0]
        if len(columns) < len(df.columns):
            logger.debug(f"以下の属性値は、すべてのタスクで区間アノテーションの長さが0であるためヒストグラムを描画しません。 :: {set(df.columns) - set(columns)}")
        df = df[columns]

    if bin_width is not None:  # noqa: SIM102
        if time_unit == TimeUnit.MINUTE:
            bin_width = bin_width / 60

    x_axis_label = "区間アノテーションの長さ[分]" if time_unit == TimeUnit.MINUTE else "区間アノテーションの長さ[秒]"
    histogram_range = get_histogram_range(df)

    logger.debug(f"{len(df.columns)}個のラベルごとのヒストグラムを出力します。")
    for col in df.columns:
        if bin_width is not None:
            if arrange_bin_edge:
                bin_edges = get_bin_edges(min_value=0, max_value=max_duration, bin_width=bin_width)
            else:
                bin_edges = get_bin_edges(min_value=0, max_value=df[col].max(), bin_width=bin_width)

            hist, bin_edges = numpy.histogram(df[col], bins=bin_edges, range=histogram_range)
        else:
            hist, bin_edges = numpy.histogram(df[col], bins=BIN_COUNT, range=histogram_range)

        fig = create_histogram_figure(
            hist,
            bin_edges,
            x_axis_label=x_axis_label,
            y_axis_label="タスク数",
            title=str(col),
            sub_title=get_sub_title_from_series(df[col], decimals=2),
        )
        histogram_list.append(fig)

    figure_list_2d.extend(convert_1d_figure_list_to_2d(histogram_list))

    bokeh_obj = bokeh.layouts.gridplot(figure_list_2d)
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()
    html_title = "区間アノテーションの長さの分布（ラベル名ごと）"
    if metadata is not None and "project_title" in metadata:
        html_title = f"{html_title}({metadata['project_title']})"

    bokeh.plotting.output_file(output_file, title=html_title)
    bokeh.plotting.save(bokeh_obj)
    logger.info(f"'{output_file}'を出力しました。")


def plot_annotation_duration_histogram_by_attribute(  # noqa: PLR0915
    annotation_duration_list: Sequence[AnnotationDuration],
    output_file: Path,
    *,
    time_unit: TimeUnit,
    bin_width: Optional[float] = None,
    prior_keys: Optional[list[AttributeValueKey]] = None,
    exclude_empty_value: bool = False,
    arrange_bin_edge: bool = False,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """
    属性値ごとの区間アノテーションの長さのヒストグラムを出力します。

    Args:
        bin_width: ビンの幅（単位は秒）
        prior_keys: 優先して表示するcounter_listのキーlist
        exclude_empty_value: Trueならば、すべての値が0である列のヒストグラムは生成しません。
        arrange_bin_edge: Trueならば、ヒストグラムの範囲をすべてのヒストグラムで一致させます。
        metadata: HTMLファイルの上部に表示するメタデータです。
    """

    def create_df() -> pandas.DataFrame:
        all_key_set = {key for c in annotation_duration_list for key in c.annotation_duration_second_by_attribute.keys()}  # noqa: SIM118
        if prior_keys is not None:
            remaining_columns = list(all_key_set - set(prior_keys))
            remaining_columns_selective_attribute = sorted(get_only_selective_attribute(remaining_columns))
            columns = prior_keys + remaining_columns_selective_attribute
        else:
            remaining_columns_selective_attribute = sorted(get_only_selective_attribute(list(all_key_set)))
            columns = remaining_columns_selective_attribute

        df = pandas.DataFrame([e.annotation_duration_second_by_attribute for e in annotation_duration_list], columns=columns)
        df.fillna(0, inplace=True)
        if time_unit == TimeUnit.MINUTE:
            df = df / 60
        return df

    def get_histogram_range(df: pandas.DataFrame) -> Optional[tuple[float, float]]:
        if arrange_bin_edge:
            return (
                df.min(numeric_only=True).min(),
                df.max(numeric_only=True).max(),
            )
        return None

    df = create_df()
    logger.debug(f"{len(df.columns)}個の属性値ごとのヒストグラムで出力します。")

    if bin_width is not None:  # noqa: SIM102
        if time_unit == TimeUnit.MINUTE:
            bin_width = bin_width / 60

    if exclude_empty_value:
        # すべての値が0である列を除外する
        columns = [col for col in df.columns if df[col].sum() > 0]
        if len(columns) < len(df.columns):
            logger.debug(f"以下のラベルは、すべてのタスクで区間アノテーションの長さが0であるためヒストグラムを描画しません。 :: {set(df.columns) - set(columns)}")
        df = df[columns]

    histogram_range = get_histogram_range(df)
    max_duration = df.max(numeric_only=True).max()
    x_axis_label = "区間アノテーションの長さ[分]" if time_unit == TimeUnit.MINUTE else "区間アノテーションの長さ[秒]"

    figure_list_2d: list[list[Optional[LayoutDOM]]] = [
        [
            Div(text="<h3>区間アノテーションの長さの分布（属性値ごと）</h3>"),
        ]
    ]

    if metadata is not None:
        figure_list_2d.append([create_pretext_from_metadata(metadata)])

    figures_dict = defaultdict(list)
    for col in df.columns:
        header = (str(col[0]), str(col[1]))  # ラベル名, 属性名

        if bin_width is not None:
            if arrange_bin_edge:
                bin_edges = get_bin_edges(min_value=0, max_value=max_duration, bin_width=bin_width)
            else:
                bin_edges = get_bin_edges(min_value=0, max_value=df[col].max(), bin_width=bin_width)

            hist, bin_edges = numpy.histogram(df[col], bins=bin_edges, range=histogram_range)
        else:
            hist, bin_edges = numpy.histogram(df[col], bins=BIN_COUNT, range=histogram_range)

        fig = create_histogram_figure(
            hist,
            bin_edges,
            x_axis_label=x_axis_label,
            y_axis_label="タスク数",
            title=f"{col[0]},{col[1]},{col[2]}",
            sub_title=get_sub_title_from_series(df[col], decimals=2),
        )

        figures_dict[header].append(fig)

    figure_list_2d.extend(convert_to_2d_figure_list(figures_dict))

    bokeh_obj = bokeh.layouts.gridplot(figure_list_2d)
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()
    html_title = "区間アノテーションの長さの分布（属性値ごと）"
    if metadata is not None and "project_title" in metadata:
        html_title = f"{html_title}({metadata['project_title']})"
    bokeh.plotting.output_file(output_file, title=html_title)
    bokeh.plotting.save(bokeh_obj)
    logger.info(f"'{output_file}'を出力しました。")


class VisualizeAnnotationDuration(CommandLine):
    COMMON_MESSAGE = "annofabcli statistics visualize_annotation_duration: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.project_id is None and args.annotation is None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --project_id: '--annotation'が未指定のときは、'--project_id' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def visualize_annotation_duration(
        self,
        annotation_path: Path,
        output_dir: Path,
        time_unit: TimeUnit,
        *,
        bin_width: Optional[int] = None,
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
        plot_annotation_duration_histogram_by_label(
            annotation_duration_list,
            output_file=duration_by_label_html,
            time_unit=time_unit,
            bin_width=bin_width,
            prior_keys=label_keys,
            exclude_empty_value=exclude_empty_value,
            arrange_bin_edge=arrange_bin_edge,
            metadata=metadata,
        )
        plot_annotation_duration_histogram_by_attribute(
            annotation_duration_list,
            output_file=duration_by_attribute_html,
            time_unit=time_unit,
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
            project, _ = self.service.api.get_project(project_id)
            if project["input_data_type"] != InputDataType.MOVIE.value:
                logger.warning(f"project_id='{project_id}'であるプロジェクトは、動画プロジェクトでないので、出力される区間アノテーションの長さはすべて0秒になります。")

        output_dir: Path = args.output_dir
        annotation_path = Path(args.annotation) if args.annotation is not None else None

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None

        func = partial(
            self.visualize_annotation_duration,
            project_id=project_id,
            output_dir=output_dir,
            time_unit=TimeUnit(args.time_unit),
            bin_width=args.bin_width,
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
    VisualizeAnnotationDuration(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "visualize_annotation_duration"
    subcommand_help = "ラベルごとまたは属性値ごとに区間アノテーションの長さをヒストグラムで可視化したファイルを出力します。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
