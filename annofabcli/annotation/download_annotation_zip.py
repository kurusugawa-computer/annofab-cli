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


class DownloadingAnnotationZip(CommandLine):
    def download_annotation_zip(self, project_id: str, output_zip: Path, is_latest: bool, should_download_full_annotation: bool = False):  # noqa: ANN201, FBT001, FBT002
        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        project_title = self.facade.get_project_title(project_id)
        logger.info(f"{project_title} のアノテーションZIPをダウンロードします。")

        obj = DownloadingFile(self.service)
        obj.download_annotation_zip(
            project_id,
            str(output_zip),
            is_latest=is_latest,
            should_download_full_annotation=should_download_full_annotation,
        )
        logger.info(f"アノテーションZIPをダウンロードしました。output={output_zip}")

    def main(self) -> None:
        args = self.args

        self.download_annotation_zip(
            args.project_id,
            output_zip=args.output,
            is_latest=args.latest,
            should_download_full_annotation=args.download_full_annotation,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DownloadingAnnotationZip(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-p", "--project_id", type=str, required=True, help="対象のプロジェクトのproject_idを指定します。")

    parser.add_argument("-o", "--output", type=Path, required=True, help="ダウンロード先を指定します。")

    parser.add_argument(
        "--latest",
        action="store_true",
        help="現在のアノテーションの状態をアノテーションZIPに反映させてから、ダウンロードします。アノテーションZIPへの反映には、データ数に応じて数分から数十分かかります。",
    )

    parser.add_argument(
        "--download_full_annotation",
        action="store_true",
        help="[DEPRECATED] FullアノテーションZIPをダウンロードします。このオプションは、廃止予定のため非推奨です。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "download"
    subcommand_help = "アノテーションZIPをダウンロードします。"
    description = "アノテーションZIPをダウンロードします。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
