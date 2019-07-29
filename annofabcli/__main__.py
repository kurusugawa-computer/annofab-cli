import argparse
import logging
from typing import Optional, Sequence  # pylint: disable=unused-import

import annofabcli.annotation.subcommand_annotation
import annofabcli.annotation_specs.print_label_color
import annofabcli.annotation_specs.subcommand_annotation_specs
import annofabcli.inspection_comment.list_inspections
import annofabcli.inspection_comment.list_unprocessed_inspections
import annofabcli.inspection_comment.subcommand_inspection_comment
import annofabcli.project.diff_projects
import annofabcli.project.download
import annofabcli.project.subcommand_project
import annofabcli.project_member.delete_users
import annofabcli.project_member.invite_users
import annofabcli.project_member.list_users
import annofabcli.project_member.subcommand_project_member
import annofabcli.task.cancel_acceptance
import annofabcli.task.complete_tasks
import annofabcli.task.reject_tasks
import annofabcli.task.subcommand_task
import annofabcli.write_annotation_image

logger = logging.getLogger(__name__)


def main(arguments: Optional[Sequence[str]] = None):
    """
    annofabcliコマンドのメイン処理
    注意： `deprecated`なツールは、サブコマンド化しない。

    Args:
        arguments: コマンドライン引数。テストコード用

    """

    parser = argparse.ArgumentParser(description="annofabapiを使ったCLIツール")
    parser.add_argument('--version', action='version', version=f'annofabcli {annofabcli.__version__}')

    subparsers = parser.add_subparsers()

    annofabcli.annotation.subcommand_annotation.add_parser(subparsers)
    annofabcli.inspection_comment.subcommand_inspection_comment.add_parser(subparsers)
    annofabcli.task.subcommand_task.add_parser(subparsers)
    annofabcli.project.subcommand_project.add_parser(subparsers)
    annofabcli.project_member.subcommand_project_member.add_parser(subparsers)
    annofabcli.annotation_specs.subcommand_annotation_specs.add_parser(subparsers)

    # サブコマンドの定義
    annofabcli.project.download.add_parser(subparsers)

    annofabcli.inspection_comment.list_unprocessed_inspections.add_parser_deprecated(subparsers)

    annofabcli.write_annotation_image.add_parser(subparsers)

    # deprecated コマンド
    annofabcli.task.complete_tasks.add_parser_deprecated(subparsers)
    annofabcli.task.reject_tasks.add_parser_dprecated(subparsers)
    annofabcli.task.cancel_acceptance.add_parser(subparsers)
    annofabcli.inspection_comment.list_inspections.add_parser_deprecated(subparsers)
    annofabcli.project.diff_projects.add_parser_deprecated(subparsers)
    annofabcli.project_member.invite_users.add_parser_deprecated(subparsers)
    annofabcli.annotation_specs.print_label_color.add_parser_deprecated(subparsers)

    if arguments is None:
        args = parser.parse_args()
    else:
        args = parser.parse_args(arguments)

    if hasattr(args, 'subcommand_func'):
        try:
            args.subcommand_func(args)
        except Exception as e:
            logger.exception(e)
            raise e

    else:
        # 未知のサブコマンドの場合はヘルプを表示
        parser.print_help()


if __name__ == "__main__":
    main()
