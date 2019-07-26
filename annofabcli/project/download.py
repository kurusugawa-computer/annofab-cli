"""
検査コメントを付与してタスクを差し戻します。
"""

import argparse
import logging
from enum import Enum
from typing import Any, Dict, List, Optional  # pylint: disable=unused-import

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login
from annofabcli.common.exceptions import AnnofabCliException

logger = logging.getLogger(__name__)


class DownloadTarget(Enum):
    TASK = "task"
    INSPECTION_COMMENT = "inspection_comment"
    TASK_HISTORY_EVENT = "task_history_event"
    SIMPLE_ANNOTATION = "simple_annotation"
    FULL_ANNOTATION = "full_annotation"


class Download(AbstractCommandLineInterface):
    def download_latest_annotation(
            self,
            target: DownloadTarget,
            project_id: str,
            output: str,
    ) -> bool:
        if target == DownloadTarget.SIMPLE_ANNOTATION:
            return self.facade.download_latest_simple_annotation_archive_with_waiting(project_id, output)

        elif target == DownloadTarget.FULL_ANNOTATION:
            return self.facade.download_latest_simple_annotation_archive_with_waiting(project_id, output)
        else:
            raise AnnofabCliException(f"target = {target.value} が不正です。")

    def download(self, target: DownloadTarget, project_id: str, output: str, latest: bool = False):
        if target == DownloadTarget.TASK:
            self.service.wrapper.download_project_tasks_url(project_id, output)

        elif target == DownloadTarget.INSPECTION_COMMENT:
            self.service.wrapper.download_project_inspections_url(project_id, output)

        elif target == DownloadTarget.TASK_HISTORY_EVENT:
            self.service.wrapper.download_project_task_history_events_url(project_id, output)

        elif target in [DownloadTarget.SIMPLE_ANNOTATION, DownloadTarget.FULL_ANNOTATION]:
            if latest:
                # アノテーション情報を最新化してからダウンロードする
                result = self.download_latest_annotation(target, project_id, output)
                if not result:
                    logger.error(f"アノテーションのダウンロードが失敗しました。 target = {target}")

            else:
                if target == DownloadTarget.SIMPLE_ANNOTATION:
                    self.service.wrapper.download_annotation_archive(project_id, output)

                elif target == DownloadTarget.FULL_ANNOTATION:
                    self.service.wrapper.download_full_annotation_archive(project_id, output)

    def main(self):
        args = self.args
        self.download(DownloadTarget(args.target), args.project_id, args.output, latest=args.latest)


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    Download(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    TARGETS = [
        DownloadTarget.TASK.value, DownloadTarget.TASK_HISTORY_EVENT.value, DownloadTarget.INSPECTION_COMMENT.value,
        DownloadTarget.SIMPLE_ANNOTATION.value, DownloadTarget.FULL_ANNOTATION.value
    ]

    parser.add_argument('target', type=str, choices=TARGETS, help='ダウンロード対象の項目を指定します。')

    parser.add_argument('-p', '--project_id', type=str, required=True, help='対象のプロジェクトのproject_idを指定します。')

    parser.add_argument('-o', '--output', type=str, required=True, help='ダウンロード先を指定します。')

    parser.add_argument(
        '--latest', action='store_true', help='最新のアノテーションをダウンロードする場合は指定してください。'
        'ただしアノテーション情報を更新するのに数分かかります。'
        'タスク、検査コメント、タスク履歴イベントに対しては無視されます。')

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "download"
    subcommand_help = "タスクや検査コメント、アノテーションなどをダウンロードします。"
    description = ("タスクや検査コメント、アノテーションなどをダウンロードします。" "タスク、検査コメント、タスク履歴イベントは毎日AM 02:00 JSTに更新されます。")
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
