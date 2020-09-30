import argparse
import logging
from typing import Optional, Sequence

import annofabcli.annotation.subcommand_annotation
import annofabcli.annotation_specs.subcommand_annotation_specs
import annofabcli.experimental.subcommand_experimental
import annofabcli.filesystem.subcommand_filesystem
import annofabcli.input_data.subcommand_input_data
import annofabcli.inspection_comment.subcommand_inspection_comment
import annofabcli.instruction.subcommand_instruction
import annofabcli.job.subcommand_job
import annofabcli.labor.subcommand_labor
import annofabcli.organization_member.subcommand_organization_member
import annofabcli.project.subcommand_project
import annofabcli.project_member.subcommand_project_member
import annofabcli.statistics.subcommand_statistics
import annofabcli.supplementary.subcommand_supplementary
import annofabcli.task.subcommand_task
import annofabcli.task_history.subcommand_task_history

logger = logging.getLogger(__name__)


def main(arguments: Optional[Sequence[str]] = None):
    """
    annofabcliコマンドのメイン処理
    注意： `deprecated`なツールは、サブコマンド化しない。

    Args:
        arguments: コマンドライン引数。テストコード用

    """

    parser = argparse.ArgumentParser(
        description="Command Line Interface for AnnoFab", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--version", action="version", version=f"annofabcli {annofabcli.__version__}")
    parser.set_defaults(command_help=parser.print_help)

    subparsers = parser.add_subparsers(dest="command_name")

    annofabcli.annotation.subcommand_annotation.add_parser(subparsers)
    annofabcli.annotation_specs.subcommand_annotation_specs.add_parser(subparsers)
    annofabcli.input_data.subcommand_input_data.add_parser(subparsers)
    annofabcli.inspection_comment.subcommand_inspection_comment.add_parser(subparsers)
    annofabcli.instruction.subcommand_instruction.add_parser(subparsers)
    annofabcli.job.subcommand_job.add_parser(subparsers)
    annofabcli.labor.subcommand_labor.add_parser(subparsers)
    annofabcli.organization_member.subcommand_organization_member.add_parser(subparsers)
    annofabcli.project.subcommand_project.add_parser(subparsers)
    annofabcli.project_member.subcommand_project_member.add_parser(subparsers)
    annofabcli.statistics.subcommand_statistics.add_parser(subparsers)
    annofabcli.supplementary.subcommand_supplementary.add_parser(subparsers)
    annofabcli.task.subcommand_task.add_parser(subparsers)
    annofabcli.task_history.subcommand_task_history.add_parser(subparsers)

    annofabcli.filesystem.subcommand_filesystem.add_parser(subparsers)
    annofabcli.experimental.subcommand_experimental.add_parser(subparsers)

    if arguments is None:
        args = parser.parse_args()
    else:
        args = parser.parse_args(arguments)

    if hasattr(args, "subcommand_func"):
        try:
            annofabcli.cli.load_logging_config_from_args(args)
            args.subcommand_func(args)
        except Exception as e:
            logger.exception(e)
            raise e

    else:
        # 未知のサブコマンドの場合はヘルプを表示
        args.command_help()


if __name__ == "__main__":
    main()
