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
