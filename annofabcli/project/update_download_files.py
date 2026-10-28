import argparse
import logging
from collections.abc import Collection
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum

import annofabapi
from annofabapi.models import ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile
from annofabcli.common.exceptions import UpdatedFileForDownloadingError
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class DownloadFileTarget(Enum):
    TASK = "task"
    ANNOTATION = "annotation"
    INPUT_DATA = "input_data"


class UpdateDownloadFilesMain:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service

    def update_download_files(self, project_id: str, targets: Collection[DownloadFileTarget]) -> None:
        """指定したダウンロード用ファイルを並列に更新し、すべての完了を待つ。

        Args:
            project_id: 対象のプロジェクトID。
            targets: 更新対象。同じ対象を複数指定しても更新は1回だけ行う。

        Returns:
            None

        Raises:
            UpdatedFileForDownloadingError: いずれかの更新要求・待機に失敗した場合。
        """
        downloader = DownloadingFile(self.service)
        update_functions = {
            DownloadFileTarget.TASK: downloader.wait_until_updated_task_json,
            DownloadFileTarget.ANNOTATION: downloader.wait_until_updated_annotation_zip,
            DownloadFileTarget.INPUT_DATA: downloader.wait_until_updated_input_data_json,
        }
        unique_targets = list(dict.fromkeys(targets))
        if not unique_targets:
            raise ValueError("更新対象を1個以上指定してください。")

        logger.info(f"project_id='{project_id}' :: {len(unique_targets)}件のダウンロード用ファイルを並列に更新します。")
        failure_targets = []
        with ThreadPoolExecutor(max_workers=len(unique_targets)) as executor:
            futures = {executor.submit(update_functions[target], project_id): target for target in unique_targets}
            for index, future in enumerate(as_completed(futures)):
                target = futures[future]
                try:
                    future.result()
                    logger.info(f"{index + 1}/{len(unique_targets)}件目 :: target='{target.value}'の更新が完了しました。")
                except Exception:
                    failure_targets.append(target.value)
                    logger.warning(f"{index + 1}/{len(unique_targets)}件目 :: target='{target.value}'の更新に失敗しました。", exc_info=True)

        logger.info(f"ダウンロード用ファイルの更新処理が終了しました。 :: 成功: {len(unique_targets) - len(failure_targets)}件, 失敗: {len(failure_targets)}件")
        if failure_targets:
            raise UpdatedFileForDownloadingError(f"ダウンロード用ファイルの更新に失敗しました。 :: target={failure_targets}")


class UpdateDownloadFiles(CommandLine):
    def main(self) -> None:
        args = self.args
        self.require_project_access(args.project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
        UpdateDownloadFilesMain(self.service).update_download_files(args.project_id, [DownloadFileTarget(target) for target in args.target])


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateDownloadFiles(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    ArgumentParser(parser).add_project_id()
    parser.add_argument(
        "--target",
        choices=[target.value for target in DownloadFileTarget],
        nargs="+",
        required=True,
        help="更新対象を1個以上指定します。task: タスク全件JSON、annotation: アノテーションZIP、input_data: 入力データ全件JSON。重複指定した対象は1回だけ更新します。",
    )
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "update_download_files"
    subcommand_help = "ダウンロード用ファイルを並列に更新し、すべての更新完了を待ちます。"
    description = (
        "指定したダウンロード用ファイルをAnnofab上で並列に更新します。ローカルへのダウンロードは行いません。"
        "同種の更新ジョブが実行中の場合は、そのジョブの完了を待ちます。"
        "60秒間隔で完了を確認し、各更新を最大6時間待ちます。"
        "一部の更新に失敗してもほかの更新の完了を待ち、いずれかが失敗またはタイムアウトした場合は非0の終了コードで終了します。"
    )
    parser = annofabcli.common.cli.add_parser(
        subparsers,
        subcommand_name,
        subcommand_help,
        description,
        epilog="オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。",
    )
    parse_args(parser)
    return parser
