import argparse
import logging
from enum import Enum
from typing import Any, Dict, List, Optional  # pylint: disable=unused-import

from annofabapi.models import JobType

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class DownloadTarget(Enum):
    TASK = "task"
    INSPECTION_COMMENT = "inspection_comment"
    TASK_HISTORY_EVENT = "task_history_event"
    SIMPLE_ANNOTATION = "simple_annotation"
    FULL_ANNOTATION = "full_annotation"


class Download(AbstractCommandLineInterface):
    def download(self, target: DownloadTarget, project_id: str, output: str, latest: bool = False):
        MAX_JOB_ACCESS = 30
        JOB_ACCESS_INTERVAL = 60
        MAX_WAIT_MINUTU = MAX_JOB_ACCESS * JOB_ACCESS_INTERVAL / 60
        if target == DownloadTarget.TASK:
            if latest:
                self.service.api.post_project_tasks_update(project_id)
                result = self.service.wrapper.wait_for_completion(project_id, job_type=JobType.GEN_TASKS_LIST,
                                                                  job_access_interval=JOB_ACCESS_INTERVAL,
                                                                  max_job_access=MAX_JOB_ACCESS)
                if result:
                    logger.info(f"タスクファイルの更新が完了しました。")
                else:
                    logger.info(f"タスクファイルの更新に失敗しました or {MAX_WAIT_MINUTU} 分待っても、更新が完了しませんでした。")
                    return

            self.service.wrapper.download_project_tasks_url(project_id, output)

        elif target == DownloadTarget.INSPECTION_COMMENT:
            self.service.wrapper.download_project_inspections_url(project_id, output)

        elif target == DownloadTarget.TASK_HISTORY_EVENT:
            self.service.wrapper.download_project_task_history_events_url(project_id, output)

        elif target in [DownloadTarget.SIMPLE_ANNOTATION, DownloadTarget.FULL_ANNOTATION, DownloadTarget.TASK]:
            if latest:
                self.service.api.post_annotation_archive_update(project_id)
                result = self.service.wrapper.wait_for_completion(project_id, job_type=JobType.GEN_ANNOTATION,
                                                                  job_access_interval=60, max_job_access=30)
                if result:
                    logger.info(f"アノテーションの更新が完了しました。")
                else:
                    logger.info(f"アノテーションの更新に失敗しました or {MAX_WAIT_MINUTU} 分待っても、更新が完了しませんでした。")
                    return

            if target == DownloadTarget.SIMPLE_ANNOTATION:
                self.service.wrapper.download_annotation_archive(project_id, output, v2=True)

            elif target == DownloadTarget.FULL_ANNOTATION:
                self.service.wrapper.download_full_annotation_archive(project_id, output)

        logger.info(f"ダウンロードが完了しました。output={output}")

    @staticmethod
    def validate(args: argparse.Namespace):
        download_target = DownloadTarget(args.target)
        if args.latest:
            if download_target not in [
                    DownloadTarget.TASK, DownloadTarget.SIMPLE_ANNOTATION, DownloadTarget.FULL_ANNOTATION
            ]:
                logger.warning(f"ダウンロード対象が`task`, `simple_annotation`, `full_annotation`以外のときは、`--latest`オプションは無視されます。")

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            return

        self.download(DownloadTarget(args.target), args.project_id, args.output, latest=args.latest)


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    Download(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    target_choices = [e.value for e in DownloadTarget]

    parser.add_argument('target', type=str, choices=target_choices, help='ダウンロード対象の項目を指定します。')

    parser.add_argument('-p', '--project_id', type=str, required=True, help='対象のプロジェクトのproject_idを指定します。')

    parser.add_argument('-o', '--output', type=str, required=True, help='ダウンロード先を指定します。')

    parser.add_argument(
        '--latest', action='store_true', help='ダウンロード対象を最新化してから、ダウンロードします。アノテーションの最新化は5分以上かかる場合があります。'
        'ダウンロード対象が`task`, `simple_annotation`, `full_annotation`のときのみ、このオプションは有効です。')

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "download"
    subcommand_help = "タスクや検査コメント、アノテーションなどをダウンロードします。"
    description = ("タスクや検査コメント、アノテーションなどをダウンロードします。"
                   "タスク、検査コメント、タスク履歴イベントは毎日AM 02:00 JSTに更新されます。"
                   "アノテーションは毎日AM 03:00 JSTに更新されます。")
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
