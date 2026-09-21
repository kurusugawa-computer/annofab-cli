import pytest

from annofabcli.task import update_metadata_per_task
from annofabcli.task.update_metadata_of_task import TaskMetadataInfo


def test_get_task_metadata_info_list_from_json_args() -> None:
    actual = update_metadata_per_task.get_task_metadata_info_list_from_json_args(
        """
        [
            {"task_id": "task_001", "metadata": {"priority": 1}, "status": "not_started"},
            {"task_id": "task_002", "metadata": {"required": true}}
        ]
        """
    )

    assert actual == [
        TaskMetadataInfo(task_id="task_001", metadata={"priority": 1}),
        TaskMetadataInfo(task_id="task_002", metadata={"required": True}),
    ]


def test_get_task_metadata_info_list_from_json_args_with_non_list_json() -> None:
    with pytest.raises(TypeError):
        update_metadata_per_task.get_task_metadata_info_list_from_json_args('{"task_001": {"priority": 1}}')


def test_get_task_metadata_info_list_from_json_args_with_duplicate_task_id() -> None:
    with pytest.raises(ValueError):
        update_metadata_per_task.get_task_metadata_info_list_from_json_args('[{"task_id": "task_001", "metadata": {}}, {"task_id": "task_001", "metadata": {}}]')
