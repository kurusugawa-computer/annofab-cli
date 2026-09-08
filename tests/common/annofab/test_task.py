from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import annofabapi

from annofabcli.common.annofab.task import get_task_dict_in_bulk


def test_get_task_dict_in_bulk() -> None:
    api = Mock()
    api.get_tasks_in_bulk.return_value = (
        {
            "success": [{"task_id": "task1"}],
            "failure": [{"task_id": "missing"}],
        },
        Mock(),
    )
    service = cast(annofabapi.Resource, SimpleNamespace(api=api))

    result = get_task_dict_in_bulk(service, "project1", ["task1", "missing"])

    assert result == {"task1": {"task_id": "task1"}}
