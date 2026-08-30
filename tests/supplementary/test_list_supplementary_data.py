from unittest.mock import Mock

from annofabcli.supplementary.list_supplementary_data import ListSupplementaryDataMain


def test_get_all_supplementary_data_list() -> None:
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

    result = main_obj.get_all_supplementary_data_list([f"input{i}" for i in range(1, 12)])

    assert result == [{"input_data_id": "input1", "supplementary_data_id": "supplementary1"}]
    assert service.api.get_supplementary_data_in_bulk.call_args_list == [
        (("project1",), {"query_params": {"input_data_id": ",".join(f"input{i}" for i in range(1, 11))}}),
        (("project1",), {"query_params": {"input_data_id": "input11"}}),
    ]
