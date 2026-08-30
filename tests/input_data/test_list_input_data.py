import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from annofabcli.input_data.list_all_input_data import ListInputDataWithJsonMain
from annofabcli.input_data.list_input_data import ListInputDataMain


def test_get_input_data_from_input_data_id() -> None:
    service = Mock()
    service.api.get_input_data_in_bulk.side_effect = [
        ({"success": [{"input_data_id": "input1"}], "failure": [{"input_data_id": "input2"}]}, Mock()),
        ({"success": [], "failure": []}, Mock()),
    ]
    main_obj = ListInputDataMain(service, project_id="project1")

    result = main_obj.get_input_data_from_input_data_id([f"input{i}" for i in range(1, 102)])

    assert result == [{"input_data_id": "input1"}]
    assert service.api.get_input_data_in_bulk.call_args_list == [
        (("project1",), {"query_params": {"input_data_id": ",".join(f"input{i}" for i in range(1, 101))}}),
        (("project1",), {"query_params": {"input_data_id": "input101"}}),
    ]


def test_list_all_fetches_input_data_in_bulk_when_downloading_input_data_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_data_json = tmp_path / "input_data.json"
    input_data_json.write_text(
        json.dumps(
            [
                {
                    "input_data_id": "input1",
                    "project_id": "project1",
                    "organization_id": "organization1",
                    "input_data_set_id": "input_data_set1",
                    "input_data_name": "input1.jpg",
                    "input_data_path": "s3://bucket/input1.jpg",
                    "url": None,
                    "etag": None,
                    "original_input_data_path": None,
                    "updated_datetime": "2026-01-01T00:00:00+09:00",
                    "sign_required": False,
                    "metadata": {},
                    "system_metadata": {},
                }
            ]
        ),
        encoding="utf-8",
    )
    downloading_file = Mock()
    downloading_file.download_input_data_json_to_dir.return_value = input_data_json
    monkeypatch.setattr("annofabcli.input_data.list_all_input_data.DownloadingFile", Mock(return_value=downloading_file))
    service = Mock()
    service.api.get_input_data_in_bulk.return_value = ({"success": [{"input_data_id": "input1", "url": "https://example.com"}], "failure": []}, Mock())
    main_obj = ListInputDataWithJsonMain(service)

    result = main_obj.get_input_data_list(project_id="project1", input_data_json=None)

    assert result == [{"input_data_id": "input1"}]
    service.api.get_input_data_in_bulk.assert_called_once_with("project1", query_params={"input_data_id": "input1"})
