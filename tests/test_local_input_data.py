import datetime
import os
import uuid
from pathlib import Path

from annofabcli.input_data.list_input_data import create_datetime_range_list
from annofabcli.input_data.put_input_data import CsvInputData, PutInputData

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

test_dir = Path('./tests/data')
out_dir = Path('./tests/out')


def is_uuid4(target: str):
    try:
        uuid.UUID(target, version=4)
        return True
    except ValueError:
        return False


def test_get_input_data_list_from_csv():
    csv_path = test_dir / "input_data.csv"
    actual_members = PutInputData.get_input_data_list_from_csv(csv_path)
    print(actual_members)
    assert actual_members[0] == CsvInputData(input_data_name="data1", input_data_path="s3://example.com/data1",
                                             input_data_id="id1", sign_required=None)
    assert actual_members[1] == CsvInputData(input_data_name="data2", input_data_path="s3://example.com/data2",
                                             input_data_id="id2", sign_required=True)
    assert actual_members[2] == CsvInputData(input_data_name="data3", input_data_path="s3://example.com/data3",
                                             input_data_id="id3", sign_required=False)

    assert is_uuid4(actual_members[3].input_data_id)


def test_create_datetime_range_list():
    first_datetime = datetime.datetime(2019, 1, 1)
    last_datetime = datetime.datetime(2019, 1, 4)

    actual = create_datetime_range_list(first_datetime=first_datetime, last_datetime=last_datetime, days=2)
    expected = [(None, datetime.datetime(2019, 1, 1)), (datetime.datetime(2019, 1, 1), datetime.datetime(2019, 1, 3)),
                (datetime.datetime(2019, 1, 3), datetime.datetime(2019, 1, 5)), (datetime.datetime(2019, 1, 5), None)]

    assert actual == expected
