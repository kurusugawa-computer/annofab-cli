import argparse
import logging
from enum import Enum

from annofabapi.models import JobStatus, JobType

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login, get_json_from_args
from annofabcli.common.dataclasses import WaitOptions

logger = logging.getLogger(__name__)


class DownloadTarget(Enum):
    TASK = "task"
    INSPECTION_COMMENT = "inspection_comment"
    TASK_HISTORY_EVENT = "task_history_event"
    SIMPLE_ANNOTATION = "simple_annotation"
    FULL_ANNOTATION = "full_annotation"


class Download(AbstractCommandLineInterface):
    def is_job_progress(self, project_id: str, job_type: JobType):
        job_list = self.service.api.get_project_job(project_id, query_params={"type": job_type.value})[0]["list"]
        if len(job_list) > 0:
            if job_list[0]["job_status"] == JobStatus.PROGRESS.value:
                return True

        return False

    def download(self, target: DownloadTarget, project_id: str, output: str, latest: bool, wait_options: WaitOptions):
        MAX_WAIT_MINUTUE = wait_options.max_tries * wait_options.interval / 60
        if latest:
            logger.info(f"最大{MAX_WAIT_MINUTUE}分間、ダウンロード対象が最新化するまで待ちます。")

        if target == DownloadTarget.TASK:
            job_type = JobType.GEN_TASKS_LIST
            if latest:
                if self.is_job_progress(project_id, job_type=job_type):
                    logger.debug(f"ダウンロード対象が最新化ジョブが既に進行中です。")
                else:
                    self.service.api.post_project_tasks_update(project_id)

                result = self.service.wrapper.wait_for_completion(
                    project_id,
                    job_type=job_type,
                    job_access_interval=wait_options.interval,
                    max_job_access=wait_options.max_tries,
                )
                if result:
                    logger.info(f"タスクファイルの更新が完了しました。")
                else:
                    logger.info(f"タスクファイルの更新に失敗しました or {MAX_WAIT_MINUTUE} 分待っても、更新が完了しませんでした。")
                    return

            self.service.wrapper.download_project_tasks_url(project_id, output)

        elif target == DownloadTarget.INSPECTION_COMMENT:
            self.service.wrapper.download_project_inspections_url(project_id, output)

        elif target == DownloadTarget.TASK_HISTORY_EVENT:
            self.service.wrapper.download_project_task_history_events_url(project_id, output)

        elif target in [DownloadTarget.SIMPLE_ANNOTATION, DownloadTarget.FULL_ANNOTATION, DownloadTarget.TASK]:
            if latest:
                job_type = JobType.GEN_ANNOTATION
                if self.is_job_progress(project_id, job_type=job_type):
                    logger.debug(f"ダウンロード対象が最新化ジョブが既に進行中です。")
                else:
                    self.service.api.post_annotation_archive_update(project_id)

                result = self.service.wrapper.wait_for_completion(
                    project_id,
                    job_type=job_type,
                    job_access_interval=wait_options.interval,
                    max_job_access=wait_options.max_tries,
                )
                if result:
                    logger.info(f"アノテーションの更新が完了しました。")
                else:
                    logger.info(f"アノテーションの更新に失敗しました or {MAX_WAIT_MINUTUE} 分待っても、更新が完了しませんでした。")
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
                DownloadTarget.TASK,
                DownloadTarget.SIMPLE_ANNOTATION,
                DownloadTarget.FULL_ANNOTATION,
            ]:
                logger.warning(f"ダウンロード対象が`task`, `simple_annotation`, `full_annotation`以外のときは、`--latest`オプションは無視されます。")

        return True

    @staticmethod
    def get_wait_options_from_args(args: argparse.Namespace) -> WaitOptions:
        if args.wait_options is not None:
            wait_options = WaitOptions.from_dict(get_json_from_args(args.wait_options))  # type: ignore
        else:
            wait_options = WaitOptions(interval=60, max_tries=360)
        return wait_options

    def main(self):
        args = self.args
        if not self.validate(args):
            return

        wait_options = self.get_wait_options_from_args(args)
        self.download(
            DownloadTarget(args.target),
            args.project_id,
            output=args.output,
            latest=args.latest,
            wait_options=wait_options,
        )


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    Download(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    target_choices = [e.value for e in DownloadTarget]

    parser.add_argument("target", type=str, choices=target_choices, help="ダウンロード対象の項目を指定します。")

    parser.add_argument("-p", "--project_id", type=str, required=True, help="対象のプロジェクトのproject_idを指定します。")

    parser.add_argument("-o", "--output", type=str, required=True, help="ダウンロード先を指定します。")

    parser.add_argument(
        "--latest",
        action="store_true",
        help="ダウンロード対象を最新化してから、ダウンロードします。アノテーションの最新化は5分以上かかる場合があります。"
        "ダウンロード対象が`task`, `simple_annotation`, `full_annotation`のときのみ、このオプションは有効です。",
    )

    parser.add_argument(
        "--wait_options",
        type=str,
        help="ダウンロード対象の最新化を待つときのオプションをJSON形式で指定してください。"
        "`file://`を先頭に付けるとjsonファイルを指定できます。"
        'デフォルとは`{"interval":60, "max_tries":360}` です。'
        "`interval`:最新化が完了したかを問い合わせる間隔[秒], "
        "`max_tires`:最新化が完了したかの問い合わせを最大何回行うか。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "download"
    subcommand_help = "タスクや検査コメント、アノテーションなどをダウンロードします。"
    description = (
        "タスクや検査コメント、アノテーションなどをダウンロードします。" "タスク、検査コメント、タスク履歴イベントは毎日AM 02:00 JSTに更新されます。" "アノテーションは毎日AM 03:00 JSTに更新されます。"
    )
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
