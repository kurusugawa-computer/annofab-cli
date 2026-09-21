from collections import UserDict
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pandas
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
    assert df["input_data_id"].iloc[2] is pandas.NA


def test_read_input_data_csv_without_input_data_id_column_uses_pd_na(tmp_path: Path) -> None:
    csv_file = tmp_path / "input_data.csv"
    csv_file.write_text("input_data_name,input_data_path\nfoo,s3://example.com/foo\n", encoding="utf-8")

    actual = create_input_data.read_input_data_csv(csv_file)

    assert actual["input_data_id"].dtype == "string"
    assert actual["input_data_id"].iloc[0] is pandas.NA


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


def test_get_metadata_from_json_args() -> None:
    actual = create_input_data.get_metadata_from_json_args('{"priority":"high","category":"image"}')

    assert actual == {"priority": "high", "category": "image"}


def test_get_metadata_from_json_args_with_invalid_value() -> None:
    with pytest.raises(ValueError):
        create_input_data.get_metadata_from_json_args('{"priority":1}')


def test_get_input_data_list_from_df_with_common_metadata() -> None:
    csv_path = test_dir / "input_data_with_header.csv"
    df = create_input_data.read_input_data_csv(csv_path)

    actual = create_input_data.CreateInputData.get_input_data_list_from_df(df, common_metadata={"category": "image"})

    assert actual[0] == create_input_data.CsvInputData(
        input_data_name="data1",
        input_data_path="s3://example.com/data1",
        input_data_id="id1",
        metadata={"category": "image"},
    )


def test_get_input_data_list_from_df_with_independent_metadata_instances() -> None:
    csv_path = test_dir / "input_data_with_header.csv"
    df = create_input_data.read_input_data_csv(csv_path)

    actual = create_input_data.CreateInputData.get_input_data_list_from_df(df, common_metadata={"category": "image"})
    assert actual[0].metadata is not None
    assert actual[1].metadata is not None

    actual[0].metadata["category"] = "document"

    assert actual[1].metadata == {"category": "image"}


def test_get_input_data_list_from_dict_with_common_metadata() -> None:
    actual = create_input_data.CreateInputData.get_input_data_list_from_dict(
        [
            {"input_data_name": "data1", "input_data_path": "file://tests/data/lenna.png", "metadata": {"country": "japan"}},
            {"input_data_name": "data2", "input_data_path": "s3://example.com/data2", "input_data_id": "id2"},
        ],
        allow_duplicated_input_data=False,
        common_metadata={"category": "image", "country": "us"},
    )

    assert actual == [
        create_input_data.CsvInputData(
            input_data_name="data1",
            input_data_path="file://tests/data/lenna.png",
            input_data_id=None,
            metadata={"category": "image", "country": "japan"},
        ),
        create_input_data.CsvInputData(
            input_data_name="data2",
            input_data_path="s3://example.com/data2",
            input_data_id="id2",
            metadata={"category": "image", "country": "us"},
        ),
    ]


def test_get_input_data_list_from_dict_with_invalid_metadata() -> None:
    with pytest.raises(ValueError):
        create_input_data.CreateInputData.get_input_data_list_from_dict(
            [{"input_data_name": "data1", "input_data_path": "file://tests/data/lenna.png", "metadata": {"priority": 1}}],
            allow_duplicated_input_data=False,
        )


def test_get_input_data_list_from_dict_with_missing_required_key() -> None:
    with pytest.raises(TypeError):
        create_input_data.CreateInputData.get_input_data_list_from_dict(
            [{"input_data_name": "data1"}],
            allow_duplicated_input_data=False,
        )


def test_get_input_data_list_from_dict_with_non_dict_element() -> None:
    input_data_list: list[Any] = [{"input_data_name": "data1", "input_data_path": "file://tests/data/lenna.png"}, "data2"]

    with pytest.raises(TypeError):
        create_input_data.CreateInputData.get_input_data_list_from_dict(
            input_data_list,
            allow_duplicated_input_data=False,
        )


def test_get_input_data_list_from_dict_with_mapping_metadata() -> None:
    actual = create_input_data.CreateInputData.get_input_data_list_from_dict(
        [{"input_data_name": "data1", "input_data_path": "file://tests/data/lenna.png", "metadata": UserDict({"country": "japan"})}],
        allow_duplicated_input_data=False,
    )

    assert actual == [
        create_input_data.CsvInputData(
            input_data_name="data1",
            input_data_path="file://tests/data/lenna.png",
            input_data_id=None,
            metadata={"country": "japan"},
        )
    ]


def test_create_input_data_with_metadata() -> None:
    service = Mock()
    facade = Mock()
    main_obj = create_input_data.SubCreateInputData(service=service, facade=facade)

    main_obj.create_input_data(
        "project1",
        create_input_data.InputDataForCreate(
            input_data_name="data1",
            input_data_path="s3://example.com/data1",
            input_data_id="input_data_001",
            metadata={"category": "image"},
        ),
    )

    service.api.put_input_data.assert_called_once_with(
        "project1",
        "input_data_001",
        request_body={
            "last_updated_datetime": None,
            "metadata": {"category": "image"},
            "input_data_name": "data1",
            "input_data_path": "s3://example.com/data1",
        },
    )
