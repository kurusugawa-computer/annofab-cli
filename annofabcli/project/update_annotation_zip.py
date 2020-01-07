import argparse
import logging
from enum import Enum
from typing import List, Optional
from annofabapi.models import JobStatus, JobType
import multiprocessing
import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login, get_json_from_args, ArgumentParser
from annofabcli.common.dataclasses import WaitOptions
import dateutil

logger = logging.getLogger(__name__)

class Download(AbstractCommandLineInterface):
    def should_update_annotation_zip(self, project_id: str):
        project, _ = self.service.api.get_project(project_id)
        last_tasks_updated_datetime = project["summary"]["last_tasks_updated_datetime"]
        logger.debug(f"タスクの最終更新日時={last_tasks_updated_datetime}")

        annotation_specs_history = self.service.api.get_annotation_specs_histories(project_id)[0]
        annotation_specs_updated_datetime = annotation_specs_history[-1]["updated_datetime"]
        logger.debug(f"アノテーション仕様の最終更新日時={annotation_specs_updated_datetime}")

        job_list = self.service.api.get_project_job(
            project_id, query_params={"type": JobType.GEN_ANNOTATION.value, "limit": 1}
        )[0]["list"]

        if len(job_list) == 0:
            return True

        job = job_list[0]
        logger.debug(f"project_id={project_id}: 最後にアノテーションzipを更新しときの情報: 最終更新日時={job['updated_datetime']}, job_status={job['job_status']}")
        job_status = JobStatus(job["job_status"])
        if job_status == JobStatus.SUCCEEDED:
            if dateutil.parser.parse(job["updated_datetime"]) < dateutil.parser.parse(
                last_tasks_updated_datetime
            ):
                return True

            elif dateutil.parser.parse(job["updated_datetime"]) < dateutil.parser.parse(
                annotation_specs_updated_datetime
            ):
                return True
            else:
                logger.info(f"project_id={project_id}: アノテーションzipを更新する必要はありません。")
                return False
        else:
            return True





    def is_job_progress(self, project_id: str, job_type: JobType):
        job_list = self.service.api.get_project_job(project_id, query_params={"type": job_type.value})[0]["list"]
        if len(job_list) > 0:
            if job_list[0]["job_status"] == JobStatus.PROGRESS.value:
                return True

        return False

    def _wait_for_completion_updated_annotation(self, project_id: str, wait_options: WaitOptions):
        MAX_WAIT_MINUTU = wait_options.max_tries * wait_options.interval / 60
        result = self.service.wrapper.wait_for_completion(
            project_id,
            job_type=JobType.GEN_ANNOTATION,
            job_access_interval=wait_options.interval,
            max_job_access=wait_options.max_tries,
        )
        if result:
            logger.info(f"project_id={project_id}: アノテーションzipの更新が完了しました。")
        else:
            logger.info(f"project_id={project_id}: アノテーションzipの更新に失敗、または{MAX_WAIT_MINUTU}分待ってもアノテーションzipの更新が終了しませんでした。")

        return result

    def update_annotation_zip_for_project(
        self, project_id: str
    ) -> None:
        job_list = self.service.api.get_project_job(
            project_id, query_params={"type": JobType.GEN_ANNOTATION.value, "limit": 1}
        )[0]["list"]
        if len(job_list) > 0:
            job = job_list[0]
            if job["job_status"] == JobStatus.PROGRESS.value:
                logger.info(
                    f"project_id={project_id}: アノテーションzipの更新処理が既に実行されています。")
                return

        self.service.api.post_annotation_archive_update(project_id)
        logger.info(
            f"project_id={project_id}: アノテーションzipの更新処理が開始されました。")

    def update_annotation_zip_and_wait_for_project(
        self, project_id: str, wait_options: WaitOptions
    ) -> None:
        self.update_annotation_zip_for_project(project_id)
        self._wait_for_completion_updated_annotation(project_id, wait_options)


    def hoge(self, project_id: str, wait:bool=False, force:bool=False):
        # validate
        if not force:
            should_update = self.should_update_annotation_zip(project_id)
        else:
            should_update = True

        if should_update:
            self.update_annotation_zip_for_project(project_id)
            if wait:
                self._wait_for_completion_updated_annotation(project_id, wait_options)
        else:
            logger.info("アノテーションzipを更新する必要はいです。")

    def update_annotation_zip(
        self, project_id_list: List[str], wait: bool = False, wait_options: Optional[WaitOptions]=None, parallelism: Optional[int]=None
    ) -> None:
        """
        複数プロジェクトに対して、アノテーションzipを更新する。

        Args:
            project_id:
            csv_file: タスク登録に関する情報が記載されたCSV
            wait_options: タスク登録の完了を待つ処理
            wait: タスク登録が完了するまで待つかどうか
        """
        processes = parallelism if parallelism is not None else len(project_id_list)
        with multiprocessing.Pool(processes) as pool:
            pool.map(f, [1, 2, 3])


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
    def get_wait_options_from_args(args: argparse.Namespace) -> Optional[WaitOptions]:
        if args.wait_options is not None:
            return WaitOptions.from_dict(get_json_from_args(args.wait_options))  # type: ignore
        else:
            return None

    def main(self):
        args = self.args

        # super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])
        project_id_list = annofabcli.common.cli.get_list_from_args(args.project_id)

        wait_options = self.get_wait_options_from_args(args)
        self.update_annotation_zip(
            project_id_list=project_id_list,
            wait=args.wait,
            wait_options=wait_options,
        )


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    Download(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument("-p", "--project_id", type=str, nargs="+",
                        help="対象のプロジェクトのproject_idを指定します。"
                             "`file://`を先頭に付けると、project_idの一覧が記載されたファイルを指定できます。")

    parser.add_argument("--wait", action="store_true", help="アノテーションzipの最新化が完了するまで待ちます。")

    parser.add_argument(
        "--wait_options",
        type=str,
        help="アノテーションzipの最新化が完了するまで待つ際のオプションを、JSON形式で指定してください。"
        "`file://`を先頭に付けるとjsonファイルを指定できます。"
        'デフォルとは`{"interval":300, "max_tries":120}` です。'
        "`interval`:完了したかを問い合わせる間隔[秒], "
        "`max_tires`:完了したかの問い合わせを最大何回行うか。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "update_annotation_zip"
    subcommand_help = "アノテーションzipを最新化します。"
    description = "アノテーションzipを最新化します。"
    epilog = "オーナまたはアノテーションユーザロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
