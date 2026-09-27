import argparse
from pathlib import Path
from unittest.mock import Mock

import pytest

from annofabcli.task import update_input_data


@pytest.mark.parametrize(
    ("old_input_data_id_list", "new_input_data_id_list", "expected_diff"),
    [
        (
            ["input1", "input2"],
            ["input1", "input2", "input3"],
            update_input_data.TaskInputDataDiff(
                added_input_data_id_list=["input3"],
                removed_input_data_id_list=[],
                order_changed=False,
            ),
        ),
        (
            ["input1", "input2", "input3"],
            ["input3", "input1", "input2"],
            update_input_data.TaskInputDataDiff(
                added_input_data_id_list=[],
                removed_input_data_id_list=[],
                order_changed=True,
            ),
        ),
        (
            ["input1", "input2", "input3"],
            ["input1", "input3"],
            update_input_data.TaskInputDataDiff(
                added_input_data_id_list=[],
                removed_input_data_id_list=["input2"],
                order_changed=False,
            ),
        ),
        (
            ["input1", "input2"],
            ["input2", "input3", "input1"],
            update_input_data.TaskInputDataDiff(
                added_input_data_id_list=["input3"],
                removed_input_data_id_list=[],
                order_changed=True,
            ),
        ),
    ],
)
def test_calculate_task_input_data_diff(
    old_input_data_id_list: list[str],
    new_input_data_id_list: list[str],
    expected_diff: update_input_data.TaskInputDataDiff,
) -> None:
    actual = update_input_data.calculate_task_input_data_diff(old_input_data_id_list, new_input_data_id_list)

    assert actual == expected_diff


def test_get_task_input_data_update_info_list_from_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "task.csv"
    csv_file.write_text(
        "input_data_id,task_id,extra\ninput2,task1,a\ninput1,task1,b\ninput3,task2,c\n",
        encoding="utf-8",
    )

    actual = update_input_data.get_task_input_data_update_info_list_from_csv(csv_file)

    assert actual == [
        update_input_data.TaskInputDataUpdateInfo(task_id="task1", input_data_id_list=["input2", "input1"]),
        update_input_data.TaskInputDataUpdateInfo(task_id="task2", input_data_id_list=["input3"]),
    ]


@pytest.mark.parametrize(
    "csv_content",
    [
        "task_id,input_data_id\ntask1,\n",
        "task_id,input_data_id\n,input1\n",
        "task_id,input_data_id\ntask1,input1\ntask1,input1\n",
    ],
)
def test_get_task_input_data_update_info_list_from_invalid_csv(tmp_path: Path, csv_content: str) -> None:
    csv_file = tmp_path / "task.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    with pytest.raises(ValueError):
        update_input_data.get_task_input_data_update_info_list_from_csv(csv_file)


def test_get_task_input_data_update_info_list_from_json() -> None:
    actual = update_input_data.get_task_input_data_update_info_list_from_json('[{"task_id":"task1","input_data_id_list":["input2","input1"],"metadata":{"foo":"bar"}}]')

    assert actual == [update_input_data.TaskInputDataUpdateInfo(task_id="task1", input_data_id_list=["input2", "input1"])]


@pytest.mark.parametrize(
    "json_value",
    [
        '{"task_id":"task1","input_data_id_list":["input1"]}',
        '[{"task_id":"task1"}]',
        '[{"task_id":"task1","input_data_id_list":["input1","input1"]}]',
        '[{"task_id":"task1","input_data_id_list":["input1"]},{"task_id":"task1","input_data_id_list":["input2"]}]',
    ],
)
def test_get_task_input_data_update_info_list_from_invalid_json(json_value: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        update_input_data.get_task_input_data_update_info_list_from_json(json_value)


def test_update_task_input_data_adds_input_data_and_preserves_metadata() -> None:
    service = Mock()
    main_obj = update_input_data.UpdateTaskInputDataMain(service, "project1", all_yes=True)
    existing_task_dict = {
        "task1": {
            "task_id": "task1",
            "input_data_id_list": ["input1", "input2"],
            "metadata": {"priority": 1},
        }
    }

    actual = main_obj.update_task_input_data(
        update_input_data.TaskInputDataUpdateInfo(task_id="task1", input_data_id_list=["input1", "input2", "input3"]),
        existing_task_dict=existing_task_dict,
    )

    assert actual == update_input_data.UpdateResult.UPDATED
    service.api.put_task.assert_called_once_with(
        "project1",
        "task1",
        request_body={"input_data_id_list": ["input1", "input2", "input3"], "metadata": {"priority": 1}},
    )


def test_update_task_input_data_reorders_input_data() -> None:
    service = Mock()
    main_obj = update_input_data.UpdateTaskInputDataMain(service, "project1", all_yes=True)

    actual = main_obj.update_task_input_data(
        update_input_data.TaskInputDataUpdateInfo(task_id="task1", input_data_id_list=["input3", "input1", "input2"]),
        existing_task_dict={"task1": {"task_id": "task1", "input_data_id_list": ["input1", "input2", "input3"]}},
    )

    assert actual == update_input_data.UpdateResult.UPDATED
    assert service.api.put_task.call_count == 1


def test_update_task_input_data_does_not_remove_input_data_without_permission() -> None:
    service = Mock()
    main_obj = update_input_data.UpdateTaskInputDataMain(service, "project1", all_yes=True)

    actual = main_obj.update_task_input_data(
        update_input_data.TaskInputDataUpdateInfo(task_id="task1", input_data_id_list=["input1"]),
        existing_task_dict={"task1": {"task_id": "task1", "input_data_id_list": ["input1", "input2"]}},
    )

    assert actual == update_input_data.UpdateResult.REMOVAL_NOT_ALLOWED
    service.api.put_task.assert_not_called()


def test_update_task_input_data_removes_input_data_with_permission() -> None:
    service = Mock()
    main_obj = update_input_data.UpdateTaskInputDataMain(service, "project1", allow_removing_input_data=True, all_yes=True)

    actual = main_obj.update_task_input_data(
        update_input_data.TaskInputDataUpdateInfo(task_id="task1", input_data_id_list=["input1"]),
        existing_task_dict={"task1": {"task_id": "task1", "input_data_id_list": ["input1", "input2"]}},
    )

    assert actual == update_input_data.UpdateResult.UPDATED
    assert service.api.put_task.call_count == 1


def test_update_task_input_data_with_no_change_does_not_call_api() -> None:
    service = Mock()
    main_obj = update_input_data.UpdateTaskInputDataMain(service, "project1", all_yes=True)

    actual = main_obj.update_task_input_data(
        update_input_data.TaskInputDataUpdateInfo(task_id="task1", input_data_id_list=["input1"]),
        existing_task_dict={"task1": {"task_id": "task1", "input_data_id_list": ["input1"]}},
    )

    assert actual == update_input_data.UpdateResult.UNCHANGED
    service.api.put_task.assert_not_called()


def test_update_task_input_data_with_missing_task_does_not_call_api() -> None:
    service = Mock()
    main_obj = update_input_data.UpdateTaskInputDataMain(service, "project1", all_yes=True)

    actual = main_obj.update_task_input_data(
        update_input_data.TaskInputDataUpdateInfo(task_id="task1", input_data_id_list=["input1"]),
        existing_task_dict={},
    )

    assert actual == update_input_data.UpdateResult.NOT_FOUND
    service.api.put_task.assert_not_called()


def test_validate_rejects_parallelism_without_yes() -> None:
    args = argparse.Namespace(parallelism=2, yes=False, allow_removing_input_data=False)

    assert update_input_data.UpdateTaskInputData.validate(args) is False


def test_validate_rejects_parallelism_with_removing_input_data() -> None:
    args = argparse.Namespace(parallelism=2, yes=True, allow_removing_input_data=True)

    assert update_input_data.UpdateTaskInputData.validate(args) is False


def test_validate_accepts_parallelism_with_yes() -> None:
    args = argparse.Namespace(parallelism=2, yes=True, allow_removing_input_data=False)

    assert update_input_data.UpdateTaskInputData.validate(args) is True
