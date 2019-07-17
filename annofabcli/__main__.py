import argparse
import logging
from typing import Optional, Sequence  # pylint: disable=unused-import

import annofabcli.task.cancel_acceptance
import annofabcli.task.complete_tasks
import annofabcli.project_member.delete_users
import annofabcli.project.diff_projects
import annofabcli.download
import annofabcli.project_member.invite_users
import annofabcli.project_member.list_users
import annofabcli.inspection.print_inspections
import annofabcli.print_label_color
import annofabcli.print_unprocessed_inspections
import annofabcli.task.reject_tasks
import annofabcli.write_annotation_image
import annofabcli.subcommand_task
import annofabcli.subcommand_inspection
import annofabcli.subcommand_project_member


logger = logging.getLogger(__name__)


def main(arguments: Optional[Sequence[str]] = None):
    """
    annofabcliコマンドのメイン処理
    注意： `deprecated`なツールは、サブコマンド化しない。

    Args:
        arguments: コマンドライン引数。テストコード用

    """

    # loggerの設定
    annofabcli.utils.set_default_logger()

    parser = argparse.ArgumentParser(description="annofabapiを使ったCLIツール")
    parser.add_argument('--version', action='version', version=f'annofabcli {annofabcli.__version__}')

    subparsers = parser.add_subparsers()

    annofabcli.subcommand_task.add_parser(subparsers)
    annofabcli.subcommand_inspection.add_parser(subparsers)
    annofabcli.subcommand_project_member.add_parser(subparsers)

    # サブコマンドの定義


    annofabcli.download.add_parser(subparsers)

    annofabcli.project.diff_projects.add_parser(subparsers)

    annofabcli.print_unprocessed_inspections.add_parser(subparsers)

    annofabcli.print_label_color.add_parser(subparsers)

    annofabcli.write_annotation_image.add_parser(subparsers)

    # deprecated コマンド
    annofabcli.task.complete_tasks.add_parser_deprecated(subparsers)
    annofabcli.task.reject_tasks.add_parser_dprecated(subparsers)
    annofabcli.task.cancel_acceptance.add_parser(subparsers)

    annofabcli.inspection.print_inspections.add_parser_deprecated(subparsers)

    annofabcli.project_member.list_users.add_parser_deprecated(subparsers)
    annofabcli.project_member.invite_users.add_parser_deprecated(subparsers)
    annofabcli.project_member.delete_users.add_parser_deprecated(subparsers)


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
