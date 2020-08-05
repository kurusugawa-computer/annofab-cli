import asyncio
import datetime
import json
import logging
import multiprocessing
import os
import pickle
import shutil
import zipfile
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

import annofabapi
import annofabapi.utils
import dateutil
import dateutil.parser
import more_itertools
from annofabapi.models import InputData, InputDataId, Inspection, JobStatus, JobType, Task, TaskHistory
from annofabapi.parser import SimpleAnnotationZipParser

from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.download import DownloadingFile
from annofabcli.common.exceptions import DownloadingFileNotFoundError

logger = logging.getLogger(__name__)

InputDataDict = Dict[InputDataId, Dict[str, Any]]
AnnotationDict = Dict[str, InputDataDict]
AnnotationSummaryFunc = Callable[[List[Dict[str, Any]]], Dict[str, Any]]
"""アノテーションの概要を算出する関数"""


def _get_task_histories_dict(api: annofabapi.AnnofabApi, project_id: str, task_id: str) -> Dict[str, List[TaskHistory]]:
    task_histories, _ = api.get_task_histories(project_id, task_id)
    return {task_id: task_histories}


@dataclass(frozen=True)
class Query:
    """
    絞り込み条件
    """

    task_query_param: Optional[Dict[str, Any]] = None
    ignored_task_id_list: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class Database:
    """
    Annofabから取得した情報に関するデータベース。
    pickelファイルをDBとして扱う
    """

    #############################################
    # Field
    #############################################

    # pickleファイルのprfixに付けるタイムスタンプ
    filename_timestamp: str

    #############################################
    # Private
    #############################################

    def __init__(
        self, annofab_service: annofabapi.Resource, project_id: str, chekpoint_dir: str, query: Optional[Query] = None
    ):
        """
        環境変数'ANNOFAB_USER_ID', 'ANNOFAB_PASSWORD'から情報を読み込み、AnnofabApiインスタンスを生成する。
        Args:
            project_id: Annofabのproject_id
        """

        self.annofab_service = annofab_service
        self.project_id = project_id
        self.checkpoint_dir = chekpoint_dir
        self.query = query if query is not None else Query()

        # ダウンロードした一括情報
        self.tasks_json_path = Path(f"{self.checkpoint_dir}/tasks.json")
        self.input_data_json_path = Path(f"{self.checkpoint_dir}/input_data.json")
        self.inspection_json_path = Path(f"{self.checkpoint_dir}/inspections.json")
        self.task_histories_json_path = Path(f"{self.checkpoint_dir}/task_histories.json")
        self.annotations_zip_path = Path(f"{self.checkpoint_dir}/simple-annotations.zip")

    def __write_checkpoint(self, obj, pickle_file_name):
        """
        チェックポイントファイルに書き込む。書き込み対象のファイルが存在すれば、書き込む前に同階層にバックアップファイルを作成する。
        """

        pickle_file_path = f"{self.checkpoint_dir}/{pickle_file_name}"
        if os.path.exists(pickle_file_path):
            dest_file_name = f"{self.filename_timestamp}_{pickle_file_name}"
            dest_path = f"{self.checkpoint_dir}/{dest_file_name}"
            shutil.copyfile(pickle_file_path, dest_path)

        with open(pickle_file_path, "wb") as file:
            pickle.dump(obj, file)

    def __read_checkpoint(self, pickle_file_name):
        file_path = f"{self.checkpoint_dir}/{pickle_file_name}"
        if not os.path.exists(file_path):
            return None
        with open(file_path, "rb") as file:
            return pickle.load(file)

    def read_account_statistics_from_checkpoint(self) -> List[Dict[str, Any]]:
        result = self.__read_checkpoint("account_statistics.pickel")
        return result if result is not None else []

    def read_labor_list_from_checkpoint(self) -> List[Dict[str, Any]]:
        result = self.__read_checkpoint("labor_list.pickel")
        return result if result is not None else []

    @staticmethod
    def task_exists(task_list: List[Task], task_id) -> bool:
        task = more_itertools.first_true(task_list, pred=lambda e: e["task_id"] == task_id)
        if task is None:
            return False
        else:
            return True

    def read_annotation_summary(
        self, task_list: List[Task], annotation_summary_func: AnnotationSummaryFunc
    ) -> AnnotationDict:
        logger.debug(f"reading {str(self.annotations_zip_path)}")

        def read_annotation_summary_per_input_data(task_id: str, input_data_id_: str) -> Dict[str, Any]:
            json_path = f"{task_id}/{input_data_id_}.json"
            parser = SimpleAnnotationZipParser(zip_file, json_path)
            simple_annotation: Dict[str, Any] = parser.load_json()
            return annotation_summary_func(simple_annotation["details"])

        with zipfile.ZipFile(self.annotations_zip_path, "r") as zip_file:
            annotation_dict: AnnotationDict = {}

            task_count = 0
            for task in task_list:
                task_count += 1
                if task_count % 1000 == 0:
                    logger.debug(f"{task_count} / {len(task_list)} 件目を読み込み中")

                task_id = task["task_id"]
                input_data_id_list = task["input_data_id_list"]

                try:
                    input_data_dict: InputDataDict = {}
                    for input_data_id in input_data_id_list:
                        input_data_dict[input_data_id] = read_annotation_summary_per_input_data(task_id, input_data_id)
                    annotation_dict[task_id] = input_data_dict
                except Exception as e:  # pylint: disable=broad-except
                    logger.warning(f"task_id='{task_id}'のJSONファイル読み込みで失敗しました。")
                    logger.warning(e)
                    continue

            return annotation_dict

    def read_inspections_from_json(self, task_id_list: List[str]) -> Dict[str, Dict[InputDataId, List[Inspection]]]:
        logger.debug(f"reading {self.inspection_json_path}")

        with open(str(self.inspection_json_path)) as f:
            all_inspections = json.load(f)

        tasks_dict: Dict[str, Dict[InputDataId, List[Inspection]]] = {}

        for inspection in all_inspections:
            task_id = inspection["task_id"]
            if task_id not in task_id_list:
                continue

            input_data_id = inspection["input_data_id"]

            input_data_dict: Dict[InputDataId, List[Inspection]] = tasks_dict.get(task_id, {})

            inspection_list: List[Inspection] = input_data_dict.get(input_data_id, [])

            inspection_list.append(inspection)

            input_data_dict[input_data_id] = inspection_list
            tasks_dict[task_id] = input_data_dict

        return tasks_dict

    def read_input_data_from_json(self, task_list: List[Task]) -> Dict[str, List[InputData]]:
        path = self.input_data_json_path
        logger.debug(f"reading {path}")
        with open(str(path)) as f:
            all_input_data_list = json.load(f)

        all_input_data_dict = {e["input_data_id"]: e for e in all_input_data_list}
        tasks_dict: Dict[str, List[InputData]] = {}

        for task in task_list:
            task_id = task["task_id"]
            input_data_id_list = task["input_data_id_list"]
            tasks_dict[task_id] = [all_input_data_dict[input_data_id] for input_data_id in input_data_id_list]

        return tasks_dict

    def read_task_histories_from_json(self, task_id_list: Optional[List[str]] = None) -> Dict[str, List[TaskHistory]]:
        logger.debug(f"reading {self.task_histories_json_path}")
        with open(str(self.task_histories_json_path)) as f:
            task_histories_dict = json.load(f)

        if task_id_list is not None:
            removed_task_id_set = set(task_histories_dict.keys()) - set(task_id_list)
            for task_id in removed_task_id_set:
                del task_histories_dict[task_id]

        return task_histories_dict

    def wait_for_completion_updated_annotation(self, project_id):
        MAX_JOB_ACCESS = 120
        JOB_ACCESS_INTERVAL = 60
        MAX_WAIT_MINUTU = MAX_JOB_ACCESS * JOB_ACCESS_INTERVAL / 60
        result = self.annofab_service.wrapper.wait_for_completion(
            project_id,
            job_type=JobType.GEN_ANNOTATION,
            job_access_interval=JOB_ACCESS_INTERVAL,
            max_job_access=MAX_JOB_ACCESS,
        )
        if result:
            logger.info(f"アノテーションの更新が完了しました。")
        else:
            logger.info(f"アノテーションの更新に失敗しました or {MAX_WAIT_MINUTU} 分待っても、更新が完了しませんでした。")
            return

    def wait_for_completion_updated_task_json(self, project_id):
        MAX_JOB_ACCESS = 120
        JOB_ACCESS_INTERVAL = 60
        MAX_WAIT_MINUTU = MAX_JOB_ACCESS * JOB_ACCESS_INTERVAL / 60
        result = self.annofab_service.wrapper.wait_for_completion(
            project_id,
            job_type=JobType.GEN_TASKS_LIST,
            job_access_interval=JOB_ACCESS_INTERVAL,
            max_job_access=MAX_JOB_ACCESS,
        )
        if result:
            logger.info(f"タスク全件ファイルの更新が完了しました。")
        else:
            logger.info(f"タスク全件ファイルの更新に失敗しました or {MAX_WAIT_MINUTU} 分待っても、更新が完了しませんでした。")
            return

    def update_annotation_zip(self, project_id: str, should_update_annotation_zip: bool = False):
        """
        必要に応じて、アノテーションの更新を実施 and アノテーションの更新を待つ。

        Args:
            project_id:
            should_update_annotation_zip:

        Returns:

        """

        project, _ = self.annofab_service.api.get_project(project_id)
        last_tasks_updated_datetime = project["summary"]["last_tasks_updated_datetime"]
        logger.debug(f"タスクの最終更新日時={last_tasks_updated_datetime}")

        annotation_specs_history = self.annofab_service.api.get_annotation_specs_histories(project_id)[0]
        annotation_specs_updated_datetime = annotation_specs_history[-1]["updated_datetime"]
        logger.debug(f"アノテーション仕様の最終更新日時={annotation_specs_updated_datetime}")

        job_list = self.annofab_service.api.get_project_job(
            project_id, query_params={"type": JobType.GEN_ANNOTATION.value, "limit": 1}
        )[0]["list"]
        if len(job_list) > 0:
            job = job_list[0]
            logger.debug(f"アノテーションzipの最終更新日時={job['updated_datetime']}, job_status={job['job_status']}")

        if should_update_annotation_zip:
            if len(job_list) == 0:
                self.annofab_service.api.post_annotation_archive_update(project_id)
                self.wait_for_completion_updated_annotation(project_id)
            else:
                job = job_list[0]
                job_status = JobStatus(job["job_status"])
                if job_status == JobStatus.PROGRESS:
                    logger.info(f"アノテーション更新が完了するまで待ちます。")
                    self.wait_for_completion_updated_annotation(project_id)

                elif job_status == JobStatus.SUCCEEDED:
                    if dateutil.parser.parse(job["updated_datetime"]) < dateutil.parser.parse(
                        last_tasks_updated_datetime
                    ):
                        logger.info(f"タスクの最新更新日時よりアノテーションzipの最終更新日時の方が古いので、アノテーションzipを更新します。")
                        self.annofab_service.api.post_annotation_archive_update(project_id)
                        self.wait_for_completion_updated_annotation(project_id)

                    elif dateutil.parser.parse(job["updated_datetime"]) < dateutil.parser.parse(
                        annotation_specs_updated_datetime
                    ):
                        logger.info(f"アノテーション仕様の更新日時よりアノテーションzipの最終更新日時の方が古いので、アノテーションzipを更新します。")
                        self.annofab_service.api.post_annotation_archive_update(project_id)
                        self.wait_for_completion_updated_annotation(project_id)

                    else:
                        logger.info(f"アノテーションzipを更新する必要がないので、更新しません。")

                elif job_status == JobStatus.FAILED:
                    logger.info("アノテーションzipの更新に失敗しているので、アノテーションzipを更新します。")
                    self.annofab_service.api.post_annotation_archive_update(project_id)
                    self.wait_for_completion_updated_annotation(project_id)

    def update_task_json(self, project_id: str, should_update_task_json: bool = False):
        """
        必要に応じて、タスク全件ファイルを更新して、更新が完了するまで待つ

        Args:
            project_id:
            should_update_task_json:
        """

        job_list = self.annofab_service.api.get_project_job(
            project_id, query_params={"type": JobType.GEN_TASKS_LIST.value, "limit": 1}
        )[0]["list"]

        if len(job_list) == 0:
            if should_update_task_json:
                self.annofab_service.api.post_project_tasks_update(project_id)
                self.wait_for_completion_updated_task_json(project_id)

        else:
            job = job_list[0]
            logger.debug(f"タスク全件ファイルの最終更新日時={job['updated_datetime']}, job_status={job['job_status']}")

            if should_update_task_json:
                job_status = JobStatus(job["job_status"])
                if job_status == JobStatus.PROGRESS:
                    logger.info(f"タスク全件ファイルの更新が完了するまで待ちます。")
                    self.wait_for_completion_updated_task_json(project_id)

                elif job_status == JobStatus.SUCCEEDED:
                    self.annofab_service.api.post_project_tasks_update(project_id)
                    self.wait_for_completion_updated_task_json(project_id)

                elif job_status == JobStatus.FAILED:
                    logger.info("タスク全件ファイルの更新に失敗しているので、タスク全件ファイルを更新します。")
                    self.annofab_service.api.post_project_tasks_update(project_id)
                    self.wait_for_completion_updated_task_json(project_id)

    def _write_task_histories_json(self):
        task_list = self.read_tasks_from_json()
        task_histories_dict = self.get_task_histories_dict(task_list)
        with self.task_histories_json_path.open(mode="w") as f:
            json.dump(task_histories_dict, f)

    def _log_annotation_zip_info(self):
        project, _ = self.annofab_service.api.get_project(self.project_id)
        last_tasks_updated_datetime = project["summary"]["last_tasks_updated_datetime"]
        logger.debug(f"タスクの最終更新日時={last_tasks_updated_datetime}")

        annotation_specs_history = self.annofab_service.api.get_annotation_specs_histories(self.project_id)[0]
        annotation_specs_updated_datetime = annotation_specs_history[-1]["updated_datetime"]
        logger.debug(f"アノテーション仕様の最終更新日時={annotation_specs_updated_datetime}")

        job_list = self.annofab_service.api.get_project_job(
            self.project_id, query_params={"type": JobType.GEN_ANNOTATION.value, "limit": 1}
        )[0]["list"]
        if len(job_list) == 0:
            logger.debug(f"アノテーションzipの最終更新日時は不明です。")
        else:
            job = job_list[0]
            logger.debug(f"アノテーションzipの最終更新日時={job['updated_datetime']}, job_status={job['job_status']}")

    def _download_db_file(self, is_latest: bool):
        """
        DBになりうるファイルをダウンロードする

        Args:
            is_latest: Trunなら最新のファイルをダウンロードする
        """

        downloading_obj = DownloadingFile(self.annofab_service)

        wait_options = WaitOptions(interval=60, max_tries=360)

        TASK_JSON_INDEX = 0
        INPUT_DATA_JSON_INDEX = 1
        ANNOTATION_ZIP_INDEX = 2
        TASK_HISTORY_JSON_INDEX = 3
        INSPECTION_JSON_INDEX = 4

        loop = asyncio.get_event_loop()
        coroutines: List[Any] = [None] * 5
        coroutines[TASK_JSON_INDEX] = downloading_obj.download_task_json_with_async(
            self.project_id, dest_path=str(self.tasks_json_path), is_latest=is_latest, wait_options=wait_options
        )
        coroutines[INPUT_DATA_JSON_INDEX] = downloading_obj.download_input_data_json_with_async(
            self.project_id, dest_path=str(self.input_data_json_path), is_latest=is_latest, wait_options=wait_options,
        )
        coroutines[ANNOTATION_ZIP_INDEX] = downloading_obj.download_annotation_zip_with_async(
            self.project_id, dest_path=str(self.annotations_zip_path), is_latest=is_latest, wait_options=wait_options,
        )
        coroutines[TASK_HISTORY_JSON_INDEX] = downloading_obj.download_task_history_json_with_async(
            self.project_id, dest_path=str(self.task_histories_json_path)
        )
        coroutines[INSPECTION_JSON_INDEX] = downloading_obj.download_inspection_json_with_async(
            self.project_id, dest_path=str(self.inspection_json_path)
        )
        gather = asyncio.gather(*coroutines, return_exceptions=True)
        results = loop.run_until_complete(gather)

        if isinstance(results[INSPECTION_JSON_INDEX], DownloadingFileNotFoundError):
            # 空のJSONファイルを作り、検査コメント0件として処理する
            self.inspection_json_path.write_text("{}", encoding="utf-8")
        elif isinstance(results[INSPECTION_JSON_INDEX], Exception):
            raise results[INSPECTION_JSON_INDEX]

        if isinstance(results[TASK_HISTORY_JSON_INDEX], DownloadingFileNotFoundError):
            # タスク履歴APIを一つずつ実行して、JSONファイルを生成する
            self._write_task_histories_json()
        elif isinstance(results[TASK_HISTORY_JSON_INDEX], Exception):
            raise results[TASK_HISTORY_JSON_INDEX]

        for result in [results[TASK_JSON_INDEX], results[INPUT_DATA_JSON_INDEX], results[ANNOTATION_ZIP_INDEX]]:
            if isinstance(result, Exception):
                raise result

    @staticmethod
    def _to_datetime_with_tz(str_date: str) -> datetime.datetime:
        dt = dateutil.parser.parse(str_date)
        dt = dt.replace(tzinfo=dateutil.tz.tzlocal())
        return dt

    def read_tasks_from_json(self,) -> List[Task]:
        """
        task.jsonからqueryに合致するタスクを調べる

        Returns:
            タスク一覧

        """
        query = self.query

        # 終了日はその日の23:59までを対象とするため、１日加算する
        dt_end_date = (
            self._to_datetime_with_tz(query.end_date) + datetime.timedelta(days=1)
            if query.end_date is not None
            else None
        )

        def filter_task(arg_task: Dict[str, Any]):
            """AND条件で絞り込む"""

            flag = True
            if query.task_query_param is not None:
                if "phase" in query.task_query_param:
                    flag = flag and arg_task["phase"] == query.task_query_param["phase"]

                if "status" in query.task_query_param:
                    flag = flag and arg_task["status"] == query.task_query_param["status"]

                if "task_id" in query.task_query_param:
                    flag = flag and str(query.task_query_param["task_id"]).lower() in str(arg_task["task_id"]).lower()

            # 終了日で絞り込む
            # 開始日の絞り込み条件はタスク履歴を見る
            if dt_end_date is not None:
                flag = flag and (dateutil.parser.parse(arg_task["updated_datetime"]) < dt_end_date)

            if query.ignored_task_id_list is not None:
                flag = flag and arg_task["task_id"] not in query.ignored_task_id_list

            return flag

        logger.debug(f"reading {self.tasks_json_path}")
        with open(str(self.tasks_json_path)) as f:
            all_tasks = json.load(f)

        filtered_task_list = [task for task in all_tasks if filter_task(task)]

        if self.query.start_date is not None:
            # start_dateは教師付開始日でみるため、タスク履歴を参照する必要あり
            dict_task_histories = self.read_task_histories_from_json()
            filtered_task_list = self._filter_task_with_task_history(
                filtered_task_list, dict_task_histories=dict_task_histories, start_date=self.query.start_date
            )

        logger.debug(f"集計対象のタスク数 = {len(filtered_task_list)}")
        return filtered_task_list

    @staticmethod
    def _filter_task_with_task_history(
        task_list: List[Task], dict_task_histories: Dict[str, List[TaskHistory]], start_date: str
    ) -> List[Task]:
        """
        タスク履歴を参照して、タスクを絞り込む。

        Args:
            task_list:
            dict_task_histories:
            start_date:

        Returns:
            タスク一覧

        """
        dt_start_date = Database._to_datetime_with_tz(start_date)

        def pred(task_id: str):
            task_histories = dict_task_histories.get(task_id)
            if task_histories is None or len(task_histories) == 0:
                return False

            first_started_datetime = task_histories[0]["started_datetime"]
            if first_started_datetime is None:
                return False
            return dateutil.parser.parse(first_started_datetime) >= dt_start_date

        return [task for task in task_list if pred(task["task_id"])]

    def update_db(self, is_latest: bool) -> None:
        """
        Annofabから情報を取得し、DB（pickel, jsonファイル）を更新する。

        Args:
            is_latest: 最新のファイル（アノテーションzipや全件ファイルjsonなど）をダウンロードする
        """

        # 残すべきファイル
        self.filename_timestamp = "{0:%Y%m%d-%H%M%S}".format(datetime.datetime.now())

        # DB用のJSONファイルをダウンロードする
        self._download_db_file(is_latest)
        self._log_annotation_zip_info()

        # 統計情報の出力
        account_statistics = self.annofab_service.wrapper.get_account_statistics(self.project_id)
        self.__write_checkpoint(account_statistics, "account_statistics.pickel")

        # 労務管理情報の出力
        labor_list = self._get_labor_list(self.project_id)
        self.__write_checkpoint(labor_list, "labor_list.pickel")

    @staticmethod
    def _get_worktime_hour(working_time_by_user: Optional[Dict[str, Any]], key: str) -> float:
        if working_time_by_user is None:
            return 0

        value = working_time_by_user.get(key)
        if value is None:
            return 0
        else:
            return value / 3600 / 1000

    def _get_labor_list(self, project_id: str) -> List[Dict[str, Any]]:
        def to_new_labor(e: Dict[str, Any]) -> Dict[str, Any]:
            return dict(
                date=e["date"],
                account_id=e["account_id"],
                worktime_plan_hour=self._get_worktime_hour(e["values"]["working_time_by_user"], "plans"),
                worktime_result_hour=self._get_worktime_hour(e["values"]["working_time_by_user"], "results"),
            )

        # 未来のデータを取得しても意味がないので、今日の日付を指定する
        end_date = (
            self.query.end_date if self.query.end_date is not None else datetime.datetime.now().strftime("%Y-%m-%d")
        )
        labor_list: List[Dict[str, Any]] = self.annofab_service.api.get_labor_control(
            {"project_id": project_id, "from": self.query.start_date, "to": end_date}
        )[0]

        return [to_new_labor(e) for e in labor_list if e["account_id"] is not None]

    @staticmethod
    def get_not_updated_task_ids(old_tasks, new_tasks) -> Set[str]:
        """
        更新されていないtask_idのListを取得する
        Args:
            old_tasks:
            new_tasks:

        Returns:

        """
        updated_task_ids = set()
        for new_task in new_tasks:
            filterd_list = [e for e in old_tasks if e["task_id"] == new_task["task_id"]]
            if len(filterd_list) == 0:
                continue
            old_task = filterd_list[0]
            if dateutil.parser.parse(old_task["updated_datetime"]) == dateutil.parser.parse(
                new_task["updated_datetime"]
            ):
                updated_task_ids.add(new_task["task_id"])

        return updated_task_ids

    def get_task_histories_dict(self, all_tasks: List[Task]) -> Dict[str, List[TaskHistory]]:
        """
        Annofabからタスク履歴情報を取得する。
        Args:
            all_tasks: 取得対象のタスク一覧
            ignored_task_ids: 取得しないタスクID List

        Returns:
            タスク履歴情報

        """
        if self.query.ignored_task_id_list is None:
            ignored_task_ids = set()
        else:
            ignored_task_ids = set(self.query.ignored_task_id_list)

        tasks = [e for e in all_tasks if e["task_id"] not in ignored_task_ids]
        logger.info(f"タスク履歴取得対象のタスク数 = {len(tasks)}")

        tasks_dict: Dict[str, List[TaskHistory]] = {}
        if len(tasks) == 0:
            return tasks_dict

        task_id_list: List[str] = [e["task_id"] for e in tasks]
        partial_func = partial(_get_task_histories_dict, self.annofab_service.api, self.project_id)
        with multiprocessing.Pool() as pool:
            task_index = 0
            for obj in pool.map(partial_func, task_id_list):
                if task_index % 100 == 0:
                    logger.debug(f"タスク履歴一覧取得中 {task_index} / {len(tasks)} 件目")
                tasks_dict.update(obj)
                task_index += 1

        return tasks_dict
