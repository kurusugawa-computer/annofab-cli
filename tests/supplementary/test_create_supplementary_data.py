import pytest

from annofabcli.supplementary.create_supplementary_data import CreateSupplementaryData, read_supplementary_data_csv


def test__common_message():
    assert CreateSupplementaryData.COMMON_MESSAGE == "annofabcli supplementary create: error:"


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
