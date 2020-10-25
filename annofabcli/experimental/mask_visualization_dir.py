import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas

import annofabcli
from annofabcli.common.cli import get_list_from_args
from annofabcli.common.utils import print_csv, read_multiheader_csv
from annofabcli.experimental.mask_user_info import (
    create_replacement_dict_by_biography,
    create_replacement_dict_by_user_id,
    replace_by_columns,
    replace_user_info_by_user_id,
)
from annofabcli.experimental.write_linegraph_per_user import write_linegraph_per_user
from annofabcli.experimental.write_performance_scatter_per_user import write_performance_scatter_per_user
from annofabcli.statistics.csv import FILENAME_PEFORMANCE_PER_USER, FILENAME_TASK_LIST

logger = logging.getLogger(__name__)


def _replace_df_member_perfomance(
    df, replacement_dict_by_user_id: Dict[str, str], replacement_dict_by_biography: Dict[str, str]
):
    replace_user_info_by_user_id(df, replacement_dict_by_user_id)
    df["biography"] = df["biography"].replace(replacement_dict_by_biography)
    return df


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


def mask_csv(
    project_dir: Path,
    output_dir: Path,
    not_masked_biography_set: Optional[Set[str]] = None,
    not_masked_user_id_set: Optional[Set[str]] = None,
):
    df_member_perfomance = read_multiheader_csv(str(project_dir / FILENAME_PEFORMANCE_PER_USER), header_row_count=2)

    replacement_dict_by_user_id = create_replacement_dict_by_user_id(
        df_member_perfomance,
        not_masked_biography_set=not_masked_biography_set,
        not_masked_user_id_set=not_masked_user_id_set,
    )
    replacement_dict_by_biography = create_replacement_dict_by_biography(
        df_member_perfomance, not_masked_biography_set=not_masked_biography_set
    )

    _replace_df_member_perfomance(
        df_member_perfomance,
        replacement_dict_by_user_id=replacement_dict_by_user_id,
        replacement_dict_by_biography=replacement_dict_by_biography,
    )
    print_csv(df_member_perfomance, output=str(output_dir / FILENAME_PEFORMANCE_PER_USER))

    df_task = pandas.read_csv(str(project_dir / FILENAME_TASK_LIST))
    _replace_df_task(df_task, replacement_dict_by_user_id=replacement_dict_by_user_id)
    print_csv(df_task, output=str(output_dir / FILENAME_TASK_LIST))


def mask_visualization_dir(
    project_dir: Path,
    output_dir: Path,
    not_masked_biography_set: Optional[Set[str]] = None,
    not_masked_user_id_set: Optional[Set[str]] = None,
    minimal_output: bool = False,
    exclude_masked_user_for_linegraph: bool = False,
):
    df_member_perfomance = read_multiheader_csv(str(project_dir / FILENAME_PEFORMANCE_PER_USER), header_row_count=2)

    replacement_dict_by_user_id = create_replacement_dict_by_user_id(
        df_member_perfomance,
        not_masked_biography_set=not_masked_biography_set,
        not_masked_user_id_set=not_masked_user_id_set,
    )
    replacement_dict_by_biography = create_replacement_dict_by_biography(
        df_member_perfomance, not_masked_biography_set=not_masked_biography_set
    )

    not_masked_user_id_set = set(df_member_perfomance[("user_id", "")]) - set(replacement_dict_by_user_id.keys())

    # CSVのユーザ情報をマスクする
    _replace_df_member_perfomance(
        df_member_perfomance,
        replacement_dict_by_user_id=replacement_dict_by_user_id,
        replacement_dict_by_biography=replacement_dict_by_biography,
    )
    print_csv(df_member_perfomance, output=str(output_dir / FILENAME_PEFORMANCE_PER_USER))

    df_task = pandas.read_csv(str(project_dir / FILENAME_TASK_LIST))
    _replace_df_task(df_task, replacement_dict_by_user_id=replacement_dict_by_user_id)
    print_csv(df_task, output=str(output_dir / FILENAME_TASK_LIST))

    # メンバのパフォーマンスを散布図で出力する
    write_performance_scatter_per_user(output_dir / FILENAME_PEFORMANCE_PER_USER, output_dir=output_dir / "scatter")

    user_id_list: Optional[List[str]] = None
    if exclude_masked_user_for_linegraph:
        user_id_list = list(not_masked_user_id_set)

    # メンバごとにパフォーマンスを折れ線グラフで出力する
    write_linegraph_per_user(
        output_dir / FILENAME_TASK_LIST,
        output_dir=output_dir / "line-graph",
        minimal_output=minimal_output,
        user_id_list=user_id_list,
    )


def main(args):
    not_masked_biography_set = (
        set(get_list_from_args(args.not_masked_biography)) if args.not_masked_biography is not None else None
    )
    not_masked_user_id_set = (
        set(get_list_from_args(args.not_masked_user_id)) if args.not_masked_user_id is not None else None
    )

    mask_visualization_dir(
        project_dir=args.dir,
        not_masked_biography_set=not_masked_biography_set,
        not_masked_user_id_set=not_masked_user_id_set,
        output_dir=args.output_dir,
        minimal_output=args.minimal,
        exclude_masked_user_for_linegraph=args.exclude_masked_user_for_linegraph,
    )


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--dir", type=Path, required=True, help="マスク対象のディレクトリ。`annofabcli statistics visualize`コマンドの出力結果。"
    )

    parser.add_argument(
        "--not_masked_biography",
        type=str,
        nargs="+",
        help="マスクしないユーザの`biography`を指定してください。",
    )

    parser.add_argument(
        "--not_masked_user_id",
        type=str,
        nargs="+",
        help="マスクしないユーザの`user_id`を指定してください。",
    )

    parser.add_argument(
        "--minimal",
        action="store_true",
        help="必要最小限のファイルを出力します。",
    )

    parser.add_argument(
        "--exclude_masked_user_for_linegraph",
        action="store_true",
        help="折れ線グラフに、マスクされたユーザを除外します。",
    )

    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力先ディレクトリ。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "mask_visualization_dir"
    subcommand_help = "`annofabcli statistics visualize`コマンドの出力結果のユーザ情報をマスクします。"
    description = "`annofabcli statistics visualize`コマンドの出力結果のユーザ情報をマスクします。マスク対象のファイルのみ出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
