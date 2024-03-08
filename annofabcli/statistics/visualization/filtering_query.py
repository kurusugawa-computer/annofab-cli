from __future__ import annotations

import datetime
import json
import logging
import multiprocessing
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Optional

import annofabapi.utils
import dateutil
import dateutil.parser
from annofabapi.dataclass.task import Task as DcTask
from annofabapi.models import InputDataId, ProjectJobType, Task, TaskHistory

from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.download import DownloadingFile
from annofabcli.common.exceptions import DownloadingFileNotFoundError
from annofabcli.common.facade import TaskQuery, match_task_with_query
from annofabcli.common.utils import isoduration_to_hour

logger = logging.getLogger(__name__)

InputDataDict = Dict[InputDataId, int]


def _get_task_histories_dict(api: annofabapi.AnnofabApi, project_id: str, task_id: str) -> Dict[str, List[TaskHistory]]:
    task_histories, _ = api.get_task_histories(project_id, task_id)
    return {task_id: task_histories}


@dataclass(frozen=True)
class FilteringQuery:
    """
    絞り込み条件
    """

    task_query: Optional[TaskQuery] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


def _to_datetime_with_tz(str_date: str) -> datetime.datetime:
    dt = dateutil.parser.parse(str_date)
    dt = dt.replace(tzinfo=dateutil.tz.tzlocal())
    return dt


def _get_first_annotation_started_datetime(sub_task_history_list: list[dict[str, Any]]) -> str:
    """
    1個のタスクのタスク履歴一覧から、最初に教師付フェーズを作業した日時を取得します。
    """
    task_history_list_with_annotation_phase = [
        e
        for e in sub_task_history_list
        if e["phase"] == "annotation" and e["account_id"] is not None and isoduration_to_hour(e["accumulated_labor_time_milliseconds"]) > 0
    ]
    if len(task_history_list_with_annotation_phase) == 0:
        return None

    return task_history_list_with_annotation_phase[0]["started_datetime"]


def filter_task_histories(
    task_histories: dict[str, list[dict[str, Any]]], *, start_date: Optional[str] = None, end_date: Optional[str] = None
) -> dict[str, list[dict[str, Any]]]:
    """
    タスク履歴を絞り込みます。

    Args:
        task_histories: タスク履歴情報。key:task_id, value:タスク履歴一覧
        start_date: `作業開始日 >= start_date`という条件を指定します。
        end_date: `作業開始日 <= end_date`という条件を指定します。

    Returns:
        タスク一覧

    """
    if start_date is None and end_date is None:
        return task_histories
    dt_start_date = Database._to_datetime_with_tz(start_date)

    def pred(sub_task_history_list: list[dict[str, Any]]) -> bool:
        has_task_creation = sub_task_history_list[0]["account_id"] is None
        if has_task_creation and len(sub_task_history_list) < 2:
            return False

        # 初回教師付けの開始日時をfirst_started_datetimeとするため「(タスク作成)」の履歴がある場合はスキップする。
        first_started_datetime = (task_histories[0] if not has_task_creation else task_histories[1])["started_datetime"]
        if first_started_datetime is None:
            return False
        return dateutil.parser.parse(first_started_datetime) >= dt_start_date

    return [task for task in task_list if pred(task["task_id"])]


def filter_tasks(tasks: list[dict[str, Any]], query: FilteringQuery, *, task_histories: dict[str, list[dict[str, Any]]]) -> List[Task]:
    """
    タスク一覧を絞り込みます。

    Args:
        tasks: タスク一覧
        query: 絞り込み条件
        task_histories: タスク履歴情報。`query.start_date`, `query.end_date`で絞り込む際に利用します。

    Returns:
        絞り込み後のタスク一覧

    """

    # 終了日はその日の23:59までを対象とするため、１日加算する
    dt_end_date = _to_datetime_with_tz(query.end_date) + datetime.timedelta(days=1) if query.end_date is not None else None

    def _filter_with_task_query(arg_task: dict[str, Any]) -> bool:
        """
        検索条件にマッチするかどうか

        Returns:
            Trueを返すなら検索条件にマッチする
        """

        flag = True
        if query.task_query is not None:
            flag = flag and match_task_with_query(DcTask.from_dict(arg_task), query.task_query)

        # # 終了日で絞り込む
        # # 開始日の絞り込み条件はタスク履歴を見る
        # if dt_end_date is not None:
        #     flag = flag and (dateutil.parser.parse(arg_task["updated_datetime"]) < dt_end_date)

        return flag

    filtered_tasks = [task for task in tasks if _filter_with_task_query(task)]

    if query.start_date is not None:
        # start_dateは教師付開始日でみるため、タスク履歴を参照する必要あり
        dict_task_histories = self.read_task_histories_from_json()
        filtered_task_list = self._filter_task_with_task_history(
            filtered_task_list, dict_task_histories=dict_task_histories, start_date=self.query.start_date
        )

    logger.debug(f"{self.logging_prefix}: 集計対象のタスク数 = {len(filtered_task_list)}")
    return filtered_task_list


class Database:
    """
    Annofabから取得した情報に関するデータベース。
    pickelファイルをDBとして扱う
    """

    #############################################
    # Field
    #############################################

    # pickleファイルのprefixに付けるタイムスタンプ
    filename_timestamp: str

    #############################################
    # Private
    #############################################

    def __init__(
        self,
        annofab_service: annofabapi.Resource,
        project_id: str,
        temp_dir: Path,
        query: Optional[Query] = None,
    ) -> None:
        """
        環境変数'ANNOFAB_USER_ID', 'ANNOFAB_PASSWORD'から情報を読み込み、AnnofabApiインスタンスを生成する。
        Args:
            project_id: Annofabのproject_id
        """

        self.annofab_service = annofab_service
        self.project_id = project_id
        self.temp_dir = temp_dir
        self.query = query if query is not None else Query()

        # ダウンロードした一括情報
        self.tasks_json_path = self.temp_dir / f"{self.project_id}__tasks.json"
        self.comment_json_path = temp_dir / f"{self.project_id}__comments.json"
        self.task_histories_json_path = temp_dir / f"{self.project_id}__task_histories.json"
        self.annotations_zip_path = temp_dir / f"{self.project_id}__simple-annotations.zip"

        self.logging_prefix = f"project_id={project_id}"

    def read_task_histories_from_json(self, task_id_list: Optional[List[str]] = None) -> Dict[str, List[TaskHistory]]:
        logger.debug(f"{self.logging_prefix}: タスク履歴全件ファイルを読み込みます。file='{self.task_histories_json_path}'")
        with open(str(self.task_histories_json_path), encoding="utf-8") as f:
            task_histories_dict = json.load(f)

        if task_id_list is not None:
            removed_task_id_set = set(task_histories_dict.keys()) - set(task_id_list)
            for task_id in removed_task_id_set:
                del task_histories_dict[task_id]

        if len(task_histories_dict) == 0:
            logger.warning("{self.logging_prefix}: タスク履歴の件数が0件です。")

        return task_histories_dict

    def wait_for_completion_updated_annotation(self, project_id: str):
        MAX_JOB_ACCESS = 120
        JOB_ACCESS_INTERVAL = 60
        MAX_WAIT_MINUTE = MAX_JOB_ACCESS * JOB_ACCESS_INTERVAL / 60
        result = self.annofab_service.wrapper.wait_for_completion(
            project_id,
            job_type=ProjectJobType.GEN_ANNOTATION,
            job_access_interval=JOB_ACCESS_INTERVAL,
            max_job_access=MAX_JOB_ACCESS,
        )
        if result:
            logger.info(f"{self.logging_prefix}: アノテーションの更新が完了しました。")
        else:
            logger.info(f"{self.logging_prefix}: アノテーションの更新に失敗しました or {MAX_WAIT_MINUTE} 分待っても、更新が完了しませんでした。")
            return

    def _write_task_histories_json_with_executing_api_one_of_each(self):
        """
        タスク履歴取得APIを1個ずつ実行して、全タスクのタスク履歴が格納されたJSONを出力します。
        事前に、タスク全件ファイルをダウンロードする必要がある。
        """
        task_list = self.read_tasks_from_json()
        task_histories_dict = self.get_task_histories_dict(task_list)
        with self.task_histories_json_path.open(mode="w", encoding="utf-8") as f:
            json.dump(task_histories_dict, f)

    def _log_annotation_zip_info(self):
        project, _ = self.annofab_service.api.get_project(self.project_id)
        last_tasks_updated_datetime = project["summary"]["last_tasks_updated_datetime"]
        logger.debug(f"{self.logging_prefix}: タスクの最終更新日時={last_tasks_updated_datetime}")

        annotation_specs_history = self.annofab_service.api.get_annotation_specs_histories(self.project_id)[0]
        annotation_specs_updated_datetime = annotation_specs_history[-1]["updated_datetime"]
        logger.debug(f"{self.logging_prefix}: アノテーション仕様の最終更新日時={annotation_specs_updated_datetime}")

        job_list = self.annofab_service.api.get_project_job(self.project_id, query_params={"type": ProjectJobType.GEN_ANNOTATION.value, "limit": 1})[
            0
        ]["list"]
        if len(job_list) == 0:
            logger.debug(f"{self.logging_prefix}: アノテーションzipの最終更新日時は不明です。")
        else:
            job = job_list[0]
            logger.debug(f"{self.logging_prefix}: アノテーションzipの最終更新日時={job['updated_datetime']}, job_status={job['job_status']}")

    def _download_db_file(self, is_latest: bool, is_get_task_histories_one_of_each: bool):
        """
        DBになりうるファイルをダウンロードする

        Args:
            is_latest: True なら最新のファイルをダウンロードする
            is_execute_task_history_api: Trueなら `get_task_histories` APIを実行する
        """

        downloading_obj = DownloadingFile(self.annofab_service)

        wait_options = WaitOptions(interval=60, max_tries=360)

        downloading_obj.download_task_json(self.project_id, dest_path=str(self.tasks_json_path), is_latest=is_latest, wait_options=wait_options)
        downloading_obj.download_annotation_zip(
            self.project_id,
            dest_path=str(self.annotations_zip_path),
            is_latest=is_latest,
            wait_options=wait_options,
        )

        try:
            downloading_obj.download_comment_json(self.project_id, dest_path=str(self.comment_json_path))
        except DownloadingFileNotFoundError:
            # プロジェクトを作成した日だと、検査コメントファイルが作成されていないので、DownloadingFileNotFoundErrorが発生する
            # その場合でも、処理は継続できるので、空listのJSONファイルを作成しておく
            self.comment_json_path.write_text("[]", encoding="utf-8")

        if is_get_task_histories_one_of_each:
            # タスク履歴APIを一つずつ実行して、JSONファイルを生成する
            # 先にタスク全件ファイルをダウンロードする必要がある
            self._write_task_histories_json_with_executing_api_one_of_each()

        else:
            try:
                downloading_obj.download_task_history_json(self.project_id, dest_path=str(self.task_histories_json_path))
            except DownloadingFileNotFoundError:
                # プロジェクトを作成した日だと、タスク履歴全県ファイルが作成されていないので、DownloadingFileNotFoundErrorが発生する
                # その場合でも、処理は継続できるので、タスク履歴APIを１個ずつ実行して、タスク履歴ファイルを作成する
                self._write_task_histories_json_with_executing_api_one_of_each()

    def update_db(self, is_latest: bool, is_get_task_histories_one_of_each: bool = False) -> None:
        """
        Annofabから情報を取得し、DB（pickel, jsonファイル）を更新する。

        Args:
            is_latest: 最新のファイル（アノテーションzipや全件ファイルjsonなど）をダウンロードする
            is_execute_task_histories_api: Trueなら `get_task_histories` APIを実行する
        """

        # 残すべきファイル
        self.filename_timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")  # noqa: DTZ005

        # DB用のJSONファイルをダウンロードする
        self._download_db_file(is_latest, is_get_task_histories_one_of_each=is_get_task_histories_one_of_each)
        self._log_annotation_zip_info()

    def get_task_histories_dict(self, all_tasks: List[Task]) -> Dict[str, List[TaskHistory]]:
        """
        Annofabからタスク履歴情報を取得する。
        Args:
            all_tasks: 取得対象のタスク一覧

        Returns:
            タスク履歴情報

        """
        tasks_dict: Dict[str, List[TaskHistory]] = {}
        if len(all_tasks) == 0:
            return tasks_dict

        task_id_list: List[str] = [e["task_id"] for e in all_tasks]

        logger.debug(f"{len(all_tasks)} 回 `get_task_histories` WebAPIを実行します。")

        partial_func = partial(_get_task_histories_dict, self.annofab_service.api, self.project_id)
        process = multiprocessing.current_process()
        # project_id単位で並列処理が実行場合があるので、デーモンプロセスかどうかを確認する
        task_index = 0
        if process.daemon:
            for task_id in task_id_list:
                if task_index % 100 == 0:
                    logger.debug(f"{self.logging_prefix}: タスク履歴一覧取得中 {task_index} / {len(all_tasks)} 件目")
                tasks_dict.update(partial_func(task_id))
                task_index += 1
        else:
            with multiprocessing.Pool() as pool:
                for obj in pool.map(partial_func, task_id_list):
                    if task_index % 100 == 0:
                        logger.debug(f"{self.logging_prefix}: タスク履歴一覧取得中 {task_index} / {len(all_tasks)} 件目")
                    tasks_dict.update(obj)
                    task_index += 1

        return tasks_dict
