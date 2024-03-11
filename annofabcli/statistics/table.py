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

    def _get_project_members_dict(self) -> Dict[str, Any]:
        project_members_dict = {}
        project_members = self.annofab_service.wrapper.get_all_project_members(self.project_id, query_params={"include_inactive_member": True})
        for member in project_members:
            project_members_dict[member["account_id"]] = member
        return project_members_dict
