from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from annofabapi.models import TaskPhase

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    get_json_from_args,
    get_list_from_args,
)
from annofabcli.common.utils import _catch_exception
from annofabcli.statistics.visualization.dataframe.cumulative_productivity import (
    AcceptorCumulativeProductivity,
    AnnotatorCumulativeProductivity,
    InspectorCumulativeProductivity,
)
from annofabcli.statistics.visualization.dataframe.productivity_per_date import (
    AcceptorProductivityPerDate,
    AnnotatorProductivityPerDate,
    InspectorProductivityPerDate,
)
from annofabcli.statistics.visualization.dataframe.task import Task
from annofabcli.statistics.visualization.dataframe.task_worktime_by_phase_user import TaskWorktimeByPhaseUser
from annofabcli.statistics.visualization.dataframe.user_performance import UserPerformance
from annofabcli.statistics.visualization.dataframe.whole_performance import WholePerformance
from annofabcli.statistics.visualization.dataframe.whole_productivity_per_date import (
    WholeProductivityPerCompletedDate,
    WholeProductivityPerFirstAnnotationStartedDate,
)
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate
from annofabcli.statistics.visualization.model import ProductionVolumeColumn, TaskCompletionCriteria
from annofabcli.statistics.visualization.project_dir import MergingInfo, ProjectDir

logger = logging.getLogger(__name__)


class WritingVisualizationFile:
    def __init__(
        self,
        output_project_dir: ProjectDir,
        task_completion_criteria: TaskCompletionCriteria,
        *,
        user_id_list: Optional[list[str]] = None,
        minimal_output: bool = False,
    ) -> None:
        self.output_project_dir = output_project_dir
        self.task_completion_criteria = task_completion_criteria
        self.user_id_list = user_id_list
        self.minimal_output = minimal_output

    @_catch_exception
    def write_user_performance(self, user_performance: UserPerformance):  # noqa: ANN201
        """ユーザごとの生産性と品質に関するファイルを出力する。"""
        self.output_project_dir.write_user_performance(user_performance)
        # ユーザーごとの散布図を出力
        self.output_project_dir.write_user_performance_scatter_plot(user_performance)

    @_catch_exception
    def write_whole_performance(self, whole_performance: WholePerformance):  # noqa: ANN201
        """全体の生産性と品質に関するファイルを出力する。"""
        self.output_project_dir.write_whole_performance(whole_performance)

    @_catch_exception
    def write_cumulative_line_graph(self, task_worktime_by_phase_user: TaskWorktimeByPhaseUser) -> None:
        """ユーザごとにプロットした累積折れ線グラフを出力する。"""
        self.output_project_dir.write_cumulative_line_graph(
            AnnotatorCumulativeProductivity.from_df_wrapper(task_worktime_by_phase_user),
            phase=TaskPhase.ANNOTATION,
            user_id_list=self.user_id_list,
            minimal_output=self.minimal_output,
        )
        self.output_project_dir.write_cumulative_line_graph(
            InspectorCumulativeProductivity.from_df_wrapper(task_worktime_by_phase_user),
            phase=TaskPhase.INSPECTION,
            user_id_list=self.user_id_list,
            minimal_output=self.minimal_output,
        )
        self.output_project_dir.write_cumulative_line_graph(
            AcceptorCumulativeProductivity.from_df_wrapper(task_worktime_by_phase_user),
            phase=TaskPhase.ACCEPTANCE,
            user_id_list=self.user_id_list,
            minimal_output=self.minimal_output,
        )

    @_catch_exception
    def write_line_graph(self, task_worktime_by_phase_user: TaskWorktimeByPhaseUser) -> None:
        """ユーザごとにプロットした折れ線グラフを出力する。"""

        annotator_per_date_obj = AnnotatorProductivityPerDate.from_df_wrapper(task_worktime_by_phase_user)
        inspector_per_date_obj = InspectorProductivityPerDate.from_df_wrapper(task_worktime_by_phase_user)
        acceptor_per_date_obj = AcceptorProductivityPerDate.from_df_wrapper(task_worktime_by_phase_user)

        self.output_project_dir.write_performance_per_started_date_csv(annotator_per_date_obj, phase=TaskPhase.ANNOTATION)
        self.output_project_dir.write_performance_per_started_date_csv(inspector_per_date_obj, phase=TaskPhase.INSPECTION)
        self.output_project_dir.write_performance_per_started_date_csv(acceptor_per_date_obj, phase=TaskPhase.ACCEPTANCE)

        # 折れ線グラフを出力
        self.output_project_dir.write_performance_line_graph_per_date(annotator_per_date_obj, phase=TaskPhase.ANNOTATION, user_id_list=self.user_id_list)
        self.output_project_dir.write_performance_line_graph_per_date(inspector_per_date_obj, phase=TaskPhase.INSPECTION, user_id_list=self.user_id_list)
        self.output_project_dir.write_performance_line_graph_per_date(acceptor_per_date_obj, phase=TaskPhase.ACCEPTANCE, user_id_list=self.user_id_list)

    @_catch_exception
    def write_task_list_and_histogram(self, task: Task) -> None:
        self.output_project_dir.write_task_list(task)
        self.output_project_dir.write_task_histogram(task)

    @_catch_exception
    def write_worktime_per_date(self, worktime_per_date: WorktimePerDate) -> None:
        self.output_project_dir.write_worktime_per_date_user(worktime_per_date)
        self.output_project_dir.write_worktime_line_graph(worktime_per_date, user_id_list=self.user_id_list)

    @_catch_exception
    def write_task_worktime_by_phase_user(self, task_worktime_by_phase_user: TaskWorktimeByPhaseUser) -> None:
        self.output_project_dir.write_task_worktime_list(task_worktime_by_phase_user)

    @_catch_exception
    def write_performance_per_first_annotation_started_date(self, task: Task) -> None:
        obj = WholeProductivityPerFirstAnnotationStartedDate.from_task(task, self.task_completion_criteria)
        self.output_project_dir.write_whole_productivity_per_first_annotation_started_date(obj)
        self.output_project_dir.write_whole_productivity_line_graph_per_annotation_started_date(obj)

    @_catch_exception
    def write_merge_performance_per_date(self, task: Task, worktime_per_date: WorktimePerDate) -> None:
        obj = WholeProductivityPerCompletedDate.from_df_wrapper(task, worktime_per_date, task_completion_criteria=self.task_completion_criteria)
        self.output_project_dir.write_whole_productivity_per_date(obj)
        self.output_project_dir.write_whole_productivity_line_graph_per_date(obj)

    @_catch_exception
    def write_merge_info(self, merging_info: MergingInfo) -> None:
        self.output_project_dir.write_merge_info(merging_info)


class MergingVisualizationFile:
    def __init__(self, project_dir_list: list[ProjectDir], *, custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None) -> None:
        self.project_dir_list = project_dir_list
        self.custom_production_volume_list = custom_production_volume_list

    def merge_worktime_per_date(self) -> WorktimePerDate:
        merged_obj: Optional[WorktimePerDate] = None
        for project_dir in self.project_dir_list:
            tmp_obj = project_dir.read_worktime_per_date_user()

            if merged_obj is None:
                merged_obj = tmp_obj
            else:
                merged_obj = WorktimePerDate.merge(merged_obj, tmp_obj)
        assert merged_obj is not None
        return merged_obj

    def merge_task_list(self) -> Task:
        task_list: list[Task] = []
        for project_dir in self.project_dir_list:
            tmp_obj = project_dir.read_task_list()
            task_list.append(tmp_obj)

        merged_obj = Task.merge(*task_list, custom_production_volume_list=self.custom_production_volume_list)
        return merged_obj

    def merge_task_worktime_by_phase_user(self) -> TaskWorktimeByPhaseUser:
        tmp_list: list[TaskWorktimeByPhaseUser] = []
        for project_dir in self.project_dir_list:
            tmp_obj = project_dir.read_task_worktime_list()
            tmp_list.append(tmp_obj)

        merged_obj = TaskWorktimeByPhaseUser.merge(*tmp_list, custom_production_volume_list=self.custom_production_volume_list)
        return merged_obj

    def create_merging_info(self, task_completion_criteria: TaskCompletionCriteria) -> MergingInfo:
        """
        `project_info.json`の内容から、どのようにマージしたかを示す情報を作成する。
        """
        target_dir_list = [str(e.project_dir) for e in self.project_dir_list]
        project_info_list = []
        for project_dir in self.project_dir_list:
            project_info = project_dir.read_project_info()
            project_info_list.append(project_info)

        merge_info = MergingInfo(target_dir_list=target_dir_list, project_info_list=project_info_list, task_completion_criteria=task_completion_criteria)
        return merge_info


def merge_visualization_dir(  # pylint: disable=too-many-statements
    project_dir_list: list[ProjectDir],
    task_completion_criteria: TaskCompletionCriteria,
    output_project_dir: ProjectDir,
    *,
    custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None,
    user_id_list: Optional[list[str]] = None,
    minimal_output: bool = False,
) -> None:
    merging_obj = MergingVisualizationFile(project_dir_list, custom_production_volume_list=custom_production_volume_list)

    merging_info = merging_obj.create_merging_info(task_completion_criteria)
    output_project_dir.metadata = merging_info.to_dict(encode_json=True)

    # 基本となるCSVファイルを読み込みマージする
    task_worktime_by_phase_user = merging_obj.merge_task_worktime_by_phase_user()
    task = merging_obj.merge_task_list()
    worktime_per_date = merging_obj.merge_worktime_per_date()

    user_performance = UserPerformance.from_df_wrapper(
        task_worktime_by_phase_user=task_worktime_by_phase_user,
        worktime_per_date=worktime_per_date,
        task_completion_criteria=task_completion_criteria,
    )
    whole_performance = WholePerformance.from_df_wrapper(
        task_worktime_by_phase_user=task_worktime_by_phase_user,
        worktime_per_date=worktime_per_date,
        task_completion_criteria=task_completion_criteria,
    )
    writing_obj = WritingVisualizationFile(output_project_dir, user_id_list=user_id_list, minimal_output=minimal_output, task_completion_criteria=task_completion_criteria)

    writing_obj.write_task_list_and_histogram(task)
    writing_obj.write_worktime_per_date(worktime_per_date)
    writing_obj.write_task_worktime_by_phase_user(task_worktime_by_phase_user)
    writing_obj.write_user_performance(user_performance)
    writing_obj.write_whole_performance(whole_performance)

    writing_obj.write_cumulative_line_graph(task_worktime_by_phase_user)
    writing_obj.write_line_graph(task_worktime_by_phase_user)

    writing_obj.write_merge_performance_per_date(task, worktime_per_date)
    writing_obj.write_performance_per_first_annotation_started_date(task)

    # info.jsonを出力
    writing_obj.write_merge_info(merging_info)


def validate(args: argparse.Namespace) -> bool:
    COMMON_MESSAGE = "annofabcli stat_visualization merge:"  # noqa: N806
    if len(args.dir) < 2:
        print(f"{COMMON_MESSAGE} argument --dir: マージ対象のディレクトリは2つ以上指定してください。", file=sys.stderr)  # noqa: T201
        return False

    return True


def create_custom_production_volume_list(cli_value: str) -> list[ProductionVolumeColumn]:
    """
    コマンドラインから渡された文字列を元に、独自の生産量を表す列情報を生成します。
    """
    dict_data = get_json_from_args(cli_value)

    column_list = dict_data["column_list"]
    custom_production_volume_list = [ProductionVolumeColumn(column["value"], column["name"]) for column in column_list]

    return custom_production_volume_list


def main(args: argparse.Namespace) -> None:
    if not validate(args):
        sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

    user_id_list = get_list_from_args(args.user_id) if args.user_id is not None else None

    custom_production_volume_list = create_custom_production_volume_list(args.custom_production_volume) if args.custom_production_volume is not None else None
    task_completion_criteria = TaskCompletionCriteria(args.task_completion_criteria)
    merge_visualization_dir(
        project_dir_list=[ProjectDir(e, task_completion_criteria) for e in args.dir],
        task_completion_criteria=task_completion_criteria,
        user_id_list=user_id_list,
        custom_production_volume_list=custom_production_volume_list,
        minimal_output=args.minimal,
        output_project_dir=ProjectDir(args.output_dir, task_completion_criteria),
    )


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dir", type=Path, nargs="+", required=True, help="マージ対象ディレクトリ。2つ以上指定してください。")
    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力先ディレクトリ。配下にプロジェクト名のディレクトリが出力される。")

    parser.add_argument(
        "--task_completion_criteria",
        type=str,
        choices=[e.value for e in TaskCompletionCriteria],
        default=TaskCompletionCriteria.ACCEPTANCE_COMPLETED.value,
        help="タスクの完了条件を指定します。\n"
        "* ``acceptance_completed``: タスクが受入フェーズの完了状態であれば「タスクの完了」とみなす\n"
        "* ``acceptance_reached``: タスクが受入フェーズに到達したら「タスクの完了」とみなす\n",
    )

    parser.add_argument(
        "-u",
        "--user_id",
        nargs="+",
        help=(
            "ユーザごとの折れ線グラフに表示するユーザのuser_idを指定してください。"
            "指定しない場合は、上位20人のユーザ情報がプロットされます。"
            " ``file://`` を先頭に付けると、一覧が記載されたファイルを指定できます。"
        ),
    )

    parser.add_argument(
        "--minimal",
        action="store_true",
        help="必要最小限のファイルを出力します。",
    )

    custom_production_volume_sample = {
        "column_list": [{"value": "video_duration_minute", "name": "動画長さ"}],
    }

    parser.add_argument(
        "--custom_production_volume",
        type=str,
        help=(f"プロジェクト独自の生産量をJSON形式で指定します。(例) ``{json.dumps(custom_production_volume_sample, ensure_ascii=False)}`` \n"),
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "merge"
    subcommand_help = "``annofabcli statistics visualize`` コマンドの出力結果をマージします。"
    description = "``annofabcli statistics visualize`` コマンドの出力結果をマージします。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
