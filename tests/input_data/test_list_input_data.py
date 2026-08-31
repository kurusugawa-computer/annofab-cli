import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from annofabcli.input_data.list_all_input_data import ListInputDataWithJsonMain
from annofabcli.input_data.list_input_data import AddingDetailsToInputData, ListInputDataMain


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


def test_add_supplementary_data_count_to_input_data_list() -> None:
    service = Mock()
    service.api.get_supplementary_data_in_bulk.side_effect = [
        (
            {
                "success": [
                    {"input_data_id": "input1", "supplementary_data_id": "supplementary1"},
                    {"input_data_id": "input1", "supplementary_data_id": "supplementary2"},
                    {"input_data_id": "input2", "supplementary_data_id": "supplementary3"},
                ],
                "failure": [{"input_data_id": "input3"}],
            },
            Mock(),
        ),
        ({"success": [], "failure": []}, Mock()),
    ]
    input_data_list = [{"input_data_id": f"input{i}"} for i in range(1, 102)]
    main_obj = AddingDetailsToInputData(service, project_id="project1")

    result = main_obj.add_supplementary_data_count_to_input_data_list(input_data_list)

    assert result[0]["supplementary_data_count"] == 2
    assert result[1]["supplementary_data_count"] == 1
    assert result[2]["supplementary_data_count"] is None
    assert result[3]["supplementary_data_count"] == 0
    assert service.api.get_supplementary_data_in_bulk.call_args_list == [
        (("project1",), {"query_params": {"input_data_id": ",".join(f"input{i}" for i in range(1, 101))}}),
        (("project1",), {"query_params": {"input_data_id": "input101"}}),
    ]


def test_list_all_uses_downloaded_input_data_json_without_fetching_input_data_in_bulk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    main_obj = ListInputDataWithJsonMain(service)

    result = main_obj.get_input_data_list(project_id="project1", input_data_json=None)

    assert result == [
        {
            "input_data_id": "input1",
            "project_id": "project1",
            "organization_id": "organization1",
            "input_data_set_id": "input_data_set1",
            "input_data_name": "input1.jpg",
            "input_data_path": "s3://bucket/input1.jpg",
            "updated_datetime": "2026-01-01T00:00:00+09:00",
            "sign_required": False,
            "metadata": {},
            "system_metadata": {},
        }
    ]
    service.api.get_input_data_in_bulk.assert_not_called()
