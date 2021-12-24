import asyncio
import logging.config
import warnings
from functools import partial
from typing import Optional

import annofabapi
import requests
from annofabapi.models import ProjectJobType

from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.exceptions import DownloadingFileNotFoundError, UpdatedFileForDownloadingError

logger = logging.getLogger(__name__)

DOWNLOADING_FILETYPE_DICT = {
    ProjectJobType.GEN_TASKS_LIST: "タスク全件ファイル",
    ProjectJobType.GEN_INPUTS_LIST: "入力データ全件ファイル",
    ProjectJobType.GEN_ANNOTATION: "アノテーションzip",
}

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)


def _get_annofab_error_message(http_error: requests.HTTPError) -> Optional[str]:
    obj = http_error.response.json()
    errors = obj.get("errors")
    if errors is None:
        return None
    return errors[0].get("message")


class DownloadingFile:
    def __init__(self, service: annofabapi.Resource):
        self.service = service

    @staticmethod
    def get_max_wait_minutes(wait_options: WaitOptions):
        return wait_options.max_tries * wait_options.interval / 60

    def _wait_for_completion(
        self,
        project_id: str,
        job_type: ProjectJobType,
        wait_options: Optional[WaitOptions] = None,
        job_id: Optional[str] = None,
    ):
        if wait_options is None:
            wait_options = DEFAULT_WAIT_OPTIONS

        max_wait_minutes = self.get_max_wait_minutes(wait_options)
        filetype = DOWNLOADING_FILETYPE_DICT[job_type]
        logger.info(f"{filetype}の更新処理が完了するまで、最大{max_wait_minutes}分間待ちます。job_id={job_id}")
        result = self.service.wrapper.wait_for_completion(
            project_id,
            job_type=job_type,
            job_access_interval=wait_options.interval,
            max_job_access=wait_options.max_tries,
        )
        if not result:
            raise UpdatedFileForDownloadingError(f"{filetype}の更新処理が{max_wait_minutes}分以内に完了しない、または更新処理に失敗しました。")

    async def download_annotation_zip_with_async(
        self, project_id: str, dest_path: str, is_latest: bool = False, wait_options: Optional[WaitOptions] = None
    ):
        loop = asyncio.get_event_loop()
        partial_func = partial(self.download_annotation_zip, project_id, dest_path, is_latest, wait_options)
        result = await loop.run_in_executor(None, partial_func)
        return result

    def download_annotation_zip(
        self, project_id: str, dest_path: str, is_latest: bool = False, wait_options: Optional[WaitOptions] = None
    ):
        logger.debug(f"アノテーションzipをダウンロードします。path={dest_path}")
        if is_latest:
            self.wait_until_updated_annotation_zip(project_id, wait_options)
            self.service.wrapper.download_annotation_archive(project_id, dest_path)

        else:
            try:
                self.service.wrapper.download_annotation_archive(project_id, dest_path)
            except requests.HTTPError as e:
                if e.response.status_code == requests.codes.not_found:
                    logger.info(f"アノテーションzipが存在しなかったので、アノテーションzipファイルの更新処理を実行します。")
                    self.wait_until_updated_annotation_zip(project_id, wait_options)
                    self.service.wrapper.download_annotation_archive(project_id, dest_path)
                else:
                    raise e

    def wait_until_updated_annotation_zip(self, project_id: str, wait_options: Optional[WaitOptions] = None):
        job_id = None
        try:
            job = self.service.api.post_annotation_archive_update(project_id)[0]["job"]
            job_id = job["job_id"]
        except requests.HTTPError as e:
            # すでにジョブが進行中の場合は、無視する
            if e.response.status_code == requests.codes.conflict:
                logger.warning(f"別のバックグラウンドジョブが既に実行されているので、更新処理を無視します。")
                logger.warning(f"{_get_annofab_error_message(e)}")
            else:
                raise e

        self._wait_for_completion(
            project_id, job_type=ProjectJobType.GEN_ANNOTATION, wait_options=wait_options, job_id=job_id
        )

    async def download_input_data_json_with_async(
        self, project_id: str, dest_path: str, is_latest: bool = False, wait_options: Optional[WaitOptions] = None
    ):
        loop = asyncio.get_event_loop()
        partial_func = partial(self.download_input_data_json, project_id, dest_path, is_latest, wait_options)
        result = await loop.run_in_executor(None, partial_func)
        return result

    def download_input_data_json(
        self, project_id: str, dest_path: str, is_latest: bool = False, wait_options: Optional[WaitOptions] = None
    ):
        logger.debug(f"入力データ全件ファイルをダウンロードします。path={dest_path}")
        if is_latest:
            self.wait_until_updated_input_data_json(project_id, wait_options)
            self.service.wrapper.download_project_inputs_url(project_id, dest_path)

        else:
            try:
                self.service.wrapper.download_project_inputs_url(project_id, dest_path)
            except requests.HTTPError as e:
                if e.response.status_code == requests.codes.not_found:
                    logger.info(f"入力データ全件ファイルが存在しなかったので、入力データ全件ファイルの更新処理を実行します。")
                    self.wait_until_updated_input_data_json(project_id, wait_options)
                    self.service.wrapper.download_project_inputs_url(project_id, dest_path)
                else:
                    raise e

    def wait_until_updated_input_data_json(self, project_id: str, wait_options: Optional[WaitOptions] = None):
        job_id = None
        try:
            job = self.service.api.post_project_inputs_update(project_id)[0]["job"]
            job_id = job["job_id"]
        except requests.HTTPError as e:
            # すでにジョブが進行中の場合は、無視する
            if e.response.status_code == requests.codes.conflict:
                logger.warning(f"別のバックグラウンドジョブが既に実行されているので、更新処理を無視します。")
                logger.warning(f"{_get_annofab_error_message(e)}")
            else:
                raise e

        self._wait_for_completion(
            project_id, job_type=ProjectJobType.GEN_INPUTS_LIST, wait_options=wait_options, job_id=job_id
        )

    async def download_task_json_with_async(
        self, project_id: str, dest_path: str, is_latest: bool = False, wait_options: Optional[WaitOptions] = None
    ):
        loop = asyncio.get_event_loop()
        partial_func = partial(self.download_task_json, project_id, dest_path, is_latest, wait_options)
        result = await loop.run_in_executor(None, partial_func)
        return result

    def download_task_json(
        self, project_id: str, dest_path: str, is_latest: bool = False, wait_options: Optional[WaitOptions] = None
    ):
        logger.debug(f"タスク全件ファイルをダウンロードします。path={dest_path}")
        if is_latest:
            self.wait_until_updated_task_json(project_id, wait_options)
            self.service.wrapper.download_project_tasks_url(project_id, dest_path)

        else:
            try:
                self.service.wrapper.download_project_tasks_url(project_id, dest_path)
            except requests.HTTPError as e:
                if e.response.status_code == requests.codes.not_found:
                    logger.info(f"タスク全件ファイルが存在しなかったので、タスク全件ファイルの更新処理を実行します。")
                    self.wait_until_updated_task_json(project_id, wait_options)
                    self.service.wrapper.download_project_tasks_url(project_id, dest_path)
                else:
                    raise e

    def wait_until_updated_task_json(self, project_id: str, wait_options: Optional[WaitOptions] = None):
        job_id = None
        try:
            job = self.service.api.post_project_tasks_update(project_id)[0]["job"]
            job_id = job["job_id"]
        except requests.HTTPError as e:
            # すでにジョブが進行中の場合は、無視する
            if e.response.status_code == requests.codes.conflict:
                logger.warning(f"別のバックグラウンドジョブが既に実行されているので、更新処理を無視します。")
                logger.warning(f"{_get_annofab_error_message(e)}")
            else:
                raise e

        self._wait_for_completion(
            project_id, job_type=ProjectJobType.GEN_TASKS_LIST, wait_options=wait_options, job_id=job_id
        )

    async def download_task_history_json_with_async(self, project_id: str, dest_path: str):
        """
        非同期でタスク履歴全件ファイルをダウンロードする。

        Raises:
            DownloadingFileNotFoundError:
        """
        return self.download_task_history_json(project_id, dest_path=dest_path)

    def download_task_history_json(self, project_id: str, dest_path: str):
        """
        タスク履歴全件ファイルをダウンロードする。

        Args:
            project_id:
            dest_path:

        Raises:
            DownloadingFileNotFoundError:
        """
        try:
            logger.debug(f"タスク履歴全件ファイルをダウンロードします。path={dest_path}")
            self.service.wrapper.download_project_task_histories_url(project_id, dest_path)
        except requests.HTTPError as e:
            if e.response.status_code == requests.codes.not_found:
                logger.info(f"タスク履歴全件ファイルが存在しません。")
                raise DownloadingFileNotFoundError("タスク履歴全件ファイルが存在しません。") from e
            raise e

    def download_task_history_event_json(self, project_id: str, dest_path: str):
        """
        タスク履歴イベント全件ファイルをダウンロードする。

        .. deprecated:: 0.21.1

        Args:
            project_id:
            dest_path:

        Raises:
            DownloadingFileNotFoundError:
        """
        try:
            logger.debug(f"タスク履歴イベント全件ファイルをダウンロードします。path={dest_path}")
            self.service.wrapper.download_project_task_history_events_url(project_id, dest_path)
        except requests.HTTPError as e:
            if e.response.status_code == requests.codes.not_found:
                logger.info(f"タスク履歴イベント全件ファイルが存在しません。")
                raise DownloadingFileNotFoundError("タスク履歴イベント全件ファイルが存在しません。") from e
            raise e

    async def download_task_history_event_json_with_async(self, project_id: str, dest_path: str):
        """
        非同期で検査コメント全件ファイルをダウンロードする。

        .. deprecated:: 0.21.1

        Raises:
            DownloadingFileNotFoundError:
        """
        warnings.warn("deprecated", DeprecationWarning)
        return self.download_task_history_event_json(project_id, dest_path=dest_path)

    async def download_inspection_json_with_async(self, project_id: str, dest_path: str):
        """
        非同期で検査コメント全件ファイルをダウンロードする。

        Raises:
            DownloadingFileNotFoundError:
        """

        return self.download_inspection_json(project_id, dest_path=dest_path)

    def download_inspection_json(self, project_id: str, dest_path: str):
        """
        検査コメント全件ファイルをダウンロードする。


        Raises:
            DownloadingFileNotFoundError:
        """
        try:
            logger.debug(f"検査コメント全件ファイルをダウンロードします。path={dest_path}")
            self.service.wrapper.download_project_inspections_url(project_id, dest_path)
        except requests.HTTPError as e:
            if e.response.status_code == requests.codes.not_found:
                logger.info(f"検査コメント全件ファイルが存在しません。")
                raise DownloadingFileNotFoundError("タスク履歴全件ファイルが存在しません。") from e
            raise e
