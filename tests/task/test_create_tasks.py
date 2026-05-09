from pathlib import Path
from unittest.mock import Mock

import pytest

from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE
from annofabcli.task import create_tasks, put_tasks


def test_get_task_relation_dict_from_header_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "task.csv"
    csv_file.write_text(
        "input_data_id,task_id,extra\ninput_data_001,task_001,a\ninput_data_002,task_001,b\ninput_data_003,task_002,c\n",
        encoding="utf-8",
    )

    actual = create_tasks.get_task_relation_dict(csv_file)

    assert actual == {
        "task_001": ["input_data_001", "input_data_002"],
        "task_002": ["input_data_003"],
    }


def test_get_task_relation_dict_from_header_csv_with_missing_column(tmp_path: Path) -> None:
    csv_file = tmp_path / "task.csv"
    csv_file.write_text("task_id\nfoo\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        create_tasks.get_task_relation_dict(csv_file)

    assert exc_info.value.code == COMMAND_LINE_ERROR_STATUS_CODE


def test_get_task_relation_dict_from_headerless_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "task.csv"
    csv_file.write_text("task_001,input_data_001\ntask_001,input_data_002\n", encoding="utf-8")

    actual = put_tasks.get_task_relation_dict(csv_file)

    assert actual == {
        "task_001": ["input_data_001", "input_data_002"],
    }


def test_get_task_creation_info_list_from_task_relation_dict() -> None:
    actual = create_tasks.get_task_creation_info_list_from_task_relation_dict(
        {"task_001": ["input_data_001", "input_data_002"]},
        common_metadata={"priority": 1},
    )

    assert actual == [
        create_tasks.TaskCreationInfo(
            task_id="task_001",
            input_data_id_list=["input_data_001", "input_data_002"],
            metadata={"priority": 1},
        )
    ]


def test_get_task_creation_info_list_from_task_relation_dict_with_common_user_id() -> None:
    actual = create_tasks.get_task_creation_info_list_from_task_relation_dict(
        {"task_001": ["input_data_001", "input_data_002"]},
        common_user_id="alice",
    )

    assert actual == [
        create_tasks.TaskCreationInfo(
            task_id="task_001",
            input_data_id_list=["input_data_001", "input_data_002"],
            metadata={},
            user_id="alice",
        )
    ]


def test_get_metadata_from_json_args() -> None:
    actual = create_tasks.get_metadata_from_json_args('{"priority":1,"category":"foo","required":true}')

    assert actual == {"priority": 1, "category": "foo", "required": True}


def test_get_metadata_from_json_args_with_invalid_json() -> None:
    with pytest.raises(TypeError):
        create_tasks.get_metadata_from_json_args('{"foo": null}')


def test_get_task_creation_info_list_from_json_args() -> None:
    actual = create_tasks.get_task_creation_info_list_from_json_args(
        """
        [
            {
                "task_id": "task_001",
                "input_data_id_list": ["input_data_001", "input_data_002"],
                "metadata": {"priority": 2},
                "user_id": "alice",
                "status": "not_started"
            },
            {
                "task_id": "task_002",
                "input_data_id_list": ["input_data_003"]
            }
        ]
        """,
        common_metadata={"priority": 1, "category": "foo"},
    )

    assert actual == [
        create_tasks.TaskCreationInfo(
            task_id="task_001",
            input_data_id_list=["input_data_001", "input_data_002"],
            metadata={"priority": 2, "category": "foo"},
            user_id="alice",
        ),
        create_tasks.TaskCreationInfo(
            task_id="task_002",
            input_data_id_list=["input_data_003"],
            metadata={"priority": 1, "category": "foo"},
        ),
    ]


def test_get_task_creation_info_list_from_json_args_with_common_user_id() -> None:
    actual = create_tasks.get_task_creation_info_list_from_json_args(
        """
        [
            {
                "task_id": "task_001",
                "input_data_id_list": ["input_data_001"],
                "user_id": null
            }
        ]
        """,
        common_user_id="alice",
    )

    assert actual == [
        create_tasks.TaskCreationInfo(
            task_id="task_001",
            input_data_id_list=["input_data_001"],
            metadata={},
            user_id="alice",
        ),
    ]


def test_get_task_creation_info_list_from_json_args_with_invalid_json() -> None:
    with pytest.raises(TypeError):
        create_tasks.get_task_creation_info_list_from_json_args('{"task_001": ["input_data_001"]}')


def test_get_task_creation_info_list_from_json_args_with_missing_input_data_id_list() -> None:
    with pytest.raises(TypeError):
        create_tasks.get_task_creation_info_list_from_json_args('[{"task_id": "task_001"}]')


def test_get_task_creation_info_list_from_json_args_with_invalid_metadata() -> None:
    with pytest.raises(TypeError):
        create_tasks.get_task_creation_info_list_from_json_args('[{"task_id": "task_001", "input_data_id_list": ["input_data_001"], "metadata": {"foo": null}}]')


def test_get_task_creation_info_list_from_json_args_with_duplicate_task_id() -> None:
    with pytest.raises(ValueError):
        create_tasks.get_task_creation_info_list_from_json_args(
            """
            [
                {"task_id": "task_001", "input_data_id_list": ["input_data_001"]},
                {"task_id": "task_001", "input_data_id_list": ["input_data_002"]}
            ]
            """
        )


def test_get_task_creation_info_list_from_json_args_with_invalid_user_id() -> None:
    with pytest.raises(TypeError):
        create_tasks.get_task_creation_info_list_from_json_args('[{"task_id": "task_001", "input_data_id_list": ["input_data_001"], "user_id": 1}]')


def test_create_task_with_user_id() -> None:
    service = Mock()
    service.wrapper.get_task_or_none.return_value = None
    main_obj = create_tasks.CreateTaskMain(service, project_id="project1", parallelism=None)
    main_obj.facade = Mock()
    main_obj.facade.get_account_id_from_user_id.return_value = "account1"

    result = main_obj.create_task(
        create_tasks.TaskCreationInfo(
            task_id="task_001",
            input_data_id_list=["input_data_001"],
            metadata={},
            user_id="alice",
        ),
    )

    assert result is True
    service.api.put_task.assert_called_once_with("project1", "task_001", request_body={"input_data_id_list": ["input_data_001"]})
    service.wrapper.change_task_operator.assert_called_once_with("project1", "task_001", operator_account_id="account1")


def test_validate_user_id_with_not_project_member() -> None:
    service = Mock()
    main_obj = create_tasks.CreateTaskMain(service, project_id="project1", parallelism=None)
    main_obj.facade = Mock()
    main_obj.facade.get_account_id_from_user_id.return_value = None

    with pytest.raises(SystemExit) as exc_info:
        main_obj.validate_user_id(
            [
                create_tasks.TaskCreationInfo(
                    task_id="task_001",
                    input_data_id_list=["input_data_001"],
                    metadata={},
                    user_id="alice",
                ),
            ]
        )

    assert exc_info.value.code == COMMAND_LINE_ERROR_STATUS_CODE


def test_validate_task_id_is_unique_with_duplicate_task_id() -> None:
    service = Mock()
    main_obj = create_tasks.CreateTaskMain(service, project_id="project1", parallelism=None)

    with pytest.raises(SystemExit) as exc_info:
        main_obj.validate_task_id_is_unique(
            [
                create_tasks.TaskCreationInfo(
                    task_id="task_001",
                    input_data_id_list=["input_data_001"],
                    metadata={},
                ),
                create_tasks.TaskCreationInfo(
                    task_id="task_001",
                    input_data_id_list=["input_data_002"],
                    metadata={},
                ),
            ]
        )

    assert exc_info.value.code == COMMAND_LINE_ERROR_STATUS_CODE


def test_validate_task_does_not_exist_with_existing_task() -> None:
    service = Mock()
    service.wrapper.get_task_or_none.return_value = {"task_id": "task_001"}
    main_obj = create_tasks.CreateTaskMain(service, project_id="project1", parallelism=None)

    with pytest.raises(SystemExit) as exc_info:
        main_obj.validate_task_does_not_exist(
            [
                create_tasks.TaskCreationInfo(
                    task_id="task_001",
                    input_data_id_list=["input_data_001"],
                    metadata={},
                ),
            ]
        )

    assert exc_info.value.code == COMMAND_LINE_ERROR_STATUS_CODE
