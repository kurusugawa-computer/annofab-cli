import argparse
import logging
from typing import List, Optional, Sequence  # pylint: disable=unused-import

import annofabcli.cancel_acceptance
import annofabcli.download
import annofabcli.complete_tasks
import annofabcli.diff_projects
import annofabcli.invite_users
import annofabcli.print_inspections
import annofabcli.print_label_color
import annofabcli.print_unprocessed_inspections
import annofabcli.reject_tasks
import annofabcli.write_annotation_image

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

    # サブコマンドの定義
    annofabcli.cancel_acceptance.add_parser(subparsers)

    annofabcli.complete_tasks.add_parser(subparsers)

    annofabcli.download.add_parser(subparsers)

    annofabcli.diff_projects.add_parser(subparsers)

    annofabcli.invite_users.add_parser(subparsers)

    annofabcli.print_inspections.add_parser(subparsers)

    annofabcli.print_unprocessed_inspections.add_parser(subparsers)

    annofabcli.print_label_color.add_parser(subparsers)

    annofabcli.reject_tasks.add_parser(subparsers)

    annofabcli.write_annotation_image.add_parser(subparsers)

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
