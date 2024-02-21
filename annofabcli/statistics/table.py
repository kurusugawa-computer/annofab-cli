from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from annofabapi.models import Task

from annofabcli.statistics.database import Database

logger = logging.getLogger(__name__)


class Table:
    """
    Databaseから取得した情報を元にPandas DataFrameを生成するクラス
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
        self.database = database

        self.project_id = self.database.project_id
        self.project_members_dict = self._get_project_members_dict()

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

    def _get_project_members_dict(self) -> Dict[str, Any]:
        project_members_dict = {}
        project_members = self.annofab_service.wrapper.get_all_project_members(self.project_id, query_params={"include_inactive_member": True})
        for member in project_members:
            project_members_dict[member["account_id"]] = member
        return project_members_dict
