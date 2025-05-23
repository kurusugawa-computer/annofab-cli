from __future__ import annotations

import argparse
import datetime
import itertools
import json
import logging
import sys
import tempfile
from collections.abc import Collection, Sequence
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Optional, Union

import bokeh
import numpy
import pandas
from annofabapi.models import InputDataType, ProjectMemberRole
from bokeh.models import HoverTool, LayoutDOM
from bokeh.models.annotations.labels import Title
from bokeh.models.widgets.markups import PreText
from bokeh.plotting import ColumnDataSource, figure

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    CommandLine,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.download import DownloadingFile
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.statistics.histogram import get_sub_title_from_series

logger = logging.getLogger(__name__)

BIN_COUNT = 20


class TimeUnit(Enum):
    SECOND = "second"
    MINUTE = "minute"


def plot_video_duration(
    durations_for_input_data: Sequence[float],
    output_file: Path,
    *,
    time_unit: TimeUnit,
    bin_width: Optional[float] = None,
    project_id: Optional[str] = None,
    project_title: Optional[str] = None,
) -> None:
    """
    ラベルごとの区間アノテーションの長さのヒストグラムを出力します。

    Args:
        durations_for_input_data: 動画の長さの一覧。単位は「秒」です。
        output_file: 出力先のファイルのパス
        time_unit: ヒストグラムに表示する時間の単位
        bin_width_second: ヒストグラムのビンの幅。単位は「秒」です。
        html_title: HTMLのタイトル。
    """

    def create_figure(
        durations: Sequence[float],
        bins: Union[int, numpy.ndarray],
        histogram_range: tuple[float, float],
        title: str,
        x_axis_label: str,
        y_axis_label: str,
    ) -> figure:
        hist, bin_edges = numpy.histogram(durations, bins=bins, range=histogram_range)

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

    if bin_width is not None:
        if time_unit == TimeUnit.MINUTE:
            bin_width = bin_width / 60

        max_duration = max(durations_for_input_data)
        bins_sequence = numpy.arange(0, max_duration + bin_width, bin_width)

        if bins_sequence[-1] == max_duration:
            bins_sequence = numpy.append(bins_sequence, bins_sequence[-1] + bin_width)  # type: ignore[assignment]

        bins: Union[int, numpy.ndarray] = bins_sequence
    else:
        bins = BIN_COUNT

    x_axis_label = "動画の長さ[分]" if time_unit == TimeUnit.MINUTE else "動画の長さ[秒]"
    histogram_range = (min(durations_for_input_data), max(durations_for_input_data))

    layout_list: list[LayoutDOM] = [
        PreText(text=f"project_id='{project_id}'\nproject_title='{project_title}'"),
        create_figure(
            durations_for_input_data,
            bins=bins,
            histogram_range=histogram_range,
            title="動画の長さの分布",
            x_axis_label=x_axis_label,
            y_axis_label="動画数",
        ),
    ]

    bokeh_obj = bokeh.layouts.layout(layout_list)
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()
    title = "動画の長さの分布"
    if project_title is not None:
        title = title + f"({project_title})"
    bokeh.plotting.output_file(output_file, title=title)
    bokeh.plotting.save(bokeh_obj)
    logger.info(f"'{output_file}'を出力しました。")


def get_video_duration_list(
    input_data_json: Path,
    task_json: Path,
    *,
    input_data_ids: Optional[Collection[str]] = None,
    from_datetime: datetime.datetime | None = None,
    to_datetime: datetime.datetime | None = None,
    task_ids: Optional[Collection[str]] = None,
) -> list[float]:
    """
    入力データである動画の長さ（単位は秒）の一覧を取得します。

    Args:
        input_data_json: 入力データ全件ファイル
        task_json: タスク全件ファイル
        from_datetime: 入力データの更新日時が`from_datetime`以降のデータのみを集計対象にします。
        to_datetime: 入力データの更新日時が`from_datetime`以前のデータのみを集計対象にします。

    """
    with input_data_json.open(encoding="utf-8") as f:
        input_data_list = json.load(f)
        logger.debug(f"'{input_data_json}'に含まれる入力データは {len(input_data_list)} 件です。")

    if input_data_ids is not None:
        input_data_list = [input_data for input_data in input_data_list if input_data["input_data_id"] in input_data_ids]
        logger.debug(
            f"「入力データのinput_data_idが引数'input_data_ids'に一致する」という条件で、入力データを {len(input_data_list)} 件に絞り込みました。  :: 引数'input_data_ids'は {len(input_data_ids)} 件"
        )

    if from_datetime is not None:
        input_data_list = [input_data for input_data in input_data_list if datetime.datetime.fromisoformat(input_data["updated_datetime"]) >= from_datetime]
        logger.debug(f"「入力データの更新日時が'{from_datetime}'以降」という条件で、入力データを {len(input_data_list)} 件に絞り込みました。")

    if to_datetime is not None:
        input_data_list = [input_data for input_data in input_data_list if datetime.datetime.fromisoformat(input_data["updated_datetime"]) <= to_datetime]
        logger.debug(f"「入力データの更新日時が'{to_datetime}'以前」という条件で、入力データを {len(input_data_list)} 件に絞り込みました。")

    if task_ids is not None:
        with task_json.open(encoding="utf-8") as f:
            task_list = json.load(f)
        input_data_id_list_list = [task["input_data_id_list"] for task in task_list if task["task_id"] in task_ids]
        input_data_ids_included_task = set(itertools.chain.from_iterable(input_data_id_list_list))
        input_data_list = [input_data for input_data in input_data_list if input_data["input_data_id"] in input_data_ids_included_task]
        logger.debug(f"「引数'task_ids'に対応するタスクに含まれている入力データ」という条件で、入力データを {len(input_data_list)} 件に絞り込みました。  :: 引数'task_ids'は {len(task_ids)} 件")

    video_duration_list = []
    for input_data in input_data_list:
        input_data_id = input_data["input_data_id"]
        duration = input_data["system_metadata"]["input_duration"]
        if duration is None:
            logger.warning(f"input_data_id='{input_data_id}' :: 'system_metadata.input_duration'がNoneです。")
        video_duration_list.append(duration)

    return video_duration_list


class VisualizeVideoDuration(CommandLine):
    COMMON_MESSAGE = "annofabcli statistics visualize_video_duration: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.project_id is None and (args.input_data_json is None or args.task_json is None):
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --project_id: '--input_data_json'または'--task_json'が未指定のときは、'--project_id' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def visualize_video_duration(  # noqa: PLR0913
        self,
        input_data_json: Path,
        task_json: Path,
        output_html: Path,
        *,
        time_unit: TimeUnit,
        project_id: Optional[str] = None,
        project_title: Optional[str] = None,
        bin_width: Optional[float] = None,
        input_data_ids: Optional[Collection[str]] = None,
        task_ids: Optional[Collection[str]] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> None:
        tz_info = datetime.datetime.now().astimezone().tzinfo
        from_datetime = datetime.datetime.fromisoformat(from_date).astimezone(tz_info) if from_date is not None else None
        to_datetime = datetime.datetime.fromisoformat(to_date).astimezone(tz_info) if to_date is not None else None

        durations_for_input_data = get_video_duration_list(
            input_data_json,
            task_json,
            input_data_ids=input_data_ids,
            from_datetime=from_datetime,
            to_datetime=to_datetime,
            task_ids=task_ids,
        )

        plot_video_duration(
            durations_for_input_data,
            output_html,
            project_id=project_id,
            project_title=project_title,
            time_unit=time_unit,
            bin_width=bin_width,
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
                print(  # noqa: T201
                    f"project_id='{project_id}'であるプロジェクトは、動画プロジェクトでないので動画の長さを可視化したファイルを出力できません。終了します。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        input_data_id_set = set(get_list_from_args(args.input_data_id)) if args.input_data_id is not None else None
        task_id_set = set(get_list_from_args(args.task_id)) if args.task_id is not None else None

        func = partial(
            self.visualize_video_duration,
            project_id=project_id,
            project_title=project["title"] if project_id is not None else None,
            output_html=args.output,
            time_unit=TimeUnit(args.time_unit),
            bin_width=args.bin_width,
            input_data_ids=input_data_id_set,
            task_ids=task_id_set,
            to_date=args.to_date,
            from_date=args.from_date,
        )

        def wrapper_func(temp_dir: Path) -> None:
            downloading_obj = DownloadingFile(self.service)
            assert project_id is not None
            if args.input_data_json is None:
                input_data_json = temp_dir / f"{project_id}__input_data.json"
                downloading_obj.download_input_data_json(
                    project_id,
                    dest_path=input_data_json,
                    is_latest=args.latest,
                )
            else:
                input_data_json = args.input_data_json

            if args.task_json is None:
                task_json = temp_dir / f"{project_id}__task.json"
                downloading_obj.download_task_json(
                    project_id,
                    dest_path=task_json,
                    is_latest=args.latest,
                )
            else:
                task_json = args.task_json

            func(task_json=task_json, input_data_json=input_data_json)

        if args.input_data_json is None or args.task_json is None:
            if args.temp_dir is not None:
                wrapper_func(args.temp_dir)
            else:
                # `NamedTemporaryFile`を使わない理由: Windowsで`PermissionError`が発生するため
                # https://qiita.com/yuji38kwmt/items/c6f50e1fc03dafdcdda0 参考
                with tempfile.TemporaryDirectory() as str_temp_dir:
                    wrapper_func(Path(str_temp_dir))

        else:
            func(task_json=args.task_json, input_data_json=args.input_data_json)


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--input_data_json",
        type=Path,
        required=False,
        help="入力データ情報が記載されたJSONファイルのパスを指定します。\nJSONファイルは ``$ annofabcli input_data download`` コマンドで取得できます。",
    )

    parser.add_argument(
        "--task_json",
        type=Path,
        required=False,
        help="タスク情報が記載されたJSONファイルのパスを指定します。\nJSONファイルは ``$ annofabcli task download`` コマンドで取得できます。",
    )

    parser.add_argument(
        "-p",
        "--project_id",
        type=str,
        required=False,
        help="project_id。``--input_data_json`` と ``--task_json`` が未指定のときは必須です。",
    )

    parser.add_argument("-o", "--output", type=Path, required=True, help="出力先HTMLファイルのパス")

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
        "-t",
        "--task_id",
        nargs="+",
        help=("指定したtask_idのタスクに含まれている入力データを可視化対象にします。 ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。"),
    )

    parser.add_argument(
        "-i",
        "--input_data_id",
        nargs="+",
        help=("指定したinput_data_idである入力データを可視化対象にします。 ``file://`` を先頭に付けると、input_data_idの一覧が記載されたファイルを指定できます。"),
    )

    parser.add_argument("--from_date", type=str, help="指定した日付（ ``YYYY-MM-DD`` ）以降に更新された入力データを可視化対象にします。")
    parser.add_argument("--to_date", type=str, help="指定した日付（ ``YYYY-MM-DD`` ）以前に更新された入力データを可視化対象にします。")

    parser.add_argument(
        "--latest",
        action="store_true",
        help="入力データ情報とタスク情報の最新版を参照します。このオプションを指定すると数分待ちます。",
    )

    parser.add_argument(
        "--temp_dir",
        type=Path,
        help="指定したディレクトリに、入力データのJSONやタスクのJSONなどテンポラリファイルをダウンロードします。",
    )

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    VisualizeVideoDuration(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "visualize_video_duration"
    subcommand_help = "動画の長さをヒストグラムで可視化します。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
