import logging
from threading import Barrier, Lock
from unittest.mock import Mock

import pytest

from annofabcli.task.create_tasks import CreateTaskMain, TaskCreationInfo
from annofabcli.task.put_tasks import PuttingTaskMain
from annofabcli.task.update_input_data import TaskInputDataUpdateInfo, UpdateResult, UpdateTaskInputDataMain
from annofabcli.task.update_metadata_of_task import UpdateMetadataOfTaskMain
from annofabcli.task.update_metadata_per_task import UpdateMetadataOfTaskMain as UpdateMetadataPerTaskMain


@pytest.mark.parametrize("main_class", [UpdateMetadataOfTaskMain, UpdateMetadataPerTaskMain])
def test_metadata_overwrite_processes_all_batches_and_reports_errors(main_class) -> None:
    service = Mock()
    barrier = Barrier(2)
    requests: list[dict] = []

    def patch_metadata(_project_id, *, request_body):
        requests.append(request_body)
        barrier.wait(timeout=10)
        if "task0" in request_body:
            raise RuntimeError("metadata API failure")
        return {}, None

    service.api.patch_tasks_metadata.side_effect = patch_metadata
    metadata = {f"task{index}": {"priority": index} for index in range(501)}
    main_obj = main_class(service, is_overwrite_metadata=True, parallelism=2, all_yes=True)

    with pytest.raises(RuntimeError):
        main_obj.update_metadata_of_task("project1", metadata)

    assert sorted(len(request) for request in requests) == [1, 500]
    assert {key: value for request in requests for key, value in request.items()} == metadata


@pytest.mark.parametrize("operation", ["create", "put", "update_input_data"])
def test_batched_task_updates_preserve_order_isolation_and_failure_summary(operation: str, caplog: pytest.LogCaptureFixture) -> None:
    service = Mock()
    barrier = Barrier(2)
    bulk_requests: list[list[str]] = []
    updates: list[str] = []
    lock = Lock()
    existing_tasks = {f"task{index}": {"task_id": f"task{index}", "input_data_id_list": ["old"], "metadata": {"priority": index}} for index in range(101)}

    def get_tasks(_project_id, *, query_params):
        task_ids = query_params["task_id"].split(",")
        bulk_requests.append(task_ids)
        tasks = [existing_tasks[task_id] for task_id in task_ids] if operation == "update_input_data" else []
        return {"success": tasks, "failure": []}, None

    def put_task(_project_id, task_id, *, request_body):
        if task_id in {"task0", "task1"}:
            barrier.wait(timeout=10)
        assert request_body["input_data_id_list"] == ["old", "new"]
        # API境界で変更しても、入力やバルク取得結果を変更しない。
        request_body["input_data_id_list"].append("server")
        if "metadata" in request_body:
            request_body["metadata"]["server"] = "value"
        if task_id == "task0":
            raise RuntimeError("task API failure")
        with lock:
            updates.append(task_id)
        return {}, None

    service.api.get_tasks_in_bulk.side_effect = get_tasks
    service.api.put_task.side_effect = put_task
    with caplog.at_level(logging.INFO):
        if operation == "create":
            creation_info = [TaskCreationInfo(task_id=f"task{index}", input_data_id_list=["old", "new"], metadata={"priority": index}) for index in range(101)]
            CreateTaskMain(service, project_id="project1", parallelism=2, all_yes=True).create_task_list(creation_info)
            assert all(info.input_data_id_list == ["old", "new"] and "server" not in info.metadata for info in creation_info)
        elif operation == "put":
            relations = {f"task{index}": ["old", "new"] for index in range(101)}
            PuttingTaskMain(service, project_id="project1", parallelism=2).put_task_list(relations)
            assert all(values == ["old", "new"] for values in relations.values())
        else:
            update_info = [TaskInputDataUpdateInfo(task_id=f"task{index}", input_data_id_list=["old", "new"]) for index in range(101)]
            result = UpdateTaskInputDataMain(service, project_id="project1", parallelism=2, all_yes=True).update_task_input_data_list(update_info)
            assert result[UpdateResult.UPDATED] == 100
            assert result[UpdateResult.FAILED] == 1
            assert all(info.input_data_id_list == ["old", "new"] for info in update_info)

    assert len(updates) == 100
    assert "task0" not in updates
    assert bulk_requests == [[f"task{index}" for index in range(100)], ["task100"]]
    assert all(task["metadata"] == {"priority": index} for index, task in enumerate(existing_tasks.values()))
    assert "100 / 101" in caplog.text


@pytest.mark.parametrize("main_class", [UpdateMetadataOfTaskMain, UpdateMetadataPerTaskMain])
def test_thread_metadata_append_keeps_existing_values_and_counts_failures(main_class, caplog: pytest.LogCaptureFixture) -> None:
    service = Mock()
    barrier = Barrier(2)
    requests: list[dict] = []
    metadata = {"task0": {"priority": 0}, "task1": {"priority": 1}}

    def get_task(_project_id, task_id):
        barrier.wait(timeout=10)
        return {"task_id": task_id, "metadata": {"existing": True}}

    def patch_metadata(_project_id, *, request_body):
        requests.append(request_body)
        if "task0" in request_body:
            raise RuntimeError("metadata API failure")
        return {}, None

    service.wrapper.get_task_or_none.side_effect = get_task
    service.api.patch_tasks_metadata.side_effect = patch_metadata
    main_obj = main_class(service, is_overwrite_metadata=False, parallelism=2, all_yes=True)

    with caplog.at_level(logging.INFO):
        main_obj.update_metadata_of_task("project1", metadata)

    assert {key: value for request in requests for key, value in request.items()} == {"task0": {"existing": True, "priority": 0}, "task1": {"existing": True, "priority": 1}}
    assert "1 / 2" in caplog.text
    assert any(record.levelno == logging.WARNING and record.exc_info for record in caplog.records)
