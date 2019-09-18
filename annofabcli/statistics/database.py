import datetime
import json
import logging
import os
import pickle
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import annofabapi
import annofabapi.utils
import more_itertools
from annofabapi.dataclass.annotation import FullAnnotationDetail
from annofabapi.models import Annotation, InputDataId, Inspection, Task, TaskHistory, TaskId
from annofabapi.parser import lazy_parse_full_annotation_zip

logger = logging.getLogger(__name__)

AnnotationDict = Dict[TaskId, Dict[InputDataId, List[FullAnnotationDetail]]]


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
        self.annotations_dir_path = Path(f"{self.checkpoint_dir}/full-annotations")
        self.annotations_zip_path = Path(f"{self.checkpoint_dir}/full-annotations.zip")

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
    def _read_annotations_from_json(input_data_json: Path) -> List[Annotation]:
        with open(str(input_data_json)) as f:
            full_annotation = json.load(f)

        annotation_list = full_annotation["detail"]
        return annotation_list

    @staticmethod
    def task_exists(task_list: List[Task], task_id) -> bool:
        task = more_itertools.first_true(task_list, pred=lambda e: e["task_id"] == task_id)
        if task is None:
            return False
        else:
            return True

    def read_annotations_from_full_annotion_dir(self, task_list: List[Task]) -> AnnotationDict:
        logger.debug(f"reading {self.annotations_dir_path}")

        tasks_dict: AnnotationDict = {}
        iter_parser = lazy_parse_full_annotation_zip(self.annotations_zip_path)
        for parser in iter_parser:
            full_annotation = parser.parse()
            task_id = full_annotation.task_id
            if not self.task_exists(task_list, task_id):
                continue

            input_data_id = full_annotation.input_data_id

            input_data_dict = tasks_dict.get(task_id)
            if input_data_dict is None:
                input_data_dict = {}

            input_data_dict[input_data_id] = full_annotation.detail
            tasks_dict[task_id] = input_data_dict

        return tasks_dict

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

    def _download_full_annotation(self, dest_path: str):
        _, response = self.annofab_service.api.get_archive_full_with_pro_id(self.project_id)
        url = response.headers['Location']
        annofabapi.utils.download(url, dest_path)

    def _download_db_file(self):
        """DBになりうるファイルをダウンロードする"""

        logger.debug(f"downloading {str(self.tasks_json_path)}")
        self.annofab_service.wrapper.download_project_tasks_url(self.project_id, str(self.tasks_json_path))

        logger.debug(f"downloading {str(self.inspection_json_path)}")
        self.annofab_service.wrapper.download_project_inspections_url(self.project_id, str(self.inspection_json_path))

        annotations_zip_file = f"{self.checkpoint_dir}/full-annotations.zip"
        logger.debug(f"downloading {str(annotations_zip_file)}")
        self._download_full_annotation(annotations_zip_file)
        # task historiesは未完成なので、使わない

        # 前のディレクトリを削除する
        if self.annotations_dir_path.exists():
            shutil.rmtree(str(self.annotations_dir_path))

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
