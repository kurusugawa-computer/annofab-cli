import argparse
import logging
from pathlib import Path
from typing import Optional

from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class DownloadingInspectionComment(AbstractCommandLineInterface):
    def download_inspection_comment_json(self, project_id: str, output_file: Path):
        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
        project_title = self.facade.get_project_title(project_id)
        logger.info(f"{project_title} の検査コメント全件ファイルをダウンロードします。")

        obj = DownloadingFile(self.service)
        obj.download_inspection_comment_json(
            project_id,
            str(output_file),
        )
        logger.info(f"検査コメント全件ファイルをダウンロードしました。output={output_file}")

    def main(self):
        args = self.args

        self.download_inspection_comment_json(
            args.project_id,
            output_file=args.output,
        )


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DownloadingInspectionComment(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument("-p", "--project_id", type=str, required=True, help="対象のプロジェクトのproject_idを指定します。")

    parser.add_argument("-o", "--output", type=Path, required=True, help="ダウンロード先を指定します。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "download"
    subcommand_help = "検査コメント全件ファイルをダウンロードします。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description=subcommand_help, epilog=epilog
    )
    parse_args(parser)
    return parser
