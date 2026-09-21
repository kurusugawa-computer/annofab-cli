import pytest

from annofabcli.input_data import update_metadata_per_input_data
from annofabcli.input_data.update_metadata_of_input_data import InputDataMetadataInfo


def test_get_input_data_metadata_info_list_from_json_args() -> None:
    actual = update_metadata_per_input_data.get_input_data_metadata_info_list_from_json_args(
        """
        [
            {"input_data_id": "input_data_001", "metadata": {"country": "japan"}, "input_data_name": "foo"},
            {"input_data_id": "input_data_002", "metadata": {"country": "us"}}
        ]
        """
    )

    assert actual == [
        InputDataMetadataInfo(input_data_id="input_data_001", metadata={"country": "japan"}),
        InputDataMetadataInfo(input_data_id="input_data_002", metadata={"country": "us"}),
    ]


def test_get_input_data_metadata_info_list_from_json_args_with_non_list_json() -> None:
    with pytest.raises(TypeError):
        update_metadata_per_input_data.get_input_data_metadata_info_list_from_json_args('{"input_data_001": {"country": "japan"}}')


def test_get_input_data_metadata_info_list_from_json_args_with_duplicate_input_data_id() -> None:
    with pytest.raises(ValueError):
        update_metadata_per_input_data.get_input_data_metadata_info_list_from_json_args('[{"input_data_id": "input_data_001", "metadata": {}}, {"input_data_id": "input_data_001", "metadata": {}}]')
