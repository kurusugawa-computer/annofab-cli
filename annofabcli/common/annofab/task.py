import logging
from collections.abc import Collection
from typing import Any

import annofabapi

from annofabcli.common.annofab.input_data import BULK_REQUEST_SIZE

logger = logging.getLogger(__name__)


def get_task_dict_in_bulk(service: annofabapi.Resource, project_id: str, task_id_list: Collection[str]) -> dict[str, dict[str, Any]]:
    """タスクをバルク取得し、IDをキーとする辞書で返す。"""
    task_id_list = list(dict.fromkeys(task_id_list))
    task_dict: dict[str, dict[str, Any]] = {}
    for initial_index in range(0, len(task_id_list), BULK_REQUEST_SIZE):
        batch_task_id_list = task_id_list[initial_index : initial_index + BULK_REQUEST_SIZE]
        response, _ = service.api.get_tasks_in_bulk(project_id, query_params={"task_id": ",".join(batch_task_id_list)})
        for task in response["success"]:
            task_dict[task["task_id"]] = task
        for failure_info in response["failure"]:
            logger.debug(f"task_id='{failure_info['task_id']}': タスクは存在しません。")
    return task_dict
