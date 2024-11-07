from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas
from annofabapi.models import TaskPhase

import annofabcli
from annofabcli.common.cli import get_list_from_args
from annofabcli.filesystem.mask_user_info import (
    create_replacement_dict_by_biography,
    create_replacement_dict_by_user_id,
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
from annofabcli.statistics.visualization.dataframe.task_worktime_by_phase_user import TaskWorktimeByPhaseUser
from annofabcli.statistics.visualization.dataframe.user_performance import UserPerformance
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate
from annofabcli.statistics.visualization.project_dir import ProjectDir

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReplacementDict:
    """
    ユーザー情報を置換するための情報。
    各プロパティは、keyが置換前の値、valueが置換後の値を持つdict。
    """

    user_id: Dict[str, str]
    username: Dict[str, str]
    account_id: Dict[str, str]
    biography: Dict[str, str]


def create_replacement_dict(
    df_user: pandas.DataFrame,
    *,
    not_masked_biography_set: Optional[Set[str]],
    not_masked_user_id_set: Optional[Set[str]],
) -> ReplacementDict:
    """
    ユーザー情報を置換するためのインスタンスを生成します。

    Args:
        df_user: ユーザー情報が格納されたDataFrame。以下の列が必要です。
            * user_id
            * username
            * account_id
            * biography
        not_masked_user_id_set: マスクしないuser_idの集合。
        not_masked_biography_set: マスクしないbiographyの集合。指定したbiographyに該当するユーザーのuser_id,username,account_idはマスクしません。
    """

    assert {"user_id", "username", "account_id", "biography"} - set(
        df_user.columns
    ) == set(), "df_userには'user_id','username','account_id','biography'の列が必要です。"

    replacement_dict_for_user_id = create_replacement_dict_by_user_id(
        df_user, not_masked_biography_set=not_masked_biography_set, not_masked_user_id_set=not_masked_user_id_set
    )

    df2 = df_user.set_index("user_id")
    df3 = df2.loc[replacement_dict_for_user_id.keys()]
    replacement_dict_for_username = dict(zip(df3["username"], replacement_dict_for_user_id.values()))
    replacement_dict_for_account_id = dict(zip(df3["account_id"], replacement_dict_for_user_id.values()))

    replacement_dict_by_biography = create_replacement_dict_by_biography(df_user, not_masked_biography_set=not_masked_biography_set)

    return ReplacementDict(
        user_id=replacement_dict_for_user_id,
        username=replacement_dict_for_username,
        account_id=replacement_dict_for_account_id,
        biography=replacement_dict_by_biography,
    )


def write_line_graph(task: Task, output_project_dir: ProjectDir, user_id_list: Optional[List[str]] = None, minimal_output: bool = False):  # noqa: ANN201, FBT001, FBT002
    output_project_dir.write_cumulative_line_graph(
        AnnotatorCumulativeProductivity.from_task(task),
        phase=TaskPhase.ANNOTATION,
        user_id_list=user_id_list,
        minimal_output=minimal_output,
    )
    output_project_dir.write_cumulative_line_graph(
        InspectorCumulativeProductivity.from_task(task),
        phase=TaskPhase.INSPECTION,
        user_id_list=user_id_list,
        minimal_output=minimal_output,
    )
    output_project_dir.write_cumulative_line_graph(
        AcceptorCumulativeProductivity.from_task(task),
        phase=TaskPhase.ACCEPTANCE,
        user_id_list=user_id_list,
        minimal_output=minimal_output,
    )

    annotator_per_date_obj = AnnotatorProductivityPerDate.from_task(task)
    inspector_per_date_obj = InspectorProductivityPerDate.from_task(task)
    acceptor_per_date_obj = AcceptorProductivityPerDate.from_task(task)

    output_project_dir.write_performance_per_started_date_csv(annotator_per_date_obj, phase=TaskPhase.ANNOTATION)
    output_project_dir.write_performance_per_started_date_csv(inspector_per_date_obj, phase=TaskPhase.INSPECTION)
    output_project_dir.write_performance_per_started_date_csv(acceptor_per_date_obj, phase=TaskPhase.ACCEPTANCE)

    if not minimal_output:
        output_project_dir.write_performance_line_graph_per_date(annotator_per_date_obj, phase=TaskPhase.ANNOTATION, user_id_list=user_id_list)
        output_project_dir.write_performance_line_graph_per_date(inspector_per_date_obj, phase=TaskPhase.INSPECTION, user_id_list=user_id_list)
        output_project_dir.write_performance_line_graph_per_date(acceptor_per_date_obj, phase=TaskPhase.ACCEPTANCE, user_id_list=user_id_list)


def create_df_user(worktime_per_date_user: WorktimePerDate, task_worktime_by_phase_user: TaskWorktimeByPhaseUser) -> pandas.DataFrame:
    """
    ユーザー情報が格納されているDataFrameを生成します。

    Returns:
        以下の列が含まれているDataFrame
        * user_id
        * account_id
        * username
        * biography
    """
    df_user1 = worktime_per_date_user.df[["user_id", "username", "account_id", "biography"]]
    df_user2 = task_worktime_by_phase_user.df[["user_id", "username", "account_id", "biography"]]
    df_user = pandas.concat([df_user1, df_user2])
    return df_user.drop_duplicates()


def mask_visualization_dir(
    project_dir: ProjectDir,
    output_project_dir: ProjectDir,
    *,
    not_masked_biography_set: Optional[Set[str]] = None,
    not_masked_user_id_set: Optional[Set[str]] = None,
    minimal_output: bool = False,
) -> None:
    worktime_per_date = project_dir.read_worktime_per_date_user()
    task_worktime_by_phase_user = project_dir.read_task_worktime_list()
    df_user = create_df_user(worktime_per_date, task_worktime_by_phase_user)
    replacement_dict = create_replacement_dict(
        df_user,
        not_masked_biography_set=not_masked_biography_set,
        not_masked_user_id_set=not_masked_user_id_set,
    )

    masked_worktime_per_date = worktime_per_date.mask_user_info(
        to_replace_for_account_id=replacement_dict.account_id,
        to_replace_for_biography=replacement_dict.biography,
        to_replace_for_user_id=replacement_dict.user_id,
        to_replace_for_username=replacement_dict.username,
    )
    masked_task_worktime_by_phase_user = task_worktime_by_phase_user.mask_user_info(
        to_replace_for_account_id=replacement_dict.account_id,
        to_replace_for_biography=replacement_dict.biography,
        to_replace_for_user_id=replacement_dict.user_id,
        to_replace_for_username=replacement_dict.username,
    )

    # CSVのユーザ情報をマスクする
    masked_user_performance = UserPerformance.from_df_wrapper(masked_worktime_per_date, masked_task_worktime_by_phase_user)
    output_project_dir.write_user_performance(masked_user_performance)

    # メンバのパフォーマンスを散布図で出力する
    output_project_dir.write_user_performance_scatter_plot(masked_user_performance)

    masked_task = project_dir.read_task_list().mask_user_info(
        to_replace_for_user_id=replacement_dict.user_id, to_replace_for_username=replacement_dict.username
    )
    output_project_dir.write_task_list(masked_task)

    write_line_graph(masked_task, output_project_dir, minimal_output=minimal_output)

    if not masked_worktime_per_date.is_empty():
        output_project_dir.write_worktime_per_date_user(masked_worktime_per_date)
        output_project_dir.write_worktime_line_graph(masked_worktime_per_date)
    else:
        logger.warning(
            f"'{project_dir.project_dir / project_dir.FILENAME_WORKTIME_PER_DATE_USER}'が存在しないかデータがないため、"
            f"'{project_dir.FILENAME_WORKTIME_PER_DATE_USER}'から生成できるファイルを出力しません。"
        )

    output_project_dir.write_task_worktime_list(masked_task_worktime_by_phase_user)

    logger.debug(f"'{project_dir}'のマスクした結果を'{output_project_dir}'に出力しました。")


def main(args: argparse.Namespace) -> None:
    not_masked_biography_set = set(get_list_from_args(args.not_masked_biography)) if args.not_masked_biography is not None else None
    not_masked_user_id_set = set(get_list_from_args(args.not_masked_user_id)) if args.not_masked_user_id is not None else None

    mask_visualization_dir(
        project_dir=ProjectDir(args.dir),
        output_project_dir=ProjectDir(args.output_dir),
        not_masked_biography_set=not_masked_biography_set,
        not_masked_user_id_set=not_masked_user_id_set,
        minimal_output=args.minimal,
    )


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dir",
        type=Path,
        required=True,
        help="マスクしたいプロジェクトディレクトリを指定してください。プロジェクトディレクトリは  ``annofabcli statistics visualize`` コマンドの出力結果です。",  # noqa: E501
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

    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力先ディレクトリ。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "mask_user_info"
    subcommand_help = "`annofabcli statistics visualize` コマンドの出力結果のユーザ情報をマスクします。"
    description = "`annofabcli statistics visualize` コマンドの出力結果のユーザ情報をマスクします。マスク対象のファイルのみ出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
