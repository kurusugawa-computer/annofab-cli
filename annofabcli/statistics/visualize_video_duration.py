from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
from enum import Enum, auto
from functools import partial
from pathlib import Path
from typing import Collection, Optional, Sequence, Union

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
    build_annofabapi_resource_and_login,
)
from annofabcli.common.download import DownloadingFile
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery
from annofabcli.statistics.histogram import get_sub_title_from_series
from annofabcli.statistics.list_annotation_duration import (
    AnnotationSpecs,
    AttributeNameKey,
    AttributeValueKey,
    ListAnnotationDurationByInputData,
)

logger = logging.getLogger(__name__)


class TimeUnit(Enum):
    SECOND = auto()
    MINUTE = auto()


def plot_video_duration(
    durations_for_input_data: Sequence[float],
    durations_for_task: Sequence[float],
    output_file: Path,
    *,
    time_unit: TimeUnit = TimeUnit.SECOND,
    bin_width: Optional[float] = None,
    html_title: Optional[str]= None
) -> None:
    """
    ラベルごとの区間アノテーションの長さのヒストグラムを出力します。

    Args:
        prior_keys: 優先して表示するcounter_listのキーlist
        exclude_empty_value: Trueならば、すべての値が0である列のヒストグラムは生成しません。
        arrange_bin_edge: Trueならば、ヒストグラムの範囲をすべてのヒストグラムで一致させます。
        html_title: HTMLのタイトル。
    """

    def create_figure(durations: list[float], bins: Union[int, numpy.ndarray], title: str, x_axis_label: str, y_axis_label: str) -> figure:
        hist, bin_edges = numpy.histogram(durations, bins=bins)

        df_histogram = pandas.DataFrame({"frequency": hist, "left": bin_edges[:-1], "right": bin_edges[1:]})
        df_histogram["interval"] = [f"{left:.1f} to {right:.1f}" for left, right in zip(df_histogram["left"], df_histogram["right"])]

        source = ColumnDataSource(df_histogram)
        fig = figure(
            width=400,
            height=300,
            x_axis_label=x_axis_label,
            y_axis_label=y_axis_label,
        )

        fig.add_layout(Title(text=get_sub_title_from_series(pandas.Series(durations), decimals=2), text_font_size="11px"), "above")
        fig.add_layout(Title(text=title), "above")

        hover = HoverTool(tooltips=[("interval", "@interval"), ("frequency", "@frequency")])

        fig.quad(source=source, top="frequency", bottom=0, left="left", right="right", line_color="white")

        fig.add_tools(hover)
        return fig

    if time_unit == TimeUnit.MINUTE:
        durations_for_input_data = [duration / 60 for duration in durations_for_input_data]
        durations_for_task = [duration / 60 for duration in durations_for_task]

    if bin_width is not None:
        if time_unit == TimeUnit.MINUTE:
            bin_width = bin_width / 60

        max_duration = max(*durations_for_input_data, *durations_for_task)
        bins_sequence = numpy.arange(0, max_duration + bin_width, bin_width)
        if bins_sequence[-1] == max_duration:
            bins_sequence = numpy.append(bins_sequence, bins_sequence[-1] + bin_width)

        bins = bins_sequence
    else:
        bins = 20

    x_axis_label = "動画の長さ[分]" if time_unit == TimeUnit.MINUTE else "動画の長さ[秒]"

    figure_list = []
    figure_list.append(
        create_figure(
            durations_for_input_data, bins=bins, title="動画の長さの分布（全ての入力データ）", x_axis_label=x_axis_label, y_axis_label="入力データ数"
        )
    )
    figure_list.append(
        create_figure(durations_for_task, bins=bins, title="動画の長さの分布（タスクに含まれる入力データ）", x_axis_label=x_axis_label, y_axis_label="タスク数")
    )

    bokeh_obj = bokeh.layouts.layout(figure_list)  # type: ignore[arg-type]
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()
    bokeh.plotting.output_file(output_file, title=html_title)
    bokeh.plotting.save(bokeh_obj)
    logger.info(f"'{output_file}'を出力しました。")


def get_video_durations(input_data_json: Path, task_json: Path) -> tuple[list[float], list[float]]:
    """
    入力データの動画の長さと、タスクの動画の長さを取得する。

    Args:
        input_data_json: 入力データ全件ファイル
        task_json: タスク全件ファイル

    Returns:
        tuple[0]: 動画の長さのリスト（入力データ全件ファイル内の個数に一致する）
        tuple[1]: タスクに含まれる動画の長さのリスト（タスク全件ファイル内の個数に一致する）
    """
    with input_data_json.open(encoding="utf-8") as f:
        input_data_list = json.load(f)

    with task_json.open(encoding="utf-8") as f:
        task_list = json.load(f)

    video_durations_dict_for_input_data: dict[str, float] = {}

    for input_data in input_data_list:
        input_data_id = input_data["input_data_id"]
        duration = input_data["system_metadata"]["input_duration"]
        if duration is None:
            logger.warning(f"input_data_id='{input_data_id}' :: 'system_metadata.input_duration'がNoneです。")
        video_durations_dict_for_input_data[input_data_id] = duration

    video_durations_dict_for_task: dict[str, float] = {}
    for task in task_list:
        task_id = task["task_id"]
        first_input_data_id = task["input_data_id_list"][0]
        duration = video_durations_dict_for_input_data.get(first_input_data_id)
        if duration is None:
            logger.warning(f"task_id='{task_id}' :: input_data='{first_input_data_id}'のinput_durationがNoneです。")
        video_durations_dict_for_task[task_id] = duration

    return list(video_durations_dict_for_input_data.value()), list(video_durations_dict_for_task.value())


class VisualizeVideoDuration(AbstractCommandLineInterface):
    COMMON_MESSAGE = "annofabcli statistics visualize_video_duration: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.project_id is None and args.annotation is None:
            print(
                f"{self.COMMON_MESSAGE} argument --project_id: '--annotation'が未指定のときは、'--project_id' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def visualize_video_duration(
        self,
        input_data_json: Path,
        task_json_json: Path,
        output_html: Path,
        *,
        project_id: Optional[str] = None,
    ) -> None:

        durations_for_input_data, durations_for_task = get_video_durations(input_data_json, task_json_json)
        

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
            bins=args.bins,
            exclude_empty_value=args.exclude_empty_value,
            arrange_bin_edge=args.arrange_bin_edge,
        )

        if annotation_path is None:
            assert project_id is not None
            downloading_obj = DownloadingFile(self.service)
            if args.temp_dir is not None:
                input_data_json = args.temp_dir / f"{project_id}__input_data.json"
                downloading_obj.download_input_data_json(
                    project_id,
                    dest_path=input_data_json,
                    is_latest=args.latest,
                )
                task_json = args.temp_dir / f"{project_id}__task.json"
                downloading_obj.download_task_json(
                    project_id,
                    dest_path=task_json,
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
        "--bins",
        type=int,
        default=20,
        help="ヒストグラムのビンの数を指定します。",
    )

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
    subcommand_name = "visualize_video_duration"
    subcommand_help = "動画の長さをヒストグラムで可視化したファイルを出力します。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
