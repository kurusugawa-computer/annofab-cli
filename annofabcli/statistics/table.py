from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import more_itertools
import pandas
from annofabapi.models import Task, TaskPhase

import annofabcli
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import isoduration_to_hour
from annofabcli.statistics.database import Database
from annofabcli.task.list_all_tasks_added_task_history import AddingAdditionalInfoToTask

logger = logging.getLogger(__name__)


class Table:
    """
    Databaseから取得した情報を元にPandas DataFrameを生成するクラス
    チェックポイントファイルがあること前提

    Attributes:
        inspection_phrases_dict: 定型指摘IDとそのコメント
        project_members_dict: account_idとプロジェクトメンバ情報

    """

    #############################################
    # Private
    #############################################

    _task_list: Optional[List[Task]] = None
    _task_histories_dict: Optional[Dict[str, List[dict[str, Any]]]] = None

    def __init__(
        self,
        database: Database,
    ) -> None:
        self.annofab_service = database.annofab_service
        self.annofab_facade = AnnofabApiFacade(database.annofab_service)
        self.database = database

        self.project_id = self.database.project_id
        self.project_members_dict = self._get_project_members_dict()

        self.project_title = self.annofab_service.api.get_project(self.project_id)[0]["title"]

    def _get_task_list(self) -> List[Task]:
        """
        self.task_listを返す。Noneならば、self.task_list, self.task_id_listを設定する。
        """
        if self._task_list is not None:
            return self._task_list
        else:
            task_list = self.database.read_tasks_from_json()
            self._task_list = task_list
            return self._task_list

    def _get_task_histories_dict(self) -> Dict[str, List[dict[str, Any]]]:
        if self._task_histories_dict is not None:
            return self._task_histories_dict
        else:
            task_id_list = [t["task_id"] for t in self._get_task_list()]
            self._task_histories_dict = self.database.read_task_histories_from_json(task_id_list)
            return self._task_histories_dict

    @staticmethod
    def operator_is_changed_by_phase(task_history_list: List[dict[str, Any]], phase: TaskPhase) -> bool:
        """
        フェーズ内の作業者が途中で変わったかどうか

        Args:
            task_history_list: タスク履歴List
            phase: フェーズ

        Returns:
            Trueならばフェーズ内の作業者が途中で変わった
        """
        account_id_list = [
            e["account_id"]
            for e in task_history_list
            if TaskPhase(e["phase"]) == phase and e["account_id"] is not None and isoduration_to_hour(e["accumulated_labor_time_milliseconds"]) > 0
        ]
        return len(set(account_id_list)) >= 2

    def _get_user_id(self, account_id: Optional[str]) -> Optional[str]:
        """
        プロジェクトメンバのuser_idを返す。
        """
        if account_id is None:
            return None

        member = self.annofab_facade.get_project_member_from_account_id(self.project_id, account_id)
        if member is not None:
            return member["user_id"]
        else:
            return None

    def _get_username(self, account_id: Optional[str]) -> Optional[str]:
        """
        プロジェクトメンバのusernameを返す。
        """
        if account_id is None:
            return None

        member = self.annofab_facade.get_project_member_from_account_id(self.project_id, account_id)
        if member is not None:
            return member["username"]
        else:
            return None

    def _get_biography(self, account_id: Optional[str]) -> Optional[str]:
        """
        ユーザのbiographyを取得する。存在しないメンバであればNoneを返す。
        """
        if account_id is None:
            return None

        member = self.annofab_facade.get_project_member_from_account_id(self.project_id, account_id)
        if member is not None:
            return member["biography"]
        else:
            return None

    def _get_project_members_dict(self) -> Dict[str, Any]:
        project_members_dict = {}
        project_members = self.annofab_service.wrapper.get_all_project_members(self.project_id, query_params={"include_inactive_member": True})
        for member in project_members:
            project_members_dict[member["account_id"]] = member
        return project_members_dict

    @classmethod
    def set_task_histories(cls, task: Task, task_histories: List[dict[str, Any]]) -> Task:
        """
        タスク履歴関係の情報を設定する
        """

        task["worktime_hour"] = sum(annofabcli.common.utils.isoduration_to_hour(e["accumulated_labor_time_milliseconds"]) for e in task_histories)

        return task

    @staticmethod
    def _get_task_from_task_id(task_list: List[Task], task_id: str) -> Optional[Task]:
        return more_itertools.first_true(task_list, pred=lambda e: e["task_id"] == task_id)

    def create_task_df(self) -> pandas.DataFrame:
        """
        タスク一覧からdataframeを作成する。
        新たに追加した列は、user_id, annotation_count, inspection_comment_count,
            first_annotation_user_id, first_annotation_started_datetime,
            annotation_worktime_hour, inspection_worktime_hour, acceptance_worktime_hour, worktime_hour
        """
        tasks = self._get_task_list()
        task_histories_dict = self._get_task_histories_dict()
        inspections_dict = self.database.get_inspection_comment_count_by_task()
        annotations_dict = self.database.get_annotation_count_by_task()

        adding_obj = AddingAdditionalInfoToTask(self.annofab_service, project_id=self.project_id)

        for task in tasks:
            adding_obj.add_additional_info_to_task(task)

            task_id = task["task_id"]
            task_histories = task_histories_dict.get(task_id, [])

            task["input_data_count"] = len(task["input_data_id_list"])

            # タスク履歴から取得できる付加的な情報を追加する
            adding_obj.add_task_history_additional_info_to_task(task, task_histories)
            self.set_task_histories(task, task_histories)

            task["annotation_count"] = annotations_dict.get(task_id, 0)
            task["inspection_comment_count"] = inspections_dict.get(task_id, 0)

        df = pandas.DataFrame(tasks)
        if len(df) > 0:
            # dictが含まれたDataFrameをbokehでグラフ化するとErrorが発生するので、dictを含む列を削除する
            # https://github.com/bokeh/bokeh/issues/9620
            df = df.drop(["histories_by_phase"], axis=1)
            return df
        else:
            logger.warning("タスク一覧が0件です。")

            numeric_columns = [
                "worktime_hour",
                "annotation_worktime_hour",
                "inspection_worktime_hour",
                "acceptance_worktime_hour",
                "input_data_count",
                "annotation_count",
                "inspection_comment_count",
                "number_of_rejections_by_inspection",
                "number_of_rejections_by_acceptance",
            ]
            string_columns = [
                "project_id",
                "task_id",
                "phase",
                "phase_stage",
                "status",
                "first_annotation_user_id",
                "first_annotation_username",
                "first_annotation_worktime_hour",
                "first_annotation_started_datetime",
                "first_inspection_user_id",
                "first_inspection_username",
                "first_inspection_worktime_hour",
                "first_inspection_started_datetime",
                "first_acceptance_user_id",
                "first_acceptance_username",
                "first_acceptance_worktime_hour",
                "first_acceptance_started_datetime",
                "first_acceptance_completed_datetime",
            ]
            boolean_columns = ["inspection_is_skipped", "acceptance_is_skipped"]
            columns = string_columns + numeric_columns + boolean_columns
            dtypes = {e: "float64" for e in numeric_columns}
            dtypes.update({e: "boolean" for e in boolean_columns})
            return pandas.DataFrame([], columns=columns).astype(dtypes)
