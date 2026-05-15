from pathlib import Path

import pytest

from annofabcli.input_data import create_input_data

test_dir = Path("./tests/data/input_data")


def test_get_input_data_list_from_csv() -> None:
    csv_path = test_dir / "input_data_with_header.csv"
    df = create_input_data.read_input_data_csv(csv_path)
    actual_members = create_input_data.CreateInputData.get_input_data_list_from_df(df)

    assert actual_members[0] == create_input_data.CsvInputData(
        input_data_name="data1",
        input_data_path="s3://example.com/data1",
        input_data_id="id1",
    )
    assert actual_members[1] == create_input_data.CsvInputData(
        input_data_name="data2",
        input_data_path="s3://example.com/data2",
        input_data_id="id2",
    )
    assert actual_members[2] == create_input_data.CsvInputData(
        input_data_name="data3",
        input_data_path="s3://example.com/data3",
        input_data_id=None,
    )


def test_read_input_data_csv_with_missing_required_column(tmp_path: Path) -> None:
    csv_file = tmp_path / "input_data.csv"
    csv_file.write_text("input_data_name\nfoo\n", encoding="utf-8")

    with pytest.raises(ValueError):
        create_input_data.read_input_data_csv(csv_file)


def test_validate_no_duplicated_final_input_data_id_with_generated_input_data_id() -> None:
    input_data_list = [
        create_input_data.CsvInputData(input_data_name="a/b", input_data_path="s3://example.com/data1"),
        create_input_data.CsvInputData(input_data_name="a__b", input_data_path="s3://example.com/data2"),
    ]

    with pytest.raises(ValueError):
        create_input_data.validate_no_duplicated_final_input_data_id(input_data_list)
