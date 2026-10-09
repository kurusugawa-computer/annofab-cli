import json
from argparse import Namespace
from unittest.mock import Mock

import pytest

from annofabcli.task_count.list_by_metadata import ListTaskCountByMetadata
from annofabcli.task_count.list_by_phase import ListTaskCountByPhase
from annofabcli.task_count.list_by_task_id_group import ListTaskCountByTaskIdGroup
from annofabcli.task_count.list_by_user import ListTaskCountByUser


@pytest.mark.parametrize("command_class", [ListTaskCountByPhase, ListTaskCountByMetadata, ListTaskCountByTaskIdGroup, ListTaskCountByUser])
@pytest.mark.parametrize("output_format", ["json", "pretty_json"])
@pytest.mark.parametrize("is_empty", [False, True])
def test_command_outputs_json_summary(command_class, output_format, is_empty, tmp_path):
    service = Mock()
    service.wrapper.get_all_tasks.return_value = (
        []
        if is_empty
        else [
            {
                "task_id": "train_001",
                "phase": "acceptance",
                "status": "complete",
                "account_id": None,
                "input_data_id_list": ["input1", "input2"],
                "metadata": {},
            }
        ]
    )
    service.api.get_task_histories.return_value = ([], None)
    output = tmp_path / "summary.json"
    args = Namespace(
        project_id="project1",
        yes=True,
        format=output_format,
        output=output,
        unit="input_data_count",
        execute_get_tasks_api=True,
        not_worked_threshold_second=0,
        metadata_key=["dataset"],
        temp_dir=tmp_path,
        task_id_delimiter="_",
        task_id_groups=None,
        task_id_group_component_count=None,
        single_group=False,
        legacy_output=False,
    )

    command_class(service, Mock(), args).main()

    contents = output.read_text()
    actual = json.loads(contents)
    assert "NaN" not in contents
    if is_empty:
        assert actual == []
    else:
        assert len(actual) == 1
        if command_class is ListTaskCountByPhase:
            assert actual[0]["phase"] == "acceptance"
            assert actual[0]["complete"] == 2
        else:
            assert actual[0]["acceptance.complete"] == 2
        if command_class in [ListTaskCountByPhase, ListTaskCountByMetadata, ListTaskCountByUser]:
            assert actual[0]["metadata.dataset"] is None
        if command_class is ListTaskCountByTaskIdGroup:
            assert actual[0]["task_id_group"] == "train"
        if command_class is ListTaskCountByUser:
            assert actual[0]["user_id"] == "unassigned"
            assert actual[0]["username"] is None
            assert actual[0]["biography"] is None
