import argparse
from pathlib import Path
from unittest.mock import Mock

import pytest

from annofabcli.task import create_tasks, put_tasks


class CreateTaskMainWithoutConfirm(create_tasks.CreateTaskMain):
    def confirm_processing(self, _confirm_message: str) -> bool:
        return False


def test_get_task_creation_info_list_from_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "task.csv"
    csv_file.write_text(
        "input_data_id,task_id,extra\ninput_data_001,task_001,a\ninput_data_002,task_001,b\ninput_data_003,task_002,c\n",
        encoding="utf-8",
    )

    actual = create_tasks.get_task_creation_info_list_from_csv(csv_file, common_metadata={"priority": 1})

    assert actual == [
        create_tasks.TaskCreationInfo(
            task_id="task_001",
            input_data_id_list=["input_data_001", "input_data_002"],
            metadata={"priority": 1},
        ),
        create_tasks.TaskCreationInfo(
            task_id="task_002",
            input_data_id_list=["input_data_003"],
            metadata={"priority": 1},
        ),
    ]


def test_get_task_creation_info_list_from_csv_with_missing_column(tmp_path: Path) -> None:
    csv_file = tmp_path / "task.csv"
    csv_file.write_text("task_id\nfoo\n", encoding="utf-8")

    with pytest.raises(ValueError):
        create_tasks.get_task_creation_info_list_from_csv(csv_file)


def test_get_task_relation_dict_from_headerless_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "task.csv"
    csv_file.write_text("task_001,input_data_001\ntask_001,input_data_002\n", encoding="utf-8")

    actual = put_tasks.get_task_relation_dict(csv_file)

    assert actual == {
        "task_001": ["input_data_001", "input_data_002"],
    }


def test_get_task_creation_info_list_from_csv_with_common_user_id(tmp_path: Path) -> None:
    csv_file = tmp_path / "task.csv"
    csv_file.write_text(
        "input_data_id,task_id\ninput_data_001,task_001\ninput_data_002,task_001\n",
        encoding="utf-8",
    )

    actual = create_tasks.get_task_creation_info_list_from_csv(csv_file, common_user_id="alice")

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


def test_get_metadata_from_json_args_with_null_value() -> None:
    actual = create_tasks.get_metadata_from_json_args('{"foo": null}')

    assert actual == {"foo": None}


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


def test_get_task_creation_info_list_from_json_args_with_null_metadata_value() -> None:
    actual = create_tasks.get_task_creation_info_list_from_json_args('[{"task_id": "task_001", "input_data_id_list": ["input_data_001"], "metadata": {"foo": null}}]')

    assert actual == [
        create_tasks.TaskCreationInfo(
            task_id="task_001",
            input_data_id_list=["input_data_001"],
            metadata={"foo": None},
        )
    ]


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
    main_obj.project_member_repository = Mock()
    main_obj.project_member_repository.get_account_id_from_user_id.return_value = "account1"

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


def test_create_task_list_skips_existing_task() -> None:
    service = Mock()
    service.wrapper.get_task_or_none.side_effect = [
        {"task_id": "task_001"},
        None,
    ]
    main_obj = create_tasks.CreateTaskMain(service, project_id="project1", parallelism=None, all_yes=True)

    main_obj.create_task_list(
        [
            create_tasks.TaskCreationInfo(
                task_id="task_001",
                input_data_id_list=["input_data_001"],
                metadata={},
            ),
            create_tasks.TaskCreationInfo(
                task_id="task_002",
                input_data_id_list=["input_data_002"],
                metadata={},
            ),
        ]
    )

    service.api.put_task.assert_called_once_with("project1", "task_002", request_body={"input_data_id_list": ["input_data_002"]})


def test_create_task_list_cancelled_by_confirm() -> None:
    service = Mock()
    main_obj = CreateTaskMainWithoutConfirm(service, project_id="project1", parallelism=None)

    main_obj.create_task_list(
        [
            create_tasks.TaskCreationInfo(
                task_id="task_001",
                input_data_id_list=["input_data_001"],
                metadata={},
            ),
        ]
    )

    service.api.put_task.assert_not_called()


def test_validate_with_parallelism_without_yes() -> None:
    args = argparse.Namespace(parallelism=2, yes=False)

    assert create_tasks.CreateTask.validate(args) is False


def test_validate_with_parallelism_and_yes() -> None:
    args = argparse.Namespace(parallelism=2, yes=True)

    assert create_tasks.CreateTask.validate(args) is True
