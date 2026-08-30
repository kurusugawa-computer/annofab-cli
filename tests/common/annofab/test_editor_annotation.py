from unittest.mock import Mock

from annofabcli.common.annofab.editor_annotation import get_editor_annotation_dict_in_bulk


def test_get_editor_annotation_dict_in_bulk_falls_back_to_single_request() -> None:
    service = Mock()
    service.api.get_editor_annotations_in_bulk.return_value = (
        {
            "success": [{"input_data_id": "input1", "details": []}],
            "failure": [{"input_data_id": "input2"}],
        },
        None,
    )
    service.api.get_editor_annotation.return_value = ({"input_data_id": "input2", "details": []}, None)

    actual = get_editor_annotation_dict_in_bulk(service, "prj1", "task1", ["input1", "input2"])

    assert actual == {
        "input1": {"input_data_id": "input1", "details": []},
        "input2": {"input_data_id": "input2", "details": []},
    }
    service.api.get_editor_annotation.assert_called_once_with("prj1", "task1", "input2", query_params={"v": "2"})
