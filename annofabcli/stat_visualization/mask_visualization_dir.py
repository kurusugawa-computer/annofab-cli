import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

from annofabapi.models import TaskPhase

import annofabcli
from annofabcli.common.cli import get_list_from_args
from annofabcli.filesystem.mask_user_info import (
    create_masked_user_info_df,
    create_replacement_dict_by_user_id,
    replace_by_columns,
)
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
from annofabcli.statistics.visualization.dataframe.user_performance import UserPerformance
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate
from annofabcli.statistics.visualization.project_dir import ProjectDir

logger = logging.getLogger(__name__)


def _replace_df_task(task: Task, replacement_dict_by_user_id: Dict[str, str]) -> Task:
    df_output = task.df.copy()

    replace_by_columns(
        df_output,
        replacement_dict_by_user_id,
        main_column="first_annotation_user_id",
        sub_columns=["first_annotation_username"],
    )
    replace_by_columns(
        df_output,
        replacement_dict_by_user_id,
        main_column="first_inspection_user_id",
        sub_columns=["first_inspection_username"],
    )
    replace_by_columns(
        df_output,
        replacement_dict_by_user_id,
        main_column="first_acceptance_user_id",
        sub_columns=["first_acceptance_username"],
    )
    return Task(df_output)


def write_line_graph(
    task: Task, output_project_dir: ProjectDir, user_id_list: Optional[List[str]] = None, minimal_output: bool = False
):
    df = task.df.copy()

    output_project_dir.write_cumulative_line_graph(
        AnnotatorCumulativeProductivity(df),
        phase=TaskPhase.ANNOTATION,
        user_id_list=user_id_list,
        minimal_output=minimal_output,
    )
    output_project_dir.write_cumulative_line_graph(
        InspectorCumulativeProductivity(df),
        phase=TaskPhase.INSPECTION,
        user_id_list=user_id_list,
        minimal_output=minimal_output,
    )
    output_project_dir.write_cumulative_line_graph(
        AcceptorCumulativeProductivity(df),
        phase=TaskPhase.ACCEPTANCE,
        user_id_list=user_id_list,
        minimal_output=minimal_output,
    )

    annotator_per_date_obj = AnnotatorProductivityPerDate.from_df_task(task.df)
    inspector_per_date_obj = InspectorProductivityPerDate.from_df_task(task.df)
    acceptor_per_date_obj = AcceptorProductivityPerDate.from_df_task(task.df)

    output_project_dir.write_performance_per_started_date_csv(annotator_per_date_obj, phase=TaskPhase.ANNOTATION)
    output_project_dir.write_performance_per_started_date_csv(inspector_per_date_obj, phase=TaskPhase.INSPECTION)
    output_project_dir.write_performance_per_started_date_csv(acceptor_per_date_obj, phase=TaskPhase.ACCEPTANCE)

    if not minimal_output:
        output_project_dir.write_performance_line_graph_per_date(
            annotator_per_date_obj, phase=TaskPhase.ANNOTATION, user_id_list=user_id_list
        )
        output_project_dir.write_performance_line_graph_per_date(
            inspector_per_date_obj, phase=TaskPhase.INSPECTION, user_id_list=user_id_list
        )
        output_project_dir.write_performance_line_graph_per_date(
            acceptor_per_date_obj, phase=TaskPhase.ACCEPTANCE, user_id_list=user_id_list
        )


def mask_visualization_dir(
    project_dir: ProjectDir,
    output_project_dir: ProjectDir,
    *,
    not_masked_biography_set: Optional[Set[str]] = None,
    not_masked_user_id_set: Optional[Set[str]] = None,
    minimal_output: bool = False,
    exclude_masked_user_for_line_graph: bool = False,
) -> None:
    user_performance = project_dir.read_user_performance()
    if user_performance.empty():
        logger.warning(f"メンバごとの生産性と品質情報が空であるため、ユーザー情報をマスクできません。終了します。")
        return

    # マスクするユーザの情報を取得する
    replacement_dict_by_user_id = create_replacement_dict_by_user_id(
        user_performance.df,
        not_masked_biography_set=not_masked_biography_set,
        not_masked_user_id_set=not_masked_user_id_set,
    )
    not_masked_user_id_set = set(user_performance.df[("user_id", "")]) - set(replacement_dict_by_user_id.keys())

    # CSVのユーザ情報をマスクする
    masked_df_member_performance = create_masked_user_info_df(
        user_performance.df,
        not_masked_biography_set=not_masked_biography_set,
        not_masked_user_id_set=not_masked_user_id_set,
    )
    masked_user_performance = UserPerformance(masked_df_member_performance)
    output_project_dir.write_user_performance(masked_user_performance)

    # メンバのパフォーマンスを散布図で出力する
    output_project_dir.write_user_performance_scatter_plot(masked_user_performance)

    user_id_list: Optional[List[str]] = None
    if exclude_masked_user_for_line_graph:
        user_id_list = list(not_masked_user_id_set)

    # TODO: validation
    task = project_dir.read_task_list()
    masked_task = _replace_df_task(task, replacement_dict_by_user_id=replacement_dict_by_user_id)
    output_project_dir.write_task_list(masked_task)

    write_line_graph(masked_task, output_project_dir, user_id_list=user_id_list, minimal_output=minimal_output)

    worktime_per_date_user = project_dir.read_worktime_per_date_user()
    if not worktime_per_date_user.is_empty():
        df_masked_worktime = create_masked_user_info_df(
            worktime_per_date_user.df,
            not_masked_biography_set=not_masked_biography_set,
            not_masked_user_id_set=not_masked_user_id_set,
        )
        masked_worktime_per_date_user = WorktimePerDate(df_masked_worktime)
        output_project_dir.write_worktime_per_date_user(masked_worktime_per_date_user)
        output_project_dir.write_worktime_line_graph(masked_worktime_per_date_user, user_id_list=user_id_list)
    else:
        logger.warning(
            f"'{project_dir.project_dir / project_dir.FILENAME_WORKTIME_PER_DATE_USER}'が存在しないかデータがないため、"
            f"'{project_dir.FILENAME_WORKTIME_PER_DATE_USER}'から生成できるファイルを出力しません。"
        )

    logger.debug(f"'{project_dir}'のマスクした結果を'{output_project_dir}'に出力しました。")


def main(args):
    not_masked_biography_set = (
        set(get_list_from_args(args.not_masked_biography)) if args.not_masked_biography is not None else None
    )
    not_masked_user_id_set = (
        set(get_list_from_args(args.not_masked_user_id)) if args.not_masked_user_id is not None else None
    )

    mask_visualization_dir(
        project_dir=ProjectDir(args.dir),
        output_project_dir=ProjectDir(args.output_dir),
        not_masked_biography_set=not_masked_biography_set,
        not_masked_user_id_set=not_masked_user_id_set,
        minimal_output=args.minimal,
        exclude_masked_user_for_line_graph=args.exclude_masked_user_for_line_graph,
    )


def parse_args(parser: argparse.ArgumentParser):

    parser.add_argument(
        "--dir",
        type=Path,
        required=True,
        help=f"マスクしたいプロジェクトディレクトリを指定してください。プロジェクトディレクトリは  ``annofabcli statistics visualize`` コマンドの出力結果です。",  # noqa: E501
    )

    parser.add_argument(
        "--not_masked_biography",
        type=str,
        nargs="+",
        help="マスクしないユーザの ``biography`` を指定してください。",
    )

    parser.add_argument(
        "--not_masked_user_id",
        type=str,
        nargs="+",
        help="マスクしないユーザの ``user_id`` を指定してください。",
    )

    parser.add_argument(
        "--minimal",
        action="store_true",
        help="必要最小限のファイルを出力します。",
    )

    parser.add_argument(
        "--exclude_masked_user_for_line_graph",
        action="store_true",
        help="折れ線グラフに、マスクされたユーザをプロットしません。",
    )

    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力先ディレクトリ。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "mask_user_info"
    subcommand_help = "`annofabcli statistics visualize` コマンドの出力結果のユーザ情報をマスクします。"
    description = "`annofabcli statistics visualize` コマンドの出力結果のユーザ情報をマスクします。マスク対象のファイルのみ出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
