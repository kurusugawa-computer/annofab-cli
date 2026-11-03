import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from threading import Barrier, Lock

import annofabapi
import pytest

from annofabcli.input_data._parallel import isolate_thread_call


def test_api_clients_and_partial_arguments_are_isolated_and_logs_are_preserved(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    service = annofabapi.build(pat="test")
    barrier = Barrier(2)
    client_ids: list[int] = []
    body: dict[str, dict[str, list[str]]] = {"metadata": {"inputs": []}}

    def put_input_data(api, _project_id, input_data_id, *, request_body):
        assert request_body["metadata"]["inputs"] == []
        request_body["metadata"]["inputs"].append(input_data_id)
        client_ids.append(id(api))
        barrier.wait(timeout=10)
        logging.getLogger("annofabcli.input_data").info("input_data_id='%s'を処理しました。", input_data_id)
        return {"input_data_id": input_data_id}, None

    monkeypatch.setattr(type(service.api), "put_input_data", put_input_data)
    func = partial(service.api.put_input_data, "project1", request_body=body)

    with caplog.at_level(logging.INFO), ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(isolate_thread_call(func, get_input_data_id=lambda item: item), ["first", "second"]))

    assert [body for body, _response in results] == [{"input_data_id": "first"}, {"input_data_id": "second"}]
    assert len(set(client_ids)) == 2
    assert id(service.api) not in client_ids
    assert body == {"metadata": {"inputs": []}}
    assert "input_data_id='first'" in caplog.text
    assert "input_data_id='second'" in caplog.text


def test_mutable_inputs_are_isolated_and_errors_are_reported() -> None:
    shared_input = ["initial"]
    barrier = Barrier(2)

    def process(values: list[str]) -> list[str]:
        values.append("processed")
        barrier.wait(timeout=10)
        return values

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(isolate_thread_call(process, get_input_data_id=lambda _item: ""), [shared_input, shared_input]))

    assert shared_input == ["initial"]
    assert results == [["initial", "processed"], ["initial", "processed"]]

    def fail(_value: str) -> None:
        raise RuntimeError("input data failure")

    with ThreadPoolExecutor(max_workers=2) as executor, pytest.raises(RuntimeError):
        list(executor.map(isolate_thread_call(fail, get_input_data_id=lambda item: item), ["input1"]))


def test_only_target_bulk_records_are_copied() -> None:
    input_data: dict[str, dict[str, list[str]]] = {"first": {"metadata": []}, "second": {"metadata": []}}
    supplementary_data = {"first": [{"name": "first"}], "second": [{"name": "second"}]}
    # コピー不能な値を含む別IDのレコードを参照・複製しないことを確認する。
    other_record = {"unused": Lock()}
    bulk_data = {**input_data, "unused": other_record}

    def process(input_data_id, *, existing_input_data_dict, src_supplementary_data_dict):
        expected_ids = {input_data_id} if input_data_id in input_data else set()
        assert existing_input_data_dict.keys() == expected_ids
        assert src_supplementary_data_dict.keys() == expected_ids
        if expected_ids:
            existing_input_data_dict[input_data_id]["metadata"].append("changed")
            src_supplementary_data_dict[input_data_id][0]["name"] = "changed"
        return input_data_id

    worker = isolate_thread_call(
        process,
        get_input_data_id=lambda item: item,
        existing_input_data_dict=bulk_data,
        src_supplementary_data_dict=supplementary_data,
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(worker, ["first", "second", "missing"])) == ["first", "second", "missing"]

    assert input_data == {"first": {"metadata": []}, "second": {"metadata": []}}
    assert supplementary_data == {"first": [{"name": "first"}], "second": [{"name": "second"}]}
