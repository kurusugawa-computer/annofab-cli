from __future__ import annotations

import argparse
import json
import logging
import threading
from unittest.mock import Mock

import pytest
import requests

from annofabcli.annotation.delete_annotation_per_annotation import DeleteAnnotationPerAnnotation, DeleteAnnotationPerAnnotationMain, DeletedAnnotationInfo
from annofabcli.common.exceptions import AnnofabCliException, ProjectAuthorizationError
from annofabcli.common.facade import AnnofabApiFacade


@pytest.fixture
def service():
    service = Mock()
    service.api.get_project.return_value = ({"title": "project"}, None)
    service.api.get_my_member_in_project.return_value = ({"member_role": "owner"}, None)
    service.wrapper.get_task_or_none.return_value = {"status": "not_started"}

    def get_annotation(_project_id, *, task_id, input_data_id, query_params):
        assert query_params == {"v": "2"}
        return {
            "project_id": "project1",
            "task_id": task_id,
            "input_data_id": input_data_id,
            "format_version": "2.0.0",
            "updated_datetime": "2026-01-01T00:00:00Z",
            "details": [{"annotation_id": annotation_id, "label_id": "label1", "body": {"_type": "Classification"}} for annotation_id in ["a1", "a2", "keep"]],
        }

    service.wrapper.get_editor_annotation_or_none.side_effect = get_annotation
    return service


def target(task_id: str = "task1", input_data_id: str = "input1", annotation_id: str = "a1") -> DeletedAnnotationInfo:
    return DeletedAnnotationInfo(task_id=task_id, input_data_id=input_data_id, annotation_id=annotation_id)


def command(service: Mock, *, include_complete_task: bool = False, all_yes: bool = True) -> DeleteAnnotationPerAnnotationMain:
    return DeleteAnnotationPerAnnotationMain(service, "project1", include_complete_task=include_complete_task, all_yes=all_yes)


@pytest.mark.parametrize("parallelism", [None, 2])
@pytest.mark.parametrize("with_backup", [False, True])
def test_deletes_only_selected_annotations_with_backups_and_worker_logs(service, tmp_path, caplog, parallelism, with_backup):
    barrier = threading.Barrier(2)
    main_thread_id = threading.get_ident()
    deleted = []
    backup_dir = tmp_path / "backup" if with_backup else None

    def delete_annotations(project_id, *, request_body, query_params):
        assert project_id == "project1"
        assert query_params == {"v": "2"}
        task_id = request_body[0]["task_id"]
        input_data_id = request_body[0]["input_data_id"]
        assert {item["annotation_id"] for item in request_body} == {"a1", "a2"}
        assert all(item["_type"] == "Delete" and item["updated_datetime"] == "2026-01-01T00:00:00Z" for item in request_body)
        if parallelism is not None:
            assert threading.get_ident() != main_thread_id
            if input_data_id == "input1":
                barrier.wait(timeout=10)
        if backup_dir is not None:
            backup = json.loads((backup_dir / task_id / f"{input_data_id}.json").read_text())
            assert [detail["annotation_id"] for detail in backup["details"]] == ["a1", "a2", "keep"]
            assert backup["task_id"] == task_id
        deleted.append((task_id, input_data_id))

    service.api.batch_update_annotations.side_effect = delete_annotations
    items = [target(task_id, input_id, annotation_id) for task_id in ["task1", "task2"] for input_id in ["input1", "input2"] for annotation_id in ["a1", "a2"]]
    items.append(items[0])
    with caplog.at_level(logging.INFO):
        command(service).delete_annotation_by_id_list(items, backup_dir, parallelism=parallelism)

    assert sorted(deleted) == [("task1", "input1"), ("task1", "input2"), ("task2", "input1"), ("task2", "input2")]
    for task_id in ["task1", "task2"]:
        assert [input_id for task, input_id in deleted if task == task_id] == ["input1", "input2"]
    assert "8/8" in caplog.messages[-1]
    assert "0 件" in caplog.messages[-1]
    assert not any(record.levelno >= logging.WARNING for record in caplog.records)
    if parallelism is not None:
        assert any(record.thread != main_thread_id and "削除しました" in record.message for record in caplog.records)


@pytest.mark.parametrize("parallelism", [None, 2])
@pytest.mark.parametrize("failure_stage", ["task", "input", "backup"])
def test_failure_does_not_stop_other_tasks_or_lose_completed_counts(service, tmp_path, caplog, parallelism, failure_stage):
    backup_dir = tmp_path / "backup"
    if failure_stage == "task":

        def get_task(_project_id, task_id):
            if task_id == "task1":
                raise RuntimeError("タスク取得に失敗")
            return {"status": "not_started"}

        service.wrapper.get_task_or_none.side_effect = get_task
    elif failure_stage == "input":
        get_annotation = service.wrapper.get_editor_annotation_or_none.side_effect

        def get_or_fail(project_id, *, task_id, input_data_id, query_params):
            if task_id == "task1" and input_data_id == "input2":
                raise RuntimeError("アノテーション取得に失敗")
            return get_annotation(project_id, task_id=task_id, input_data_id=input_data_id, query_params=query_params)

        service.wrapper.get_editor_annotation_or_none.side_effect = get_or_fail
    else:
        # ディレクトリの代わりにファイルを置き、実際の保存処理を失敗させる。
        backup_dir.mkdir()
        (backup_dir / "task1").write_text("blocked")

    items = [target("task1", "input1"), target("task1", "input2"), target("task2", "input1")]
    with caplog.at_level(logging.INFO), pytest.raises(AnnofabCliException):
        command(service).delete_annotation_by_id_list(items, backup_dir, parallelism=parallelism)

    deleted = {(call.kwargs["request_body"][0]["task_id"], call.kwargs["request_body"][0]["input_data_id"]) for call in service.api.batch_update_annotations.call_args_list}
    assert deleted == ({("task1", "input1"), ("task2", "input1")} if failure_stage == "input" else {("task2", "input1")})
    assert ("2/3" if failure_stage == "input" else "1/3") in caplog.messages[-1]
    assert any(record.levelno == logging.WARNING and record.exc_info for record in caplog.records)


def test_http_failure_recounts_partial_deletion_and_keeps_other_inputs(service, caplog):
    def delete_annotations(_project_id, *, request_body, query_params):
        assert query_params == {"v": "2"}
        if request_body[0]["input_data_id"] == "input1":
            raise requests.HTTPError("一部の削除に失敗")

    service.api.batch_update_annotations.side_effect = delete_annotations
    service.api.get_editor_annotation.return_value = ({"details": [{"annotation_id": "a2"}, {"annotation_id": "keep"}]}, None)
    items = [target(annotation_id="a1"), target(annotation_id="a2"), target(annotation_id="missing"), target(input_data_id="input2")]

    with caplog.at_level(logging.INFO), pytest.raises(AnnofabCliException):
        command(service).delete_annotation_by_id_list(items, parallelism=2)

    assert "2/4" in caplog.messages[-1]
    assert "2 件" in caplog.messages[-1]
    assert service.api.batch_update_annotations.call_count == 2
    assert all(item["annotation_id"] != "missing" for call in service.api.batch_update_annotations.call_args_list for item in call.kwargs["request_body"])


@pytest.mark.parametrize("status,include_complete,expected", [(None, False, False), ("working", True, False), ("complete", False, False), ("complete", True, True)])
def test_task_state_controls_deletion(service, status, include_complete, expected):
    service.wrapper.get_task_or_none.return_value = {"status": status} if status is not None else None
    command(service, include_complete_task=include_complete).delete_annotation_by_id_list([target()], parallelism=2)
    assert bool(service.api.batch_update_annotations.call_count) == expected


def test_missing_inputs_and_annotations_do_not_delete_other_annotations(service, caplog):
    service.wrapper.get_editor_annotation_or_none.side_effect = [None, {"task_id": "task1", "input_data_id": "input2", "details": [{"annotation_id": "keep"}]}]
    with caplog.at_level(logging.INFO):
        command(service).delete_annotation_by_id_list([target(), target(input_data_id="input2")], parallelism=2)
    service.api.batch_update_annotations.assert_not_called()
    assert "0/2" in caplog.messages[-1]


def test_cancelled_confirmation_does_not_delete_or_backup(service, tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _message: "n")
    backup_dir = tmp_path / "backup"
    command(service, all_yes=False).delete_annotation_by_id_list([target()], backup_dir)
    service.api.batch_update_annotations.assert_not_called()
    assert not backup_dir.exists()


@pytest.mark.parametrize("input_format", ["json", "json_file", "csv"])
def test_command_reads_ids_and_deletes_with_real_backup(service, tmp_path, input_format):
    args = argparse.Namespace(project_id="project1", json=None, csv=None, backup=tmp_path / "backup", include_complete_task=False, yes=True, parallelism=2)
    if input_format == "csv":
        args.csv = tmp_path / "input.csv"
        args.csv.write_text("task_id,input_data_id,annotation_id,extra\ntask1,input1,a1,ignored\n")
    else:
        value = json.dumps([{"task_id": "task1", "input_data_id": "input1", "annotation_id": "a1"}])
        if input_format == "json_file":
            path = tmp_path / "input.json"
            path.write_text(value)
            args.json = f"file://{path}"
        else:
            args.json = value
    DeleteAnnotationPerAnnotation(service, AnnofabApiFacade(service), args).main()
    assert service.api.batch_update_annotations.call_args.kwargs["request_body"][0]["annotation_id"] == "a1"
    assert (args.backup / "task1/input1.json").is_file()


@pytest.mark.parametrize("input_format", ["json", "csv"])
def test_invalid_ids_are_rejected_before_any_deletion(service, tmp_path, input_format):
    args = argparse.Namespace(project_id="project1", json=None, csv=None, backup=tmp_path / "backup", include_complete_task=False, yes=True, parallelism=2)
    if input_format == "json":
        args.json = '[{"task_id":"task1","input_data_id":"input1","annotation_id":"a1"},{"task_id":"task2","input_data_id":"input2"}]'
    else:
        args.csv = tmp_path / "input.csv"
        args.csv.write_text("task_id,input_data_id,annotation_id\ntask1,input1,a1\ntask2,input2,\n")
    with pytest.raises(AnnofabCliException):
        DeleteAnnotationPerAnnotation(service, AnnofabApiFacade(service), args).main()
    service.api.batch_update_annotations.assert_not_called()


def test_parallelism_requires_yes_before_any_deletion(service):
    args = argparse.Namespace(parallelism=2, yes=False)
    with pytest.raises(AnnofabCliException):
        DeleteAnnotationPerAnnotation(service, AnnofabApiFacade(service), args).main()
    service.api.batch_update_annotations.assert_not_called()


def test_complete_tasks_require_owner_role(service, tmp_path):
    service.api.get_my_member_in_project.return_value = ({"member_role": "accepter"}, None)
    args = argparse.Namespace(project_id="project1", json='[{"task_id":"task1","input_data_id":"input1","annotation_id":"a1"}]', backup=tmp_path, include_complete_task=True, yes=True, parallelism=2)
    with pytest.raises(ProjectAuthorizationError):
        DeleteAnnotationPerAnnotation(service, AnnofabApiFacade(service), args).main()
    service.api.batch_update_annotations.assert_not_called()
