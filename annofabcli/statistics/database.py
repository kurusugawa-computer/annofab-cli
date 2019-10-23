import datetime
import json
import logging
import os
import pickle
import shutil
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import annofabapi
import annofabapi.utils
import dateutil
import more_itertools
from annofabapi.dataclass.annotation import SimpleAnnotationDetail
from annofabapi.models import InputDataId, Inspection, JobStatus, Task, TaskHistory, TaskId
from annofabapi.parser import SimpleAnnotationZipParser, lazy_parse_simple_annotation_zip

from annofabcli.common.exceptions import AnnofabCliException

logger = logging.getLogger(__name__)

InputDataDict = Dict[InputDataId, List[SimpleAnnotationDetail]]



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

    zip_file: Optional[zipfile.ZipFile] = None
    """Simpleアノテーションzipのファイルオブジェク"""

    #############################################
    # Private
    #############################################

    def __init__(self, annofab_service: annofabapi.Resource, project_id: str, chekpoint_dir: str):
        """
        環境変数'ANNOFAB_USER_ID', 'ANNOFAB_PASSWORD'から情報を読み込み、AnnofabApiインスタンスを生成する。
        Args:
            project_id: Annofabのproject_id
        """

        self.annofab_service = annofab_service
        self.project_id = project_id
        self.checkpoint_dir = chekpoint_dir

        # ダウンロードした一括情報
        self.tasks_json_path = Path(f"{self.checkpoint_dir}/tasks.json")
        self.inspection_json_path = Path(f"{self.checkpoint_dir}/inspections.json")
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

    def __update_task_histories(self, tasks: List[Task], not_updated_task_ids: Set[str]):
        pickel_file_name = "task_histories.pickel"
        # 過去のtask_history情報に存在しないtask_id AND 更新されていないタスクのtask_idを取得する
        old_task_histories_dict = self.read_task_histories_from_checkpoint()
        ignored_task_ids = set(old_task_histories_dict.keys()) & not_updated_task_ids

        # APIで情報を取得
        new_task_histories_dict = self.get_task_histories_dict(tasks, ignored_task_ids)
        old_task_histories_dict.update(new_task_histories_dict)

        self.__write_checkpoint(old_task_histories_dict, pickel_file_name)

    def read_tasks_from_checkpoint(self) -> List[Task]:
        result = self.__read_checkpoint("tasks.pickel")
        return result if result is not None else []

    def read_task_histories_from_checkpoint(self) -> Dict[TaskId, List[TaskHistory]]:
        result = self.__read_checkpoint("task_histories.pickel")
        return result if result is not None else {}

    def read_account_statistics_from_checkpoint(self) -> List[Dict[str, Any]]:
        result = self.__read_checkpoint("account_statistics.pickel")
        return result if result is not None else []

    @staticmethod
    def task_exists(task_list: List[Task], task_id) -> bool:
        task = more_itertools.first_true(task_list, pred=lambda e: e["task_id"] == task_id)
        if task is None:
            return False
        else:
            return True

    def read_annotations(self, task_id: str, input_data_id_list: List[str]) -> InputDataDict:
        logger.debug(f"アノテーションzipの読み込み: task_id={task_id}")
        input_data_dict: InputDataDict = {}

        if self.zip_file is None:
            self.zip_file = zipfile.ZipFile(self.annotations_zip_path, 'r')

        for input_data_id in input_data_id_list:
            json_path = f"{task_id}/{input_data_id}.json"
            parser = SimpleAnnotationZipParser(self.zip_file, json_path)
            simple_annotation = parser.parse()
            input_data_dict[input_data_id] = simple_annotation.details

        return input_data_dict

    def read_inspections_from_json(self,
                                   task_id_list: List[TaskId]) -> Dict[TaskId, Dict[InputDataId, List[Inspection]]]:
        logger.debug(f"reading {self.inspection_json_path}")

        with open(str(self.inspection_json_path)) as f:
            all_inspections = json.load(f)

        tasks_dict: Dict[TaskId, Dict[InputDataId, List[Inspection]]] = {}

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

    def _download_simple_annotation(self, dest_path: str):
        _, response = self.annofab_service.api.get_archive_dow_with_pro_id(self.project_id)
        url = response.headers['Location']
        annofabapi.utils.download(url, dest_path)

    def log_for_annotation_zip(self, project_id: str) -> None:
        project, _ = self.annofab_service.api.get_project(project_id)
        last_tasks_updated_datetime = project['summary']['last_tasks_updated_datetime']
        logger.debug(f"タスクの最終更新日時={last_tasks_updated_datetime}")

        job = self.annofab_service.api.get_project_job(project_id, query_params={
            "type": "gen-annotation",
            "limit": 1
        })[0]["list"][0]
        logger.debug(f"アノテーションzipの最終更新日時={job['updated_datetime']}, job_status={job['job_status']}")

        if job['job_status'] == JobStatus.FAILED:
            raise AnnofabCliException("アノテーションzipの更新に失敗しています。")

        if dateutil.parser.parse(last_tasks_updated_datetime) > dateutil.parser.parse(job['updated_datetime']):
            logger.warning(f"タスクの最新更新日時よりアノテーションzipの最終更新日時の方が古いです。")

    def _download_db_file(self):
        """DBになりうるファイルをダウンロードする"""

        self.log_for_annotation_zip(self.project_id)

        logger.debug(f"downloading {str(self.tasks_json_path)}")
        self.annofab_service.wrapper.download_project_tasks_url(self.project_id, str(self.tasks_json_path))

        logger.debug(f"downloading {str(self.inspection_json_path)}")
        self.annofab_service.wrapper.download_project_inspections_url(self.project_id, str(self.inspection_json_path))

        annotations_zip_file = f"{self.checkpoint_dir}/simple-annotations.zip"
        logger.debug(f"downloading {str(annotations_zip_file)}")
        self.annofab_service.wrapper.download_annotation_archive(self.project_id, annotations_zip_file, v2=True)
        # task historiesは未完成なので、使わない

    def read_tasks_from_json(self, task_query_param: Optional[Dict[str, Any]] = None,
                             ignored_task_id_list: Optional[List[TaskId]] = None) -> List[Task]:
        """
        tass.jsonからqueryに合致するタスクを調べる
        Args:
            task_query_param: taskを調べるquery. `phase`と`status`のみ有効
            ignored_task_id_list: 無視するtask_idのList

        Returns:

        """
        def filter_task(arg_task):
            """AND条件で絞り込む"""

            flag = True
            if task_query_param is not None:
                if "phase" in task_query_param:
                    flag = flag and arg_task["phase"] == task_query_param["phase"]

                if "status" in task_query_param:
                    flag = flag and arg_task["status"] == task_query_param["status"]

            if ignored_task_id_list is not None:
                flag = flag and arg_task["task_id"] not in ignored_task_id_list

            return flag

        logger.debug(f"reading {self.tasks_json_path}")
        with open(str(self.tasks_json_path)) as f:
            all_tasks = json.load(f)

        return [task for task in all_tasks if filter_task(task)]

    def update_db(self, task_query_param: Dict[str, Any], ignored_task_ids: Optional[List[str]] = None):
        """
        Annofabから情報を取得し、DB（pickelファイル）を更新する。
        TODO タスク履歴一括ファイルに必要な情報が含まれたら、修正する
        Args:
            task_query_param: タスク取得のクエリパラメタ. デフォルトは受け入れ完了タスク
            ignored_task_ids: 可視化対象外のtask_idのList
        """

        # 残すべきファイル
        self.filename_timestamp = "{0:%Y%m%d-%H%M%S}".format(datetime.datetime.now())

        # DB用のJSONファイルをダウンロードする
        self._download_db_file()

        logger.info(f"DB更新: task_query_param = {task_query_param}")
        tasks = self.read_tasks_from_json(task_query_param)

        if ignored_task_ids is not None:
            # 無視するtask_idを除外する
            logger.info(f"除外するtask_ids = {ignored_task_ids}")
            tasks = [e for e in tasks if e['task_id'] not in ignored_task_ids]

        old_tasks = self.read_tasks_from_checkpoint()
        not_updated_task_ids = self.get_not_updated_task_ids(old_tasks, tasks)
        logger.debug(f"更新されていないtask_id = {not_updated_task_ids}")
        logger.info(f"更新されていないタスク数 = {len(not_updated_task_ids)}")

        self.__update_task_histories(tasks, not_updated_task_ids)
        self.__write_checkpoint(tasks, "tasks.pickel")

        # 統計情報の出力
        account_statistics = self.annofab_service.api.get_account_statistics(self.project_id)[0]
        self.__write_checkpoint(account_statistics, "account_statistics.pickel")

    @staticmethod
    def get_not_updated_task_ids(old_tasks, new_tasks) -> Set[str]:
        """
        更新されていないtask_idのListを取得する
        Args:
            old_tasks:
            new_tasks:

        Returns:

        """
        from dateutil.parser import parse
        updated_task_ids = set()
        for new_task in new_tasks:
            filterd_list = [e for e in old_tasks if e["task_id"] == new_task["task_id"]]
            if len(filterd_list) == 0:
                continue
            old_task = filterd_list[0]
            if parse(old_task["updated_datetime"]) == parse(new_task["updated_datetime"]):
                updated_task_ids.add(new_task["task_id"])

        return updated_task_ids

    def get_task_histories_dict(self, all_tasks: List[Task],
                                ignored_task_ids: Set[str] = None) -> Dict[TaskId, List[TaskHistory]]:
        """
        Annofabからタスク履歴情報を取得する。
        Args:
            all_tasks: 取得対象のタスク一覧
            ignored_task_ids: 取得しないタスクID List

        Returns:
            タスク履歴情報

        """

        if ignored_task_ids is None:
            ignored_task_ids = set()

        tasks = [e for e in all_tasks if e["task_id"] not in ignored_task_ids]
        logger.info(f"タスク履歴取得対象のタスク数 = {len(tasks)}")

        tasks_dict = {}

        for task_index, task in enumerate(tasks):
            if task_index % 10 == 0:
                logger.debug(f"タスク履歴一覧取得中 {task_index} / {len(tasks)} 件目")

            task_id = task["task_id"]
            task_histories = self.annofab_service.api.get_task_histories(self.project_id, task_id)[0]
            tasks_dict.update({task_id: task_histories})

        return tasks_dict

    def close_zip_file(self):
        if self.zip_file is not None:
            self.zip_file.close()
