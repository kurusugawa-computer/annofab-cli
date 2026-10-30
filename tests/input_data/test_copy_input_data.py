import json
from pathlib import Path
from unittest.mock import Mock

import annofabapi
import pytest
import requests
from annofabapi.credentials import IdPass
from annofabapi.models import JobStatus, ProjectJobType

from annofabcli.input_data.copy_input_data import CopyInputDataMain


@pytest.mark.parametrize("file_exists", [True, False])
def test_get_all_input_data_ids_creates_missing_file(monkeypatch, file_exists):
    service = annofabapi.Resource(IdPass("test", "test"))
    monkeypatch.setattr(service.api, "get_project", Mock(return_value=({"title": "test"}, None)))
    download_response = ({"url": "https://example.com/inputs.json"}, None)
    responses: list[tuple[dict[str, str], None] | requests.HTTPError] = [download_response]
    if not file_exists:
        response = requests.Response()
        response.status_code = 404
        responses.insert(0, requests.HTTPError(response=response))
    monkeypatch.setattr(service.api, "get_project_inputs_url", Mock(side_effect=responses))
    update = Mock(return_value=({"job": {"job_id": "input-job"}}, None))
    wait = Mock(return_value=JobStatus.SUCCEEDED)
    monkeypatch.setattr(service.api, "post_project_inputs_update", update)
    monkeypatch.setattr(service.wrapper, "wait_until_job_finished", wait)

    def download(_url, dest_path, **_kwargs):
        Path(dest_path).write_text(json.dumps([{"input_data_id": "input1"}, {"input_data_id": "input2"}]), encoding="utf-8")

    monkeypatch.setattr(service.wrapper, "download", download)
    command = CopyInputDataMain(service, src_project_id="src", dest_project_id="dest", should_overwrite=False)

    assert command.get_all_input_data_id_list("src") == ["input1", "input2"]
    if file_exists:
        update.assert_not_called()
        wait.assert_not_called()
    else:
        update.assert_called_once_with("src")
        wait.assert_called_once_with("src", job_type=ProjectJobType.GEN_INPUTS_LIST, job_id="input-job", job_access_interval=60, max_job_access=360)
