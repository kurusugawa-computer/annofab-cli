import asyncio
import logging.config
from functools import partial

import annofabapi
import requests
from annofabapi.models import JobType

from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.exceptions import UpdatedFileForDownloadingError

logger = logging.getLogger(__name__)


class DownloadingFile:
    """
    """

    def __init__(self, service: annofabapi.Resource):
        self.service = service

    @staticmethod
    def get_max_wait_minutes(wait_options: WaitOptions):
        return wait_options.max_tries * wait_options.interval / 60

    def _wait_for_completion(self, project_id: str, job_type: JobType, wait_options: WaitOptions):
        max_wait_minutues = self.get_max_wait_minutes(wait_options)
        logger.info(f"ダウンロード対象の更新処理が完了するまで、最大{max_wait_minutues}分間待ちます。")
        result = self.service.wrapper.wait_for_completion(
            project_id,
            job_type=job_type,
            job_access_interval=wait_options.interval,
            max_job_access=wait_options.max_tries,
        )
        if not result:
            raise UpdatedFileForDownloadingError(f"ダウンロードの対象の更新処理が{max_wait_minutues}分以内に完了しない、または更新処理に失敗しました。")

    async def download_input_data_json_with_async(
        self, project_id: str, dest_path: str, is_latest: bool, wait_options: WaitOptions
    ):
        loop = asyncio.get_event_loop()
        partial_func = partial(self.download_input_data_json, project_id, dest_path, is_latest, wait_options)
        result = await loop.run_in_executor(None, partial_func)
        return result

    def download_input_data_json(self, project_id: str, dest_path: str, is_latest: bool, wait_options: WaitOptions):
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

    def wait_until_updated_input_data_json(self, project_id: str, wait_options: WaitOptions):
        try:
            self.service.api.post_project_inputs_update(project_id)
        except requests.HTTPError as e:
            # すでにジョブが進行中の場合は、無視する
            if e.response.status_code == requests.codes.conflict:
                logger.info(f"入力データ全件ファイルの更新処理が既に実行されています。")
            else:
                raise e

        self._wait_for_completion(project_id, job_type=JobType.GEN_INPUTS_LIST, wait_options=wait_options)

    async def download_task_json_with_async(
        self, project_id: str, dest_path: str, is_latest: bool, wait_options: WaitOptions
    ):
        loop = asyncio.get_event_loop()
        partial_func = partial(self.download_task_json, project_id, dest_path, is_latest, wait_options)
        result = await loop.run_in_executor(None, partial_func)
        return result

    def download_task_json(self, project_id: str, dest_path: str, is_latest: bool, wait_options: WaitOptions):
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

    def wait_until_updated_task_json(self, project_id: str, wait_options: WaitOptions):
        try:
            self.service.api.post_project_tasks_update(project_id)
        except requests.HTTPError as e:
            # すでにジョブが進行中の場合は、無視する
            if e.response.status_code == requests.codes.conflict:
                logger.info(f"タスク全件ファイルの更新処理が既に実行されています。")
            else:
                raise e

        self._wait_for_completion(project_id, job_type=JobType.GEN_TASKS_LIST, wait_options=wait_options)
