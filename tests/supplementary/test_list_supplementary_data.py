import logging
from unittest.mock import Mock

import pytest

from annofabcli.supplementary.list_supplementary_data import ListSupplementaryDataMain


def test_get_all_supplementary_data_list(caplog: pytest.LogCaptureFixture) -> None:
    service = Mock()
    service.api.get_supplementary_data_in_bulk.side_effect = [
        (
            {
                "success": [
                    {
                        "input_data_id": "input1",
                        "supplementary_data_id": "supplementary1",
                        "url": "https://example.com",
                        "etag": "etag1",
                    }
                ],
                "failure": [{"input_data_id": "input2"}],
            },
            Mock(),
        ),
        ({"success": [], "failure": []}, Mock()),
    ]
    main_obj = ListSupplementaryDataMain(service, project_id="project1")

    with caplog.at_level(logging.INFO):
        result = main_obj.get_all_supplementary_data_list([f"input{i}" for i in range(1, 102)])

    assert result == [{"input_data_id": "input1", "supplementary_data_id": "supplementary1"}]
    assert "100 / 101 件の入力データに紐づく補助情報を取得しました。" in caplog.messages
    assert "補助情報の取得が完了しました。取得件数: 1 件, 失敗した入力データ数: 1 件" in caplog.messages
    assert service.api.get_supplementary_data_in_bulk.call_args_list == [
        (("project1",), {"query_params": {"input_data_id": ",".join(f"input{i}" for i in range(1, 101))}}),
        (("project1",), {"query_params": {"input_data_id": "input101"}}),
    ]


def test_get_all_supplementary_data_list_when_bulk_request_fails(caplog: pytest.LogCaptureFixture) -> None:
    service = Mock()
    service.api.get_supplementary_data_in_bulk.side_effect = RuntimeError()
    main_obj = ListSupplementaryDataMain(service, project_id="project1")

    with caplog.at_level(logging.INFO):
        result = main_obj.get_all_supplementary_data_list([f"input{i}" for i in range(1, 101)])

    assert result == []
    assert "入力データ 1〜100 件（100件）の補助情報バルク取得に失敗しました。" in caplog.messages
    assert "補助情報の取得が完了しました。取得件数: 0 件, 失敗した入力データ数: 100 件" in caplog.messages
