import argparse
import logging
from collections.abc import Collection
from dataclasses import dataclass
from enum import Enum

import annofabapi
from annofabapi.models import ProjectJobType, ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.cli import CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile
from annofabcli.common.exceptions import UpdatedFileForDownloadingError
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)

MAX_PROJECT_COUNT = 4
"""一度に更新できるプロジェクト数の上限。"""


def validate_project_ids(project_ids: Collection[str]) -> None:
    """更新対象のプロジェクト数を検証する。

    Args:
        project_ids: 更新対象のプロジェクトID。

    Returns:
        None

    Raises:
        ValueError: プロジェクト数が1〜4個の範囲外の場合。
    """
    if not 1 <= len(project_ids) <= MAX_PROJECT_COUNT:
        raise ValueError(f"--project_id は1個以上{MAX_PROJECT_COUNT}個以下で指定してください。")


class DownloadFileTarget(Enum):
    TASK = "task"
    ANNOTATION = "annotation"
    INPUT_DATA = "input_data"


@dataclass(frozen=True)
class UpdateJob:
    project_id: str
    """対象のプロジェクトID。"""
    target: DownloadFileTarget
    """更新対象。"""
    job_id: str
    """待機する更新ジョブのID。"""


class UpdateDownloadFilesMain:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service

    def update_download_files(self, project_ids: Collection[str], targets: Collection[DownloadFileTarget]) -> None:
        """指定したダウンロード用ファイルを並列に更新し、すべての完了を待つ。

        Args:
            project_ids: 対象のプロジェクトID。最大4個。
            targets: 更新対象。

        Returns:
            None

        Raises:
            UpdatedFileForDownloadingError: いずれかの更新要求・待機に失敗した場合。
        """
        validate_project_ids(project_ids)
        downloader = DownloadingFile(self.service)
        job_types = {
            DownloadFileTarget.TASK: ProjectJobType.GEN_TASKS_LIST,
            DownloadFileTarget.ANNOTATION: ProjectJobType.GEN_ANNOTATION,
            DownloadFileTarget.INPUT_DATA: ProjectJobType.GEN_INPUTS_LIST,
        }
        unique_targets = list(dict.fromkeys(targets))
        if not unique_targets:
            raise ValueError("更新対象を1個以上指定してください。")

        unique_project_ids = list(dict.fromkeys(project_ids))
        job_count = len(unique_project_ids) * len(unique_targets)
        logger.info(f"{len(unique_project_ids)}件のプロジェクトのダウンロード用ファイル{job_count}件を並列に更新します。")
        failure_targets = []
        jobs = []
        # 完了を待つ前にすべての更新を要求し、Annofab上で並列に実行させる。
        for project_id in unique_project_ids:
            for target in unique_targets:
                log_prefix = f"project_id='{project_id}', target='{target.value}'"
                try:
                    job_id = downloader.request_update(project_id, job_types[target])
                    jobs.append(UpdateJob(project_id, target, job_id))
                except Exception:
                    failure_targets.append(log_prefix)
                    logger.warning(f"{log_prefix}の更新要求に失敗しました。", exc_info=True)

        for index, job in enumerate(jobs):
            log_prefix = f"project_id='{job.project_id}', target='{job.target.value}'"
            try:
                downloader.wait_for_completion(job.project_id, job_types[job.target], job.job_id)
                logger.info(f"{index + 1}/{len(jobs)}件目 :: {log_prefix}の更新が完了しました。")
            except Exception:
                failure_targets.append(log_prefix)
                logger.warning(f"{index + 1}/{len(jobs)}件目 :: {log_prefix}の更新に失敗しました。", exc_info=True)

        logger.info(f"ダウンロード用ファイルの更新処理が終了しました。 :: 成功: {job_count - len(failure_targets)}件, 失敗: {len(failure_targets)}件")
        if failure_targets:
            raise UpdatedFileForDownloadingError(f"ダウンロード用ファイルの更新に失敗しました。 :: target={failure_targets}")


class UpdateDownloadFiles(CommandLine):
    def main(self) -> None:
        args = self.args
        for project_id in dict.fromkeys(args.project_id):
            self.require_project_access(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
        UpdateDownloadFilesMain(self.service).update_download_files(args.project_id, [DownloadFileTarget(target) for target in args.target])


def main(args: argparse.Namespace) -> None:
    try:
        validate_project_ids(args.project_id)
    except ValueError as e:
        args.root_parser.error(str(e))
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateDownloadFiles(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-p", "--project_id", nargs="+", required=True, help="対象のプロジェクトIDを最大4個指定します。")
    parser.add_argument(
        "--target",
        choices=[target.value for target in DownloadFileTarget],
        nargs="+",
        required=True,
        help="更新対象を1個以上指定します。task: タスク全件JSON、annotation: アノテーションZIP、input_data: 入力データ全件JSON。",
    )
    parser.set_defaults(subcommand_func=main)


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "update_download_files"
    subcommand_help = "ダウンロード用ファイルを並列に更新し、すべての更新完了を待ちます。"
    description = (
        "指定したダウンロード用ファイルをAnnofab上で並列に更新します。ローカルへのダウンロードは行いません。"
        "60秒間隔で完了を確認し、各更新を最大6時間待ちます。"
        "一部の更新に失敗してもほかの更新の完了を待ち、いずれかが失敗またはタイムアウトした場合は非0の終了コードで終了します。"
    )
    parser = annofabcli.common.cli.create_parser(
        subparsers,
        subcommand_name,
        subcommand_help,
        description,
        epilog="オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。",
    )
    parse_args(parser)
    return parser
