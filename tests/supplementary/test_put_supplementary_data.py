import argparse
import logging

import pytest

from annofabcli.supplementary.put_supplementary_data import CliSupplementaryData, PutSupplementaryData, convert_supplementary_data_name_to_supplementary_data_id


def test__convert_supplementary_data_name_to_supplementary_data_id():
    assert convert_supplementary_data_name_to_supplementary_data_id("a/b/c.png") == "a__b__c.png"
    assert convert_supplementary_data_name_to_supplementary_data_id("s3://foo.png") == "s3______foo.png"
    assert convert_supplementary_data_name_to_supplementary_data_id("あ.png") == "__.png"


@pytest.mark.parametrize("supplementary_thread_service", ["read", "write"], indirect=True)
def test_thread_registration_preserves_counts_and_worker_logs(supplementary_thread_service, caplog: pytest.LogCaptureFixture) -> None:
    service, facade, created_input_ids = supplementary_thread_service
    command = PutSupplementaryData(service, facade, argparse.Namespace(yes=True))
    supplementary_data = [
        CliSupplementaryData(input_data_id=input_data_id, supplementary_data_name="data", supplementary_data_path="https://example.com/data.jpg")
        for input_data_id in ["failed", "input1", "input2", "missing"]
    ]

    with caplog.at_level(logging.DEBUG):
        command.put_supplementary_data_list("project1", supplementary_data, parallelism=2)

    assert sorted(created_input_ids) == ["input1", "input2"]
    assert "2 / 4 件の補助情報を登録しました" in caplog.messages[-1]
    assert any(record.levelno == logging.WARNING and record.exc_info for record in caplog.records)
    assert any(record.levelno == logging.DEBUG and "補助情報を登録しました" in record.message for record in caplog.records)
