from __future__ import annotations

import argparse
import copy
import logging
import sys
from typing import Optional

import pandas

import annofabcli.annotation.subcommand_annotation
import annofabcli.annotation_specs.subcommand_annotation_specs
import annofabcli.comment.subcommand_comment
import annofabcli.common.cli
import annofabcli.experimental.subcommand_experimental
import annofabcli.filesystem.subcommand_filesystem
import annofabcli.input_data.subcommand_input_data
import annofabcli.instruction.subcommand_instruction
import annofabcli.job.subcommand_job
import annofabcli.my_account.subcommand_my_account
import annofabcli.organization.subcommand_organization
import annofabcli.organization_member.subcommand_organization_member
import annofabcli.project.subcommand_project
import annofabcli.project_member.subcommand_project_member
import annofabcli.stat_visualization.subcommand_stat_visualization
import annofabcli.statistics.subcommand_statistics
import annofabcli.supplementary.subcommand_supplementary
import annofabcli.task.subcommand_task
import annofabcli.task_history.subcommand_task_history
import annofabcli.task_history_event.subcommand_task_history_event

logger = logging.getLogger(__name__)


def warn_pandas_copy_on_write() -> None:
    """
    pandas2.2以上ならば、Copy-on-Writeの警告を出す。
    pandas 3.0で予期しない挙動になるのを防ぐため。
    https://pandas.pydata.org/docs/user_guide/copy_on_write.html
    """
    major, minor, _ = pandas.__version__.split(".")
    if int(major) >= 2 and int(minor) >= 2:
        pandas.options.mode.copy_on_write = "warn"


def mask_sensitive_value_in_argv(argv: list[str]) -> list[str]:
    """
    `argv`にセンシティブな情報が含まれている場合は、`***`に置き換える。
    """
    tmp_argv = copy.deepcopy(argv)
    for masked_option in ["--annofab_user_id", "--annofab_password", "--annofab_pat"]:
        try:
            start_index = 0
            # `--annofab_password a --annofab_password b`のように複数指定された場合でもマスクできるようにする
            while True:
                index = tmp_argv.index(masked_option, start_index)
                tmp_argv[index + 1] = "***"
                start_index = index + 2

        except ValueError:
            continue
    return tmp_argv


def main(arguments: Optional[list[str]] = None) -> None:
    """
    annofabcliコマンドのメイン処理
    注意： `deprecated`なツールは、サブコマンド化しない。

    Args:
        arguments: コマンドライン引数。テストコード用

    """
    warn_pandas_copy_on_write()
    parser = create_parser()

    if arguments is None:
        args = parser.parse_args()
    else:
        args = parser.parse_args(arguments)

    if hasattr(args, "subcommand_func"):
        try:
            annofabcli.common.cli.load_logging_config_from_args(args)
            argv = sys.argv
            if arguments is not None:
                argv = ["annofabcli", *list(arguments)]
            logger.info(f"argv={mask_sensitive_value_in_argv(argv)}")
            args.subcommand_func(args)
        except Exception as e:
            logger.exception(e)  # noqa: TRY401
            raise e  # noqa: TRY201

    else:
        # 未知のサブコマンドの場合はヘルプを表示
        args.command_help()


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Command Line Interface for Annofab", formatter_class=annofabcli.common.cli.PrettyHelpFormatter)
    parser.add_argument("--version", action="version", version=f"annofabcli {annofabcli.__version__}")
    parser.set_defaults(command_help=parser.print_help)

    subparsers = parser.add_subparsers(dest="command_name")

    annofabcli.annotation.subcommand_annotation.add_parser(subparsers)
    annofabcli.annotation_specs.subcommand_annotation_specs.add_parser(subparsers)
    annofabcli.comment.subcommand_comment.add_parser(subparsers)
    annofabcli.input_data.subcommand_input_data.add_parser(subparsers)
    annofabcli.instruction.subcommand_instruction.add_parser(subparsers)
    annofabcli.job.subcommand_job.add_parser(subparsers)
    annofabcli.my_account.subcommand_my_account.add_parser(subparsers)
    annofabcli.organization.subcommand_organization.add_parser(subparsers)
    annofabcli.organization_member.subcommand_organization_member.add_parser(subparsers)
    annofabcli.project.subcommand_project.add_parser(subparsers)
    annofabcli.project_member.subcommand_project_member.add_parser(subparsers)
    annofabcli.statistics.subcommand_statistics.add_parser(subparsers)
    annofabcli.stat_visualization.subcommand_stat_visualization.add_parser(subparsers)
    annofabcli.supplementary.subcommand_supplementary.add_parser(subparsers)
    annofabcli.task.subcommand_task.add_parser(subparsers)
    annofabcli.task_history.subcommand_task_history.add_parser(subparsers)
    annofabcli.task_history_event.subcommand_task_history_event.add_parser(subparsers)

    annofabcli.filesystem.subcommand_filesystem.add_parser(subparsers)
    annofabcli.experimental.subcommand_experimental.add_parser(subparsers)

    return parser


if __name__ == "__main__":
    main()
