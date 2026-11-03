import argparse
import logging

import pytest

from annofabcli.supplementary.create_supplementary_data import CliSupplementaryData, CreateSupplementaryData, read_supplementary_data_csv


def test__common_message():
    assert CreateSupplementaryData.COMMON_MESSAGE == "annofabcli supplementary create: error:"


def test_log_progress(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        CreateSupplementaryData.log_progress(99, 100)
        CreateSupplementaryData.log_progress(100, 100)

    assert "100 / 100 件の補助情報を処理しました。" in caplog.messages


def test__read_supplementary_data_csv__header_exists(tmp_path):
    csv_path = tmp_path / "supplementary_data.csv"
    csv_path.write_text(
        "input_data_id,supplementary_data_name,supplementary_data_path,supplementary_data_id,supplementary_data_type,supplementary_data_number\ninput1,data1,file://data1.jpg,id1,image,1\n"
    )

    df = read_supplementary_data_csv(csv_path)

    assert df.to_dict("records") == [
        {
            "input_data_id": "input1",
            "supplementary_data_name": "data1",
            "supplementary_data_path": "file://data1.jpg",
            "supplementary_data_id": "id1",
            "supplementary_data_type": "image",
            "supplementary_data_number": 1,
        }
    ]


def test__read_supplementary_data_csv__header_not_exists(tmp_path):
    csv_path = tmp_path / "supplementary_data.csv"
    csv_path.write_text("input1,data1,file://data1.jpg,id1,image,1\n")

    with pytest.raises(ValueError):
        read_supplementary_data_csv(csv_path)


def test__get_supplementary_data_list_from_csv__supplementary_data_number_is_optional(tmp_path):
    csv_path = tmp_path / "supplementary_data.csv"
    csv_path.write_text("input_data_id,supplementary_data_name,supplementary_data_path\ninput1,data1,file://data1.jpg\n")

    supplementary_data_list = CreateSupplementaryData.get_supplementary_data_list_from_csv(csv_path)

    assert supplementary_data_list[0].supplementary_data_number is None


def test__get_supplementary_data_list_from_csv__empty_supplementary_data_number(tmp_path):
    csv_path = tmp_path / "supplementary_data.csv"
    csv_path.write_text("input_data_id,supplementary_data_name,supplementary_data_path,supplementary_data_number\ninput1,data1,file://data1.jpg,\n")

    supplementary_data_list = CreateSupplementaryData.get_supplementary_data_list_from_csv(csv_path)

    assert supplementary_data_list[0].supplementary_data_number is None


@pytest.mark.parametrize("supplementary_thread_service", ["read", "write"], indirect=True)
def test_thread_creation_preserves_counts_progress_and_worker_logs(supplementary_thread_service, caplog: pytest.LogCaptureFixture) -> None:
    service, facade, created_input_ids = supplementary_thread_service
    command = CreateSupplementaryData(service, facade, argparse.Namespace(yes=True))
    supplementary_data = [
        CliSupplementaryData(input_data_id=input_data_id, supplementary_data_name="data", supplementary_data_path="https://example.com/data.jpg")
        for input_data_id in ["failed", "input1", "input2", "missing"]
    ]

    with caplog.at_level(logging.DEBUG):
        command.create_supplementary_data_list("project1", supplementary_data, parallelism=2)

    assert sorted(created_input_ids) == ["input1", "input2"]
    assert "2 / 4 件の補助情報を作成しました" in caplog.messages[-1]
    assert "4 / 4 件の補助情報を処理しました。" in caplog.messages
    assert any(record.levelno == logging.WARNING and record.exc_info for record in caplog.records)
    assert any(record.levelno == logging.DEBUG and "補助情報を作成しました" in record.message for record in caplog.records)
