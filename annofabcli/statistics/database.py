import datetime
import json
import logging
import multiprocessing
from collections import defaultdict
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Collection, Dict, List, Optional

import annofabapi.utils
import dateutil
import dateutil.parser
import more_itertools
from annofabapi.dataclass.task import Task as DcTask
from annofabapi.models import CommentStatus, InputDataId, JobStatus, ProjectJobType, Task, TaskHistory
from annofabapi.parser import lazy_parse_simple_annotation_zip

from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.download import DownloadingFile
from annofabcli.common.exceptions import DownloadingFileNotFoundError
from annofabcli.common.facade import TaskQuery, match_task_with_query

logger = logging.getLogger(__name__)

InputDataDict = Dict[InputDataId, int]


def _get_task_histories_dict(api: annofabapi.AnnofabApi, project_id: str, task_id: str) -> Dict[str, List[TaskHistory]]:
    task_histories, _ = api.get_task_histories(project_id, task_id)
    return {task_id: task_histories}


@dataclass(frozen=True)
class Query:
    """
    絞り込み条件
    """

    task_query: Optional[TaskQuery] = None
    task_ids: Optional[Collection[str]] = None
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

    @staticmethod
    def task_exists(task_list: List[Task], task_id: str) -> bool:
        task = more_itertools.first_true(task_list, pred=lambda e: e["task_id"] == task_id)
        if task is None:
            return False
        else:
            return True

    def get_annotation_count_by_task(self) -> Dict[str, int]:
        logger.debug(f"{self.logging_prefix}: アノテーションZIPを読み込みます。file='{str(self.annotations_zip_path)}'")

        result: Dict[str, int] = defaultdict(int)
        for index, parser in enumerate(lazy_parse_simple_annotation_zip(self.annotations_zip_path)):
            simple_annotation: Dict[str, Any] = parser.load_json()
            annotation_count = len(simple_annotation["details"])
            result[parser.task_id] += annotation_count
            if (index + 1) % 10000 == 0:
                logger.debug(f"{self.logging_prefix}: {index+1} 件の入力データに含まれているアノテーション情報を読み込みました。")

        return result

    def get_inspection_comment_count_by_task(self) -> Dict[str, int]:
        """
        タスクごとに指摘を受けた検査コメント数を取得します。

        Returns:
            key: task_id, value: 指摘を受けた検査コメント数のdictです。
        """

        def is_target_comment(comment: Dict[str, Any]) -> bool:
            """
            指摘を受けたコメントか否か
            """
            if comment["comment_type"] != "inspection":
                return False

            comment_node = comment["comment_node"]
            if comment_node["_type"] != "Root":
                return False

            if comment_node["status"] != CommentStatus.RESOLVED.value:
                return False
            return True

        logger.debug(f"{self.logging_prefix}: コメント全件ファイルを読み込みます。file='{self.comment_json_path}'")

        with open(str(self.comment_json_path), encoding="utf-8") as f:
            all_comments = json.load(f)

        tasks_dict: Dict[str, int] = defaultdict(int)

        for comment in all_comments:
            task_id = comment["task_id"]
            if is_target_comment(comment):
                tasks_dict[task_id] += 1

        return tasks_dict

    def read_task_histories_from_json(self, task_id_list: Optional[List[str]] = None) -> Dict[str, List[TaskHistory]]:
        logger.debug(f"{self.logging_prefix}: タスク履歴全件ファイルを読み込みます。file='{self.task_histories_json_path}'")
        with open(str(self.task_histories_json_path), encoding="utf-8") as f:
            task_histories_dict = json.load(f)

        if task_id_list is not None:
            removed_task_id_set = set(task_histories_dict.keys()) - set(task_id_list)
            for task_id in removed_task_id_set:
                del task_histories_dict[task_id]

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

    def wait_for_completion_updated_task_json(self, project_id: str):
        MAX_JOB_ACCESS = 120
        JOB_ACCESS_INTERVAL = 60
        MAX_WAIT_MINUTE = MAX_JOB_ACCESS * JOB_ACCESS_INTERVAL / 60
        result = self.annofab_service.wrapper.wait_for_completion(
            project_id,
            job_type=ProjectJobType.GEN_TASKS_LIST,
            job_access_interval=JOB_ACCESS_INTERVAL,
            max_job_access=MAX_JOB_ACCESS,
        )
        if result:
            logger.info(f"{self.logging_prefix}: タスク全件ファイルの更新が完了しました。")
        else:
            logger.info(f"{self.logging_prefix}: タスク全件ファイルの更新に失敗しました or {MAX_WAIT_MINUTE} 分待っても、更新が完了しませんでした。")
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
        logger.debug(f"{self.logging_prefix}: タスクの最終更新日時={last_tasks_updated_datetime}")
        if last_tasks_updated_datetime is None:
            logger.warning("{self.logging_prefix}: タスクの最終更新日時がNoneなので、アノテーションzipを更新しません。")
            return

        annotation_specs_history = self.annofab_service.api.get_annotation_specs_histories(project_id)[0]
        annotation_specs_updated_datetime = annotation_specs_history[-1]["updated_datetime"]
        logger.debug(f"{self.logging_prefix}: アノテーション仕様の最終更新日時={annotation_specs_updated_datetime}")

        job_list = self.annofab_service.api.get_project_job(
            project_id, query_params={"type": ProjectJobType.GEN_ANNOTATION.value, "limit": 1}
        )[0]["list"]
        if len(job_list) > 0:
            job = job_list[0]
            logger.debug(
                f"{self.logging_prefix}: アノテーションzipの最終更新日時={job['updated_datetime']}, job_status={job['job_status']}"
            )

        if should_update_annotation_zip:
            if len(job_list) == 0:
                self.annofab_service.api.post_annotation_archive_update(project_id)
                self.wait_for_completion_updated_annotation(project_id)
            else:
                job = job_list[0]
                job_status = JobStatus(job["job_status"])
                if job_status == JobStatus.PROGRESS:
                    logger.info(f"{self.logging_prefix}: アノテーション更新が完了するまで待ちます。")
                    self.wait_for_completion_updated_annotation(project_id)

                elif job_status == JobStatus.SUCCEEDED:
                    if dateutil.parser.parse(job["updated_datetime"]) < dateutil.parser.parse(
                        last_tasks_updated_datetime
                    ):
                        logger.info(f"{self.logging_prefix}: タスクの最新更新日時よりアノテーションzipの最終更新日時の方が古いので、アノテーションzipを更新します。")
                        self.annofab_service.api.post_annotation_archive_update(project_id)
                        self.wait_for_completion_updated_annotation(project_id)

                    elif dateutil.parser.parse(job["updated_datetime"]) < dateutil.parser.parse(
                        annotation_specs_updated_datetime
                    ):
                        logger.info(
                            f"{self.logging_prefix}: アノテーション仕様の更新日時よりアノテーションzipの最終更新日時の方が古いので、アノテーションzipを更新します。"
                        )
                        self.annofab_service.api.post_annotation_archive_update(project_id)
                        self.wait_for_completion_updated_annotation(project_id)

                    else:
                        logger.info(f"{self.logging_prefix}: アノテーションzipを更新する必要がないので、更新しません。")

                elif job_status == JobStatus.FAILED:
                    logger.info("{self.logging_prefix}: ノテーションzipの更新に失敗しているので、アノテーションzipを更新します。")
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
            project_id, query_params={"type": ProjectJobType.GEN_TASKS_LIST.value, "limit": 1}
        )[0]["list"]

        if len(job_list) == 0:
            if should_update_task_json:
                self.annofab_service.api.post_project_tasks_update(project_id)
                self.wait_for_completion_updated_task_json(project_id)

        else:
            job = job_list[0]
            logger.debug(
                f"{self.logging_prefix}: タスク全件ファイルの最終更新日時={job['updated_datetime']}, job_status={job['job_status']}"
            )

            if should_update_task_json:
                job_status = JobStatus(job["job_status"])
                if job_status == JobStatus.PROGRESS:
                    logger.info(f"{self.logging_prefix}: タスク全件ファイルの更新が完了するまで待ちます。")
                    self.wait_for_completion_updated_task_json(project_id)

                elif job_status == JobStatus.SUCCEEDED:
                    self.annofab_service.api.post_project_tasks_update(project_id)
                    self.wait_for_completion_updated_task_json(project_id)

                elif job_status == JobStatus.FAILED:
                    logger.info("{self.logging_prefix}: タスク全件ファイルの更新に失敗しているので、タスク全件ファイルを更新します。")
                    self.annofab_service.api.post_project_tasks_update(project_id)
                    self.wait_for_completion_updated_task_json(project_id)

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

        job_list = self.annofab_service.api.get_project_job(
            self.project_id, query_params={"type": ProjectJobType.GEN_ANNOTATION.value, "limit": 1}
        )[0]["list"]
        if len(job_list) == 0:
            logger.debug(f"{self.logging_prefix}: アノテーションzipの最終更新日時は不明です。")
        else:
            job = job_list[0]
            logger.debug(
                f"{self.logging_prefix}: アノテーションzipの最終更新日時={job['updated_datetime']}, job_status={job['job_status']}"
            )

    def _download_db_file(self, is_latest: bool, is_get_task_histories_one_of_each: bool):
        """
        DBになりうるファイルをダウンロードする

        Args:
            is_latest: True なら最新のファイルをダウンロードする
            is_execute_task_history_api: Trueなら `get_task_histories` APIを実行する
        """

        downloading_obj = DownloadingFile(self.annofab_service)

        wait_options = WaitOptions(interval=60, max_tries=360)

        downloading_obj.download_task_json(
            self.project_id, dest_path=str(self.tasks_json_path), is_latest=is_latest, wait_options=wait_options
        )
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
                downloading_obj.download_task_history_json(
                    self.project_id, dest_path=str(self.task_histories_json_path)
                )
            except DownloadingFileNotFoundError:
                # プロジェクトを作成した日だと、タスク履歴全県ファイルが作成されていないので、DownloadingFileNotFoundErrorが発生する
                # その場合でも、処理は継続できるので、タスク履歴APIを１個ずつ実行して、タスク履歴ファイルを作成する
                self._write_task_histories_json_with_executing_api_one_of_each()

    @staticmethod
    def _to_datetime_with_tz(str_date: str) -> datetime.datetime:
        dt = dateutil.parser.parse(str_date)
        dt = dt.replace(tzinfo=dateutil.tz.tzlocal())
        return dt

    def read_tasks_from_json(
        self,
    ) -> List[Task]:
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

        def filter_task(arg_task: Dict[str, Any]) -> bool:
            """
            検索条件にマッチするかどうか

            Returns:
                Trueを返すなら検索条件にマッチする
            """

            flag = True
            if query.task_query is not None:
                flag = flag and match_task_with_query(DcTask.from_dict(arg_task), query.task_query)

            if query.task_ids is not None:
                flag = flag and arg_task["task_id"] in query.task_ids

            # 終了日で絞り込む
            # 開始日の絞り込み条件はタスク履歴を見る
            if dt_end_date is not None:
                flag = flag and (dateutil.parser.parse(arg_task["updated_datetime"]) < dt_end_date)

            return flag

        logger.debug(f"{self.logging_prefix}: タスク全件ファイルを読み込みます。file='{self.tasks_json_path}'")
        with open(str(self.tasks_json_path), encoding="utf-8") as f:
            all_tasks = json.load(f)

        filtered_task_list = [task for task in all_tasks if filter_task(task)]

        if self.query.start_date is not None:
            # start_dateは教師付開始日でみるため、タスク履歴を参照する必要あり
            dict_task_histories = self.read_task_histories_from_json()
            filtered_task_list = self._filter_task_with_task_history(
                filtered_task_list, dict_task_histories=dict_task_histories, start_date=self.query.start_date
            )

        logger.debug(f"{self.logging_prefix}: 集計対象のタスク数 = {len(filtered_task_list)}")
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

            has_task_creation = task_histories[0]["account_id"] is None
            if has_task_creation and len(task_histories) < 2:
                return False

            # 初回教師付けの開始日時をfirst_started_datetimeとするため「(タスク作成)」の履歴がある場合はスキップする。
            first_started_datetime = (task_histories[0] if not has_task_creation else task_histories[1])[
                "started_datetime"
            ]
            if first_started_datetime is None:
                return False
            return dateutil.parser.parse(first_started_datetime) >= dt_start_date

        return [task for task in task_list if pred(task["task_id"])]

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
