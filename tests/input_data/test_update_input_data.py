import logging
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import annofabapi
import pytest

from annofabcli.input_data.update_input_data import UpdatedInputData, UpdateInputDataMain, UpdateResult


def create_old_input_data() -> dict[str, str]:
    return {
        "input_data_id": "input1",
        "input_data_name": "old_name",
        "input_data_path": "s3://bucket/old_image.jpg",
        "updated_datetime": "2026-01-01T00:00:00.000+09:00",
    }


def create_service() -> tuple[annofabapi.Resource, Mock, Mock]:
    api = Mock()
    wrapper = Mock()
    wrapper.get_input_data_or_none.return_value = create_old_input_data()
    service = cast(annofabapi.Resource, SimpleNamespace(api=api, wrapper=wrapper))
    return service, api, wrapper


def test_update_input_data_with_url_path() -> None:
    service, api, wrapper = create_service()
    main_obj = UpdateInputDataMain(service, all_yes=True)

    result = main_obj.update_input_data("project1", "input1", new_input_data_path="s3://bucket/new_image.jpg")

    assert result == UpdateResult.SUCCESS
    api.put_input_data.assert_called_once_with(
        "project1",
        "input1",
        request_body={
            "input_data_id": "input1",
            "input_data_name": "old_name",
            "input_data_path": "s3://bucket/new_image.jpg",
            "updated_datetime": "2026-01-01T00:00:00.000+09:00",
            "last_updated_datetime": "2026-01-01T00:00:00.000+09:00",
        },
    )
    wrapper.put_input_data_from_file.assert_not_called()


def test_update_input_data_with_file_scheme_path(tmp_path: Path) -> None:
    input_data_file = tmp_path / "new_image.jpg"
    input_data_file.write_bytes(b"image")
    service, api, wrapper = create_service()
    main_obj = UpdateInputDataMain(service, all_yes=True)

    result = main_obj.update_input_data("project1", "input1", new_input_data_name="new_name", new_input_data_path=f"file://{input_data_file}")

    assert result == UpdateResult.SUCCESS
    wrapper.put_input_data_from_file.assert_called_once_with(
        "project1",
        input_data_id="input1",
        file_path=str(input_data_file),
        request_body={
            "input_data_id": "input1",
            "input_data_name": "new_name",
            "input_data_path": "s3://bucket/old_image.jpg",
            "updated_datetime": "2026-01-01T00:00:00.000+09:00",
            "last_updated_datetime": "2026-01-01T00:00:00.000+09:00",
        },
    )
    api.put_input_data.assert_not_called()


def test_update_input_data_with_missing_file_scheme_path(tmp_path: Path) -> None:
    service, api, wrapper = create_service()
    main_obj = UpdateInputDataMain(service, all_yes=True)

    result = main_obj.update_input_data("project1", "input1", new_input_data_path=f"file://{tmp_path / 'missing.jpg'}")

    assert result == UpdateResult.SKIPPED
    wrapper.put_input_data_from_file.assert_not_called()
    api.put_input_data.assert_not_called()


def test_parallel_update_logs_and_counts_results(caplog: pytest.LogCaptureFixture) -> None:
    service, api, _ = create_service()
    api.get_input_data_in_bulk.return_value = (
        {"success": [dict(create_old_input_data(), input_data_id=input_data_id) for input_data_id in ["input1", "failed"]]},
        None,
    )
    main_thread_id = threading.get_ident()
    updated_ids: list[str] = []

    def put_input_data(_project_id, input_data_id, **_kwargs):
        assert threading.get_ident() != main_thread_id
        updated_ids.append(input_data_id)
        if input_data_id == "failed":
            raise RuntimeError

    api.put_input_data.side_effect = put_input_data
    command = UpdateInputDataMain(service, all_yes=True)
    with caplog.at_level(logging.DEBUG, logger="annofabcli.input_data.update_input_data"):
        command.update_input_data_list_in_parallel(
            "project1",
            [UpdatedInputData(input_data_id, input_data_name="new_name") for input_data_id in ["input1", "missing", "failed"]],
            parallelism=2,
        )

    assert sorted(updated_ids) == ["failed", "input1"]
    assert "成功: 1件, スキップ: 1件, 失敗: 1件" in caplog.text
    worker_records = [record for record in caplog.records if "件目 ::" in record.message]
    assert len(worker_records) == 3
    assert all(record.thread != main_thread_id for record in worker_records)
    assert any(record.exc_info is not None for record in worker_records)
