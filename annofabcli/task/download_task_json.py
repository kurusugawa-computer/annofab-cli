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


class DownloadingTaskJson(AbstractCommandLineInterface):
    def download_task_json(self, project_id: str, output_file: Path, is_latest: bool):
        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
        project_title = self.facade.get_project_title(project_id)
        logger.info(f"{project_title} のタスク全件ファイルをダウンロードします。")

        obj = DownloadingFile(self.service)
        obj.download_task_json(
            project_id,
            str(output_file),
            is_latest=is_latest,
        )
        logger.info(f"タスク全件ファイルをダウンロードしました。output={output_file}")

    def main(self):
        args = self.args

        self.download_task_json(
            args.project_id,
            output_file=args.output,
            is_latest=args.latest,
        )


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DownloadingTaskJson(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument("-p", "--project_id", type=str, required=True, help="対象のプロジェクトのproject_idを指定します。")

    parser.add_argument("-o", "--output", type=Path, required=True, help="ダウンロード先を指定します。")

    parser.add_argument(
        "--latest",
        action="store_true",
        help="現在のタスクの状態をタスク全件ファイルに反映させてから、ダウンロードします。タスク全件ファイルへの反映には、データ数に応じて数分から数十分かかります。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "download"
    subcommand_help = "タスク全件ファイルをダウンロードします。"
    description = "タスク全件ファイルをダウンロードします。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
