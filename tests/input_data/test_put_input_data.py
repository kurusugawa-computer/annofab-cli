from pathlib import Path

from annofabcli.input_data.put_input_data import CsvInputData, PutInputData, convert_input_data_name_to_input_data_id, read_input_data_csv

test_dir = Path("./tests/data/input_data")


def test_get_input_data_list_from_csv():
    csv_path = test_dir / "input_data.csv"
    df = read_input_data_csv(csv_path)
    actual_members = PutInputData.get_input_data_list_from_df(df)
    assert actual_members[0] == CsvInputData(input_data_name="data1", input_data_path="s3://example.com/data1", input_data_id="id1")
    assert actual_members[1] == CsvInputData(input_data_name="data2", input_data_path="s3://example.com/data2", input_data_id="id2")
    assert actual_members[2] == CsvInputData(input_data_name="data3", input_data_path="s3://example.com/data3", input_data_id="id3")

    assert actual_members[3].input_data_id is None


def test__convert_input_data_name_to_input_data_id():
    assert convert_input_data_name_to_input_data_id("a/b/c.png") == "a__b__c.png"
    assert convert_input_data_name_to_input_data_id("s3://foo.png") == "s3______foo.png"
    assert convert_input_data_name_to_input_data_id("あ.png") == "__.png"
