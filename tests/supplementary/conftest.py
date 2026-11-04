import threading
from unittest.mock import Mock

import pytest
import requests


@pytest.fixture
def supplementary_thread_service(request: pytest.FixtureRequest) -> tuple[Mock, Mock, list[str]]:
    service = Mock()
    facade = Mock()
    facade.get_project_title.return_value = "project"
    barrier = threading.Barrier(2)
    main_thread_id = threading.get_ident()
    created_input_ids: list[str] = []

    def get_supplementary_data(_project_id, input_data_id):
        assert threading.get_ident() != main_thread_id
        if input_data_id in {"input1", "input2"}:
            barrier.wait(timeout=10)
        if input_data_id == "failed" and request.param == "read":
            raise RuntimeError("read API failure")
        return None if input_data_id == "missing" else []

    def put_supplementary_data(_project_id, input_data_id, _supplementary_data_id, *, request_body):
        assert request_body["supplementary_data_number"] == 1
        if input_data_id == "failed":
            raise requests.HTTPError("write API failure")
        created_input_ids.append(input_data_id)
        return {}, None

    service.wrapper.get_supplementary_data_list_or_none.side_effect = get_supplementary_data
    service.api.put_supplementary_data.side_effect = put_supplementary_data
    return service, facade, created_input_ids


@pytest.fixture
def supplementary_delete_service():
    service = Mock()
    service.api.get_project.return_value = ({"title": "project"}, None)
    service.api.get_my_member_in_project.return_value = ({"member_role": "owner"}, None)
    service.wrapper.get_input_data_or_none.side_effect = lambda _project, input_id: None if input_id == "missing-input" else {"input_data_name": input_id}
    records = [
        {"input_data_id": input_id, "supplementary_data_id": supplementary_id, "supplementary_data_name": supplementary_id}
        for input_id in ("input1", "input2")
        for supplementary_id in ("s1", "s2", "keep")
    ]
    service.api.get_supplementary_data_in_bulk.side_effect = lambda _project, *, query_params: (
        {"success": [row for row in records if row["input_data_id"] in query_params["input_data_id"].split(",")], "failure": []},
        None,
    )
    service.api.get_supplementary_data_list.side_effect = lambda _project, input_id: ([row for row in records if row["input_data_id"] == input_id], None)
    return service
