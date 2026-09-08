from collections.abc import Collection

import annofabapi
from annofabapi.models import Task

from annofabcli.common.annofab.input_data import BULK_REQUEST_SIZE


def get_task_dict_in_bulk(service: annofabapi.Resource, project_id: str, task_id_list: Collection[str]) -> dict[str, Task]:
    """タスクをバルク取得し、IDをキーとする辞書で返す。

    存在しないタスクは戻り値に含めない。

    Args:
        service: Annofab APIのリソース。
        project_id: プロジェクトID。
        task_id_list: 取得対象のタスクID。

    Returns:
        タスクIDをキー、タスクを値とする辞書。
    """
    task_id_list = list(dict.fromkeys(task_id_list))
    task_dict: dict[str, Task] = {}
    for initial_index in range(0, len(task_id_list), BULK_REQUEST_SIZE):
        batch_task_id_list = task_id_list[initial_index : initial_index + BULK_REQUEST_SIZE]
        response, _ = service.api.get_tasks_in_bulk(project_id, query_params={"task_id": ",".join(batch_task_id_list)})
        for task in response["success"]:
            task_dict[task["task_id"]] = task
    return task_dict
