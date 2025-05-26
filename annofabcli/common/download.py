import asyncio
import logging.config
from functools import partial
from pathlib import Path
from typing import Optional, Union

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
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service

    @staticmethod
    def get_max_wait_minutes(wait_options: WaitOptions) -> float:
        return wait_options.max_tries * wait_options.interval / 60

    def _wait_for_completion(  # noqa: ANN202
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
        logger.info(f"{filetype}の更新処理が完了するまで、最大{max_wait_minutes}分間待ちます。job_id='{job_id}'")
        result = self.service.wrapper.wait_for_completion(
            project_id,
            job_type=job_type,
            job_access_interval=wait_options.interval,
            max_job_access=wait_options.max_tries,
        )
        if not result:
            raise UpdatedFileForDownloadingError(f"{filetype}の更新処理が{max_wait_minutes}分以内に完了しない、または更新処理に失敗しました。")

    async def download_annotation_zip_with_async(
        self,
        project_id: str,
        dest_path: Union[str, Path],
        is_latest: bool = False,  # noqa: FBT001, FBT002
        wait_options: Optional[WaitOptions] = None,
    ) -> None:
        loop = asyncio.get_event_loop()
        partial_func = partial(self.download_annotation_zip, project_id, dest_path, is_latest, wait_options)
        await loop.run_in_executor(None, partial_func)

    def download_annotation_zip(
        self,
        project_id: str,
        dest_path: Union[str, Path],
        is_latest: bool = False,  # noqa: FBT001, FBT002
        wait_options: Optional[WaitOptions] = None,
        should_download_full_annotation: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        """アノテーションZIPをダウンロードします。"""

        def download_annotation_zip():  # noqa: ANN202
            if should_download_full_annotation:
                self.service.wrapper.download_full_annotation_archive(project_id, dest_path)
            else:
                self.service.wrapper.download_annotation_archive(project_id, dest_path)

        if is_latest:
            self.wait_until_updated_annotation_zip(project_id, wait_options)
            download_annotation_zip()

        else:
            try:
                download_annotation_zip()
            except requests.HTTPError as e:
                if e.response.status_code == requests.codes.not_found:
                    logger.info("アノテーションzipが存在しなかったので、アノテーションzipファイルの更新処理を実行します。")
                    self.wait_until_updated_annotation_zip(project_id, wait_options)
                    download_annotation_zip()
                else:
                    raise e  # noqa: TRY201

    def wait_until_updated_annotation_zip(self, project_id: str, wait_options: Optional[WaitOptions] = None) -> None:
        job_id = None
        try:
            job = self.service.api.post_annotation_archive_update(project_id)[0]["job"]
            job_id = job["job_id"]
        except requests.HTTPError as e:
            # すでにジョブが進行中の場合は、無視する
            if e.response.status_code == requests.codes.conflict:
                logger.warning(f"別のバックグラウンドジョブが既に実行されているので、アノテーションZIPの更新処理を実行できません。 :: error_message: {_get_annofab_error_message(e)}")
            else:
                raise e  # noqa: TRY201

        self._wait_for_completion(project_id, job_type=ProjectJobType.GEN_ANNOTATION, wait_options=wait_options, job_id=job_id)

    async def download_input_data_json_with_async(
        self,
        project_id: str,
        dest_path: Union[str, Path],
        is_latest: bool = False,  # noqa: FBT001, FBT002
        wait_options: Optional[WaitOptions] = None,
    ) -> None:
        loop = asyncio.get_event_loop()
        partial_func = partial(self.download_input_data_json, project_id, dest_path, is_latest, wait_options)
        await loop.run_in_executor(None, partial_func)

    def download_input_data_json(
        self,
        project_id: str,
        dest_path: Union[str, Path],
        is_latest: bool = False,  # noqa: FBT001, FBT002
        wait_options: Optional[WaitOptions] = None,
    ) -> None:
        if is_latest:
            self.wait_until_updated_input_data_json(project_id, wait_options)
            self.service.wrapper.download_project_inputs_url(project_id, dest_path)

        else:
            try:
                self.service.wrapper.download_project_inputs_url(project_id, dest_path)
            except requests.HTTPError as e:
                if e.response.status_code == requests.codes.not_found:
                    logger.info("入力データ全件ファイルが存在しなかったので、入力データ全件ファイルの更新処理を実行します。")
                    self.wait_until_updated_input_data_json(project_id, wait_options)
                    self.service.wrapper.download_project_inputs_url(project_id, dest_path)
                else:
                    raise e  # noqa: TRY201

    def wait_until_updated_input_data_json(self, project_id: str, wait_options: Optional[WaitOptions] = None) -> None:
        job_id = None
        try:
            job = self.service.api.post_project_inputs_update(project_id)[0]["job"]
            job_id = job["job_id"]
        except requests.HTTPError as e:
            # すでにジョブが進行中の場合は、無視する
            if e.response.status_code == requests.codes.conflict:
                logger.warning(f"別のバックグラウンドジョブが既に実行されているので、更新処理を無視します。 :: error_message: {_get_annofab_error_message(e)}")
            else:
                raise e  # noqa: TRY201

        self._wait_for_completion(project_id, job_type=ProjectJobType.GEN_INPUTS_LIST, wait_options=wait_options, job_id=job_id)

    async def download_task_json_with_async(
        self,
        project_id: str,
        dest_path: Union[str, Path],
        is_latest: bool = False,  # noqa: FBT001, FBT002
        wait_options: Optional[WaitOptions] = None,
    ) -> None:
        loop = asyncio.get_event_loop()
        partial_func = partial(self.download_task_json, project_id, dest_path, is_latest=is_latest, wait_options=wait_options)
        await loop.run_in_executor(None, partial_func)

    def download_task_json(self, project_id: str, dest_path: Union[str, Path], *, is_latest: bool = False, wait_options: Optional[WaitOptions] = None) -> None:
        if is_latest:
            self.wait_until_updated_task_json(project_id, wait_options)
            self.service.wrapper.download_project_tasks_url(project_id, dest_path)

        else:
            try:
                self.service.wrapper.download_project_tasks_url(project_id, dest_path)
            except requests.HTTPError as e:
                if e.response.status_code == requests.codes.not_found:
                    logger.info("タスク全件ファイルが存在しなかったので、タスク全件ファイルの更新処理を実行します。")
                    self.wait_until_updated_task_json(project_id, wait_options)
                    self.service.wrapper.download_project_tasks_url(project_id, dest_path)
                else:
                    raise e  # noqa: TRY201

    def wait_until_updated_task_json(self, project_id: str, wait_options: Optional[WaitOptions] = None) -> None:
        job_id = None
        try:
            job = self.service.api.post_project_tasks_update(project_id)[0]["job"]
            job_id = job["job_id"]
        except requests.HTTPError as e:
            # すでにジョブが進行中の場合は、無視する
            if e.response.status_code == requests.codes.conflict:
                logger.warning(f"別のバックグラウンドジョブが既に実行されているので、更新処理を無視します。 :: error_message={_get_annofab_error_message(e)}")
            else:
                raise e  # noqa: TRY201

        self._wait_for_completion(project_id, job_type=ProjectJobType.GEN_TASKS_LIST, wait_options=wait_options, job_id=job_id)

    async def download_task_history_json_with_async(self, project_id: str, dest_path: Union[str, Path]) -> None:
        """
        非同期でタスク履歴全件ファイルをダウンロードする。

        Raises:
            DownloadingFileNotFoundError:
        """
        return self.download_task_history_json(project_id, dest_path=dest_path)

    def download_task_history_json(self, project_id: str, dest_path: Union[str, Path]) -> None:
        """
        タスク履歴全件ファイルをダウンロードする。

        Args:
            project_id:
            dest_path:

        Raises:
            DownloadingFileNotFoundError:
        """
        try:
            self.service.wrapper.download_project_task_histories_url(project_id, dest_path)
        except requests.HTTPError as e:
            if e.response.status_code == requests.codes.not_found:
                raise DownloadingFileNotFoundError(f"project_id='{project_id}'のプロジェクトに、タスク履歴全件ファイルが存在しないため、ダウンロードできませんでした。") from e
            raise e  # noqa: TRY201

    def download_task_history_event_json(self, project_id: str, dest_path: Union[str, Path]) -> None:
        """
        タスク履歴イベント全件ファイルをダウンロードする。

        Args:
            project_id:
            dest_path:

        Raises:
            DownloadingFileNotFoundError:
        """
        try:
            self.service.wrapper.download_project_task_history_events_url(project_id, dest_path)
        except requests.HTTPError as e:
            if e.response.status_code == requests.codes.not_found:
                raise DownloadingFileNotFoundError(f"project_id='{project_id}'のプロジェクトに、タスク履歴イベント全件ファイルが存在しないため、ダウンロードできませんでした。") from e
            raise e  # noqa: TRY201

    async def download_task_history_event_json_with_async(self, project_id: str, dest_path: Union[str, Path]) -> None:
        """
        非同期でタスク履歴全件ファイルをダウンロードする。


        Raises:
            DownloadingFileNotFoundError:
        """
        return self.download_task_history_event_json(project_id, dest_path=dest_path)

    async def download_inspection_json_with_async(self, project_id: str, dest_path: Union[str, Path]) -> None:
        """
        非同期で検査コメント全件ファイルをダウンロードする。

        Raises:
            DownloadingFileNotFoundError:
        """

        return self.download_inspection_comment_json(project_id, dest_path=dest_path)

    def download_inspection_comment_json(self, project_id: str, dest_path: Union[str, Path]) -> None:
        """
        検査コメント全件ファイルをダウンロードする。


        Raises:
            DownloadingFileNotFoundError:
        """
        try:
            self.service.wrapper.download_project_inspections_url(project_id, dest_path)
        except requests.HTTPError as e:
            if e.response.status_code == requests.codes.not_found:
                raise DownloadingFileNotFoundError(f"project_id='{project_id}'のプロジェクトに、検査コメント全件ファイルが存在しないため、ダウンロードできませんでした。") from e
            raise e  # noqa: TRY201

    async def download_comment_json_with_async(self, project_id: str, dest_path: Union[str, Path]) -> None:
        """
        非同期でコメント全件ファイルをダウンロードする。

        Raises:
            DownloadingFileNotFoundError:
        """

        return self.download_comment_json(project_id, dest_path=dest_path)

    def download_comment_json(self, project_id: str, dest_path: Union[str, Path]) -> None:
        """
        コメント全件ファイルをダウンロードする。


        Raises:
            DownloadingFileNotFoundError:
        """
        try:
            self.service.wrapper.download_project_comments_url(project_id, dest_path)
        except requests.HTTPError as e:
            if e.response.status_code == requests.codes.not_found:
                raise DownloadingFileNotFoundError(f"project_id='{project_id}'のプロジェクトに、コメント全件ファイルが存在しないため、ダウンロードできませんでした。") from e
            raise e  # noqa: TRY201
