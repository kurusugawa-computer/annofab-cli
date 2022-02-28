import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas

import annofabcli
from annofabcli.common.cli import get_list_from_args
from annofabcli.common.utils import print_csv, read_multiheader_csv
from annofabcli.filesystem.mask_user_info import (
    create_masked_user_info_df,
    create_replacement_dict_by_user_id,
    replace_by_columns,
)
from annofabcli.stat_visualization.write_linegraph_per_user import write_linegraph_per_user
from annofabcli.stat_visualization.write_performance_scatter_per_user import write_performance_scatter_per_user
from annofabcli.statistics.csv import FILENAME_PERFORMANCE_PER_USER, FILENAME_TASK_LIST
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate

logger = logging.getLogger(__name__)


def _replace_df_task(df, replacement_dict_by_user_id: Dict[str, str]):
    replace_by_columns(df, replacement_dict_by_user_id, main_column="user_id", sub_columns=["username"])

    replace_by_columns(
        df,
        replacement_dict_by_user_id,
        main_column="first_annotation_user_id",
        sub_columns=["first_annotation_username"],
    )
    replace_by_columns(
        df,
        replacement_dict_by_user_id,
        main_column="first_inspection_user_id",
        sub_columns=["first_inspection_username"],
    )
    replace_by_columns(
        df,
        replacement_dict_by_user_id,
        main_column="first_acceptance_user_id",
        sub_columns=["first_acceptance_username"],
    )


# class MaskingVisualizationDir:
#     def __init__(self,     not_masked_biography_set: Optional[Set[str]] = None,
#         not_masked_user_id_set: Optional[Set[str]] = None,
#         minimal_output: bool = False,
#         exclude_masked_user_for_linegraph: bool = False,
#     ) -> None:
#         self.not_masked_biography_set


def mask_visualization_dir(
    project_dir: Path,
    output_dir: Path,
    *,
    not_masked_biography_set: Optional[Set[str]] = None,
    not_masked_user_id_set: Optional[Set[str]] = None,
    minimal_output: bool = False,
    exclude_masked_user_for_linegraph: bool = False,
):
    if not (project_dir / FILENAME_PERFORMANCE_PER_USER).exists():
        logger.warning(
            f"'{str(project_dir / FILENAME_PERFORMANCE_PER_USER)}'が存在しないので、'{str(project_dir)}'のマスク処理をスキップします。"
        )
        return

    df_member_performance = read_multiheader_csv(str(project_dir / FILENAME_PERFORMANCE_PER_USER), header_row_count=2)

    replacement_dict_by_user_id = create_replacement_dict_by_user_id(
        df_member_performance,
        not_masked_biography_set=not_masked_biography_set,
        not_masked_user_id_set=not_masked_user_id_set,
    )
    not_masked_user_id_set = set(df_member_performance[("user_id", "")]) - set(replacement_dict_by_user_id.keys())

    # CSVのユーザ情報をマスクする
    masked_df_member_performance = create_masked_user_info_df(
        df_member_performance,
        not_masked_biography_set=not_masked_biography_set,
        not_masked_user_id_set=not_masked_user_id_set,
    )
    print_csv(masked_df_member_performance, output=str(output_dir / FILENAME_PERFORMANCE_PER_USER))

    # メンバのパフォーマンスを散布図で出力する
    write_performance_scatter_per_user(output_dir / FILENAME_PERFORMANCE_PER_USER, output_dir=output_dir / "scatter")

    user_id_list: Optional[List[str]] = None
    if exclude_masked_user_for_linegraph:
        user_id_list = list(not_masked_user_id_set)

    task_csv_file = project_dir / FILENAME_TASK_LIST
    if task_csv_file.exists():
        df_task = pandas.read_csv(str(project_dir / FILENAME_TASK_LIST))
        _replace_df_task(df_task, replacement_dict_by_user_id=replacement_dict_by_user_id)
        print_csv(df_task, output=str(output_dir / FILENAME_TASK_LIST))
    else:
        logger.warning(f"'{task_csv_file}' が存在しないため、" f"'{output_dir / FILENAME_TASK_LIST}' は出力しません。 ")

    if (output_dir / FILENAME_TASK_LIST).exists():
        # メンバごとにパフォーマンスを折れ線グラフで出力する
        write_linegraph_per_user(
            output_dir / FILENAME_TASK_LIST,
            output_dir=output_dir / "line-graph",
            minimal_output=minimal_output,
            user_id_list=user_id_list,
        )

    user_date_csv_file = project_dir / "ユーザ_日付list-作業時間.csv"
    if user_date_csv_file.exists():
        df_worktime = pandas.read_csv(str(user_date_csv_file))
        df_masked_worktime = create_masked_user_info_df(
            df_worktime,
            not_masked_biography_set=not_masked_biography_set,
            not_masked_user_id_set=not_masked_user_id_set,
        )
        worktime_per_date_obj = WorktimePerDate(df_masked_worktime)
        worktime_per_date_obj.plot_cumulatively(output_dir / "line-graph/累積折れ線-横軸_日-縦軸_作業時間.html", user_id_list)
        worktime_per_date_obj.to_csv(output_dir / "ユーザ_日付list-作業時間.csv")
    else:
        logger.warning(
            f"{user_date_csv_file}が存在しないため、"
            f"'{output_dir / 'line-graph/累積折れ線-横軸_日-縦軸_作業時間.html'}', "
            f"'{output_dir / 'ユーザ_日付list-作業時間.csv'}' は出力しません。"
        )

    logger.debug(f"'{project_dir}'のマスクした結果を'{output_dir}'に出力しました。")


def mask_visualization_root_dir(
    project_root_dir: Path,
    output_dir: Path,
    not_masked_biography_set: Optional[Set[str]] = None,
    not_masked_user_id_set: Optional[Set[str]] = None,
    minimal_output: bool = False,
    exclude_masked_user_for_linegraph: bool = False,
):

    for project_dir in project_root_dir.iterdir():
        if not project_dir.is_dir():
            continue

        project_output_dir = output_dir / project_dir.name

        try:
            mask_visualization_dir(
                project_dir,
                project_output_dir,
                not_masked_biography_set=not_masked_biography_set,
                not_masked_user_id_set=not_masked_user_id_set,
                minimal_output=minimal_output,
                exclude_masked_user_for_linegraph=exclude_masked_user_for_linegraph,
            )
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"'{project_dir}'のユーザのマスク処理に失敗しました。", exc_info=True)
            continue


def main(args):
    not_masked_biography_set = (
        set(get_list_from_args(args.not_masked_biography)) if args.not_masked_biography is not None else None
    )
    not_masked_user_id_set = (
        set(get_list_from_args(args.not_masked_user_id)) if args.not_masked_user_id is not None else None
    )

    mask_visualization_root_dir(
        project_root_dir=args.dir,
        not_masked_biography_set=not_masked_biography_set,
        not_masked_user_id_set=not_masked_user_id_set,
        output_dir=args.output_dir,
        minimal_output=args.minimal,
        exclude_masked_user_for_linegraph=args.exclude_masked_user_for_linegraph,
    )


def parse_args(parser: argparse.ArgumentParser):

    parser.add_argument(
        "--dir",
        type=Path,
        required=True,
        help=f"マスクしたいプロジェクトディレクトリが存在するディレクトリを指定してください。プロジェクトディレクトリは  ``annofabcli statistics visualize`` コマンドの出力結果です。\n"
        f"プロジェクトディレクトリ配下の'{FILENAME_PERFORMANCE_PER_USER}'を読み込み、ユーザ情報をマスクします。",
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
        "--exclude_masked_user_for_linegraph",
        action="store_true",
        help="折れ線グラフに、マスクされたユーザをプロットしません。",
    )

    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力先ディレクトリ。配下にプロジェクトディレクトリが生成されます。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "mask_user_info"
    subcommand_help = "`annofabcli statistics visualize` コマンドの出力結果のユーザ情報をマスクします。"
    description = "`annofabcli statistics visualize` コマンドの出力結果のユーザ情報をマスクします。マスク対象のファイルのみ出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
