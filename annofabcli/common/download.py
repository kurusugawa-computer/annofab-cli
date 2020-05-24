import json
import logging.config
import os
import pkgutil
import re
import sys
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar
from annofabcli.common.dataclasses import WaitOptions
from annofabapi.models import JobType
import dateutil.parser
import isodate
import pandas
import requests
import yaml
import asyncio
import annofabapi

logger = logging.getLogger(__name__)



class DownloadingFile:
    """
    """

    def __init__(self, service: annofabapi.Resource):
        self.service = service


    async def download_input_data_json_with_async(self, project_id: str, dest_path: str, is_latest: bool, wait_options: WaitOptions):
        loop = asyncio.get_event_loop()
        partial_func = partial(
            self.download_input_data_json,
            project_id,
            dest_path,
            is_latest,
            wait_options
        )
        result = await loop.run_in_executor(None, partial_func)
        return result

    def download_input_data_json(self, project_id: str, dest_path: str, is_latest: bool, wait_options: WaitOptions):
        if is_latest:
            self.wait_until_updated_input_data_json(project_id, wait_options)
            self.service.wrapper.download_project_inputs_url(project_id, dest_path)

        else:
            try:
                self.service.wrapper.download_project_tasks_url(project_id, dest_path)
            except requests.HTTPError as e:
                if e.response.status_code == requests.codes.not_found:
                    logger.info(f"入力データ全件ファイルが存在しなかったので、入力データ全件ファイルの更新処理を実行します。")
                    self.wait_until_updated_input_data_json(project_id, wait_options)
                    self.service.wrapper.download_project_inputs_url(project_id, dest_path)
                else:
                    raise e


    def wait_until_updated_input_data_json(self, project_id: str, wait_options: WaitOptions) -> bool:
        try:
            self.service.api.post_project_inputs_update(project_id)
        except requests.HTTPError as e:
            # すでにジョブが進行中の場合は、無視する
            if e.response.status_code == requests.codes.conflict:
                logger.info(f"入力データ全件ファイルの更新処理が既に実行されています。")
            else:
                raise e

        return self.service.wrapper.wait_for_completion(project_id, job_type=JobType.GEN_INPUTS_LIST, job_access_interval=wait_options.interval, max_job_access=wait_options.max_tries)



    async def download_task_json_with_async(self, project_id: str, dest_path: str, is_latest: bool, wait_options: WaitOptions):
        loop = asyncio.get_event_loop()
        partial_func = partial(
            self.download_task_json,
            project_id,
            dest_path,
            is_latest,
            wait_options
        )
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


    def wait_until_updated_task_json(self, project_id: str, wait_options: WaitOptions) -> bool:
        try:
            self.service.api.post_project_tasks_update(project_id)
        except requests.HTTPError as e:
            # すでにジョブが進行中の場合は、無視する
            if e.response.status_code == requests.codes.conflict:
                logger.info(f"タスク全件ファイルの更新処理が既に実行されています。")
            else:
                raise e

        return self.service.wrapper.wait_for_completion(project_id, job_type=JobType.GEN_TASKS_LIST, job_access_interval=wait_options.interval, max_job_access=wait_options.max_tries)



    async def wait_until_updated_task(self, project_id: str, dest_path: Path, is_latest:bool, wait_options: WaitOptions):
        try:
            self.service.api.post_project_tasks_update(project_id)
        except requests.HTTPError as e:
            if e.response.status_code != requests.codes.conflict:
                raise e

        loop = asyncio.get_event_loop()
        partial_func = partial(
            self.service.wrapper.wait_for_completion,
            project_id,
            JobType.GEN_TASKS_LIST,
            wait_options.interval,
            wait_options.max_tries,
        )
        result = await loop.run_in_executor(None, partial_func)
        return result

