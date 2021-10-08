import argparse
import logging
import sys
from enum import Enum
from typing import Any, Callable, Optional

from annofabapi.models import JobStatus, ProjectJobType

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    get_wait_options_from_args,
)
from annofabcli.common.dataclasses import WaitOptions

logger = logging.getLogger(__name__)

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)


class DownloadTarget(Enum):
    TASK = "task"
    INPUT_DATA = "input_data"
    INSPECTION_COMMENT = "inspection_comment"
    TASK_HISTORY = "task_history"
    TASK_HISTORY_EVENT = "task_history_event"
    SIMPLE_ANNOTATION = "simple_annotation"
    FULL_ANNOTATION = "full_annotation"


class Download(AbstractCommandLineInterface):
    def is_job_progress(self, project_id: str, job_type: ProjectJobType):
        job_list = self.service.api.get_project_job(project_id, query_params={"type": job_type.value})[0]["list"]
        if len(job_list) > 0:
            if job_list[0]["job_status"] == JobStatus.PROGRESS.value:
                return True

        return False

    def update_file_and_wait(
        self, project_id: str, job_type: ProjectJobType, update_func: Callable[[str], Any], wait_options: WaitOptions
    ) -> None:
        """
        最新化処理が完了するまで待つ。
        """
        MAX_WAIT_MINUTES = wait_options.max_tries * wait_options.interval / 60

        if self.is_job_progress(project_id, job_type=job_type):
            logger.info(f"ダウンロード対象の最新化処理が既に実行されています。")
        else:
            logger.info(f"ダウンロード対象の最新化処理を実行します。")
            update_func(project_id)

        logger.info(f"ダウンロード対象の最新化処理が完了するまで、最大{MAX_WAIT_MINUTES}分間待ちます。")
        result = self.service.wrapper.wait_for_completion(
            project_id,
            job_type=job_type,
            job_access_interval=wait_options.interval,
            max_job_access=wait_options.max_tries,
        )
        if result:
            logger.info(f"ダウンロード対象の最新化処理が完了しました。")
        else:
            logger.info(f"ダウンロードの対象の最新化に失敗したか、または {MAX_WAIT_MINUTES} 分待っても最新化処理が完了しませんでした。")

    def download(self, target: DownloadTarget, project_id: str, output: str, latest: bool, wait_options: WaitOptions):
        project_title = self.facade.get_project_title(project_id)
        logger.info(f"{project_title} の {target.value} をダウンロードします。")

        if target == DownloadTarget.TASK:
            if latest:
                self.update_file_and_wait(
                    project_id, ProjectJobType.GEN_TASKS_LIST, self.service.api.post_project_tasks_update, wait_options
                )

            self.service.wrapper.download_project_tasks_url(project_id, output)

        elif target == DownloadTarget.INPUT_DATA:
            if latest:
                self.update_file_and_wait(
                    project_id,
                    ProjectJobType.GEN_INPUTS_LIST,
                    self.service.api.post_project_inputs_update,
                    wait_options,
                )

            self.service.wrapper.download_project_inputs_url(project_id, output)

        elif target == DownloadTarget.INSPECTION_COMMENT:
            self.service.wrapper.download_project_inspections_url(project_id, output)

        elif target == DownloadTarget.TASK_HISTORY:
            self.service.wrapper.download_project_task_histories_url(project_id, output)

        elif target == DownloadTarget.TASK_HISTORY_EVENT:
            self.service.wrapper.download_project_task_history_events_url(project_id, output)

        elif target in [DownloadTarget.SIMPLE_ANNOTATION, DownloadTarget.FULL_ANNOTATION, DownloadTarget.TASK]:
            if latest:
                self.update_file_and_wait(
                    project_id,
                    ProjectJobType.GEN_ANNOTATION,
                    self.service.api.post_annotation_archive_update,
                    wait_options,
                )

            if target == DownloadTarget.SIMPLE_ANNOTATION:
                self.service.wrapper.download_annotation_archive(project_id, output)

            elif target == DownloadTarget.FULL_ANNOTATION:
                self.service.wrapper.download_full_annotation_archive(project_id, output)

        logger.info(f"ダウンロードが完了しました。output={output}")

    @staticmethod
    def validate(args: argparse.Namespace):
        download_target = DownloadTarget(args.target)
        if args.latest:
            if download_target not in [
                DownloadTarget.TASK,
                DownloadTarget.INPUT_DATA,
                DownloadTarget.SIMPLE_ANNOTATION,
                DownloadTarget.FULL_ANNOTATION,
            ]:
                logger.warning(
                    f"ダウンロード対象が'task', 'input_data', 'simple_annotation', 'full_annotation'以外では`--latest`オプションは無視されます。"
                )

        if download_target in [DownloadTarget.FULL_ANNOTATION, DownloadTarget.TASK_HISTORY_EVENT]:
            logger.warning(f"ダウンロード対象`{download_target.value}`は非推奨です。いずれ廃止されます。")

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        wait_options = get_wait_options_from_args(get_json_from_args(args.wait_options), DEFAULT_WAIT_OPTIONS)
        self.download(
            DownloadTarget(args.target),
            args.project_id,
            output=args.output,
            latest=args.latest,
            wait_options=wait_options,
        )


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    Download(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    target_choices = [e.value for e in DownloadTarget]

    parser.add_argument(
        "target",
        type=str,
        choices=target_choices,
        help="ダウンロード対象の項目を指定します。"
        "simple_annotation: シンプルアノテーションzip, "
        "full_annotation: フルアノテーションzip(非推奨), "
        "task: タスクjson, "
        "input_data: 入力データjson, "
        "inspection_comment: 検査コメントjson, "
        "task_history: タスク履歴json, "
        "task_history_event: タスク履歴イベントjson(非推奨)",
    )

    parser.add_argument("-p", "--project_id", type=str, required=True, help="対象のプロジェクトのproject_idを指定します。")

    parser.add_argument("-o", "--output", type=str, required=True, help="ダウンロード先を指定します。")

    parser.add_argument(
        "--latest",
        action="store_true",
        help="ダウンロード対象を最新化してから、ダウンロードします。ファイルの最新化は5分以上かかる場合があります。"
        "特にsimple_annotation,full_annotationの最新化は1時間以上かかる場合があります。"
        "ダウンロード対象が'task', 'input_data', 'simple_annotation', 'full_annotation'のときのみ、このオプションは有効です。",
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


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "download"
    subcommand_help = "タスクや検査コメント、アノテーションなどをダウンロードします。"
    description = (
        "タスクや検査コメント、アノテーションなどをダウンロードします。" + "タスク、検査コメント、タスク履歴イベントは毎日AM 02:00 JSTに更新されます。"
        "アノテーションは毎日AM 03:00 JSTに更新されます。"
    )
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
