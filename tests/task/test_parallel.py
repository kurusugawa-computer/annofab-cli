import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from threading import Barrier

import annofabapi
import pytest

from annofabcli.task._parallel import isolate_thread_call


def test_api_clients_and_partial_arguments_are_isolated_and_logs_are_preserved(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    service = annofabapi.build(pat="test")
    barrier = Barrier(2)
    client_ids: list[int] = []
    body: dict[str, dict[str, list[str]]] = {"metadata": {"tasks": []}}

    def put_task(api, _project_id, task_id, *, request_body):
        assert request_body["metadata"]["tasks"] == []
        request_body["metadata"]["tasks"].append(task_id)
        client_ids.append(id(api))
        barrier.wait(timeout=10)
        logging.getLogger("annofabcli.task").info("task_id='%s'を処理しました。", task_id)
        return {"task_id": task_id}, None

    monkeypatch.setattr(type(service.api), "put_task", put_task)
    func = partial(service.api.put_task, "project1", request_body=body)

    with caplog.at_level(logging.INFO), ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(isolate_thread_call(func), ["first", "second"]))

    assert [body for body, _response in results] == [{"task_id": "first"}, {"task_id": "second"}]
    assert len(set(client_ids)) == 2
    assert id(service.api) not in client_ids
    assert body == {"metadata": {"tasks": []}}
    assert "task_id='first'" in caplog.text
    assert "task_id='second'" in caplog.text


def test_mutable_inputs_are_isolated_and_errors_are_reported() -> None:
    shared_input = ["initial"]
    barrier = Barrier(2)

    def process(values: list[str]) -> list[str]:
        values.append("processed")
        barrier.wait(timeout=10)
        return values

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(isolate_thread_call(process), [shared_input, shared_input]))

    assert shared_input == ["initial"]
    assert results == [["initial", "processed"], ["initial", "processed"]]

    def fail(_value: str) -> None:
        raise RuntimeError("task failure")

    with ThreadPoolExecutor(max_workers=2) as executor, pytest.raises(RuntimeError):
        list(executor.map(isolate_thread_call(fail), ["task1"]))
