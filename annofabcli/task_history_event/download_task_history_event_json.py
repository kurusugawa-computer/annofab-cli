import argparse
import logging
from pathlib import Path
from typing import Optional

from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class DownloadingTaskHistoryEvent(CommandLine):
    def download_task_history_event_json(self, project_id: str, output_file: Path):  # noqa: ANN201
        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
        project_title = self.facade.get_project_title(project_id)
        logger.info(f"{project_title} のタスク履歴イベント全件ファイルをダウンロードします。")

        obj = DownloadingFile(self.service)
        obj.download_task_history_event_json(
            project_id,
            str(output_file),
        )
        logger.info(f"タスク履歴イベント全件ファイルをダウンロードしました。output={output_file}")

    def main(self) -> None:
        args = self.args

        self.download_task_history_event_json(
            args.project_id,
            output_file=args.output,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DownloadingTaskHistoryEvent(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-p", "--project_id", type=str, required=True, help="対象のプロジェクトのproject_idを指定します。")

    parser.add_argument("-o", "--output", type=Path, required=True, help="ダウンロード先を指定します。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "download"
    subcommand_help = "タスク履歴イベント全件ファイルをダウンロードします。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
