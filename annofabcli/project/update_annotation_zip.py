import argparse
import logging
import multiprocessing
from functools import partial
from typing import List, Optional

import annofabapi
import dateutil
from annofabapi.models import JobStatus, ProjectJobType, ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    get_wait_options_from_args,
)
from annofabcli.common.dataclasses import WaitOptions

logger = logging.getLogger(__name__)

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=300, max_tries=72)


class SubUpdateAnnotationZip:
    """
    `AbstractCommandLineInterface`を継承したクラスだと、`multiprocessing.Pool`を実行したときに
    `AttributeError: Can't pickle local object 'ArgumentParser.__init__.<locals>.identity'`というエラーが発生したので、
    `ArgumentParser`を除いたクラスを作成した。
    """

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade):
        self.service = service
        self.facade = facade

    def _should_update_annotation_zip(self, project_id: str) -> bool:
        """
        アノテーションzipを更新する必要があるかどうか

        Args:
            project_id:

        Returns:
            True:アノテーションzipを更新する必要がある。

        """
        project, _ = self.service.api.get_project(project_id)
        last_tasks_updated_datetime = project["summary"]["last_tasks_updated_datetime"]
        logger.debug(f"project_id={project_id}: タスクの最終更新日時={last_tasks_updated_datetime}")
        if last_tasks_updated_datetime is None:
            logger.debug(f"project_id={project_id}: タスクがまだ作成されていないので、アノテーションzipを更新する必要はありません。")
            return False

        annotation_specs_history = self.service.api.get_annotation_specs_histories(project_id)[0]
        annotation_specs_updated_datetime = annotation_specs_history[-1]["updated_datetime"]
        logger.debug(f"project_id={project_id}: アノテーション仕様の最終更新日時={annotation_specs_updated_datetime}")

        job_list = self.service.api.get_project_job(
            project_id, query_params={"type": ProjectJobType.GEN_ANNOTATION.value, "limit": 1}
        )[0]["list"]

        if len(job_list) == 0:
            return True

        job = job_list[0]
        logger.debug(
            f"project_id={project_id}: 最後にアノテーションzipを更新しときの情報: "
            f"最終更新日時={job['updated_datetime']}, job_status={job['job_status']}"
        )
        job_status = JobStatus(job["job_status"])
        if job_status == JobStatus.SUCCEEDED:
            if dateutil.parser.parse(job["updated_datetime"]) < dateutil.parser.parse(last_tasks_updated_datetime):
                return True

            elif dateutil.parser.parse(job["updated_datetime"]) < dateutil.parser.parse(
                annotation_specs_updated_datetime
            ):
                return True
            else:
                logger.debug(
                    f"project_id={project_id}: タスクの最終更新日時 or アノテーション仕様の最終更新日時が、"
                    f"アノテーションzipの最終更新日時より古いため、アノテーションzipを更新する必要はありません。"
                )
                return False
        else:
            return True

    def _wait_for_completion_updated_annotation(self, project_id: str, wait_options: Optional[WaitOptions] = None):
        """
        アノテーションzipの更新が完了するまで待ちます。
        """
        if wait_options is None:
            wait_options = DEFAULT_WAIT_OPTIONS

        MAX_WAIT_MINUTU = wait_options.max_tries * wait_options.interval / 60
        result = self.service.wrapper.wait_for_completion(
            project_id,
            job_type=ProjectJobType.GEN_ANNOTATION,
            job_access_interval=wait_options.interval,
            max_job_access=wait_options.max_tries,
        )
        if result:
            logger.info(f"project_id={project_id}: アノテーションzipの更新が完了しました。")
        else:
            logger.info(f"project_id={project_id}: アノテーションzipの更新に失敗、または{MAX_WAIT_MINUTU}分待ってもアノテーションzipの更新が終了しませんでした。")
        return result

    def _update_annotation_zip_for_project(self, project_id: str) -> None:
        job_list = self.service.api.get_project_job(
            project_id, query_params={"type": ProjectJobType.GEN_ANNOTATION.value, "limit": 1}
        )[0]["list"]
        if len(job_list) > 0:
            job = job_list[0]
            if job["job_status"] == JobStatus.PROGRESS.value:
                logger.info(f"project_id={project_id}: アノテーションzipの更新処理が既に実行されています。")
                return

        self.service.api.post_annotation_archive_update(project_id)
        logger.info(f"project_id={project_id}: アノテーションzipの更新処理が開始されました。")

    def execute_for_project(
        self, project_id: str, force: bool = False, wait: bool = False, wait_options: Optional[WaitOptions] = None
    ) -> None:
        """
        1つのプロジェクトに対して、アノテーションzipを更新して、必要なら更新が完了するまで待ちます。
        """
        project = self.service.wrapper.get_project_or_none(project_id)
        if project is None:
            logger.warning(f"project_id={project_id}: プロジェクトにアクセスできません。")
            return

        logger.debug(f"project_id={project_id}: project_title='{project['title']}'")
        if not self.facade.contains_any_project_member_role(
            project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER]
        ):
            logger.warning(f"project_id={project_id}: オーナロールまたはアノテーションユーザロールでないため、アノテーションzipを更新できません。")
            return

        if not force:
            should_update = self._should_update_annotation_zip(project_id)
        else:
            should_update = True

        if should_update:
            self._update_annotation_zip_for_project(project_id)
            if wait:
                self._wait_for_completion_updated_annotation(project_id, wait_options)
        else:
            logger.info(f"project_id={project_id}: アノテーションzipを更新する必要がないので、何も処理しません。")


class UpdateAnnotationZip(AbstractCommandLineInterface):
    def update_annotation_zip(
        self,
        project_id_list: List[str],
        force: bool = False,
        wait: bool = False,
        wait_options: Optional[WaitOptions] = None,
        parallelism: Optional[int] = None,
    ) -> None:
        """
        複数プロジェクトに対して、アノテーションzipを更新する。

        Args:
            project_id_list:
            force: アノテーションzipを更新する必要がなくても、常に更新する。
            wait: アノテーションzipの更新が完了するまで待つかどうか
            wait_options: アノテーションzipの更新が完了するまで待つときのオプション
            parallelism: 並列度
        """
        obj = SubUpdateAnnotationZip(service=self.service, facade=self.facade)
        processes = parallelism if parallelism is not None else len(project_id_list)
        # project_idごとに並列で処理します
        partial_func = partial(obj.execute_for_project, force=force, wait=wait, wait_options=wait_options)
        with multiprocessing.Pool(processes) as pool:
            pool.map(partial_func, project_id_list)

    def main(self):
        args = self.args

        project_id_list = annofabcli.common.cli.get_list_from_args(args.project_id)

        wait_options = get_wait_options_from_args(get_json_from_args(args.wait_options), DEFAULT_WAIT_OPTIONS)
        self.update_annotation_zip(
            project_id_list=project_id_list,
            force=args.force,
            wait=args.wait,
            wait_options=wait_options,
        )


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateAnnotationZip(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "-p",
        "--project_id",
        type=str,
        nargs="+",
        required=True,
        help="対象のプロジェクトのproject_idを指定します。 ``file://`` を先頭に付けると、project_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "--force", action="store_true", help="アノテーションzipを常に更新します。指定しない場合は、アノテーションzipを更新する必要がなければ更新しません。"
    )

    parser.add_argument("--wait", action="store_true", help="アノテーションzipの更新が完了するまで待ちます。")

    parser.add_argument(
        "--wait_options",
        type=str,
        help="アノテーションzipの最新化が完了するまで待つ際のオプションを、JSON形式で指定してください。"
        " ``file://`` を先頭に付けるとjsonファイルを指定できます。"
        'デフォルとは ``{"interval":300, "max_tries":72}`` です。'
        " ``interval`` :完了したかを問い合わせる間隔[秒], "
        " ``max_tires`` :完了したかの問い合わせを最大何回行うか。",
    )

    parser.add_argument("--parallelism", type=int, help="並列度。指定しない場合は、project_idの個数が並列度になります。")
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "update_annotation_zip"
    subcommand_help = "アノテーションzipを更新します。"
    description = "アノテーションzipを更新します。"
    epilog = "対象プロジェクトに対して、オーナまたはアノテーションユーザロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
