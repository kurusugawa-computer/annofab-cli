from unittest.mock import Mock

import pytest
from annofabapi.models import JobStatus

from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.download import DownloadFileTarget, DownloadingFile


def test_common_updater_deduplicates_projects_and_targets_and_uses_wait_options():
    service = Mock()
    service.api.post_project_inputs_update.return_value = ({"job": {"job_id": "input"}}, None)
    service.wrapper.wait_until_job_finished.return_value = JobStatus.SUCCEEDED
    project_ids = ["p1", "p2", "p3", "p4", "p5", "p1"]
    DownloadingFile(service).update_download_files(project_ids, [DownloadFileTarget.INPUT_DATA, DownloadFileTarget.INPUT_DATA], wait_options=WaitOptions(interval=1, max_tries=2))
    assert [call.args[0] for call in service.api.post_project_inputs_update.call_args_list] == project_ids[:5]
    assert service.wrapper.wait_until_job_finished.call_count == 5
    for call in service.wrapper.wait_until_job_finished.call_args_list:
        assert call.kwargs["job_access_interval"] == 1
        assert call.kwargs["max_job_access"] == 2
    service.api.post_project_tasks_update.assert_not_called()
    service.api.post_annotation_archive_update.assert_not_called()


@pytest.mark.parametrize(("projects", "targets"), [([], [DownloadFileTarget.TASK]), (["p"], [])])
def test_empty_update_selection_is_rejected_before_submitting_jobs(projects, targets):
    service = Mock()
    with pytest.raises(ValueError):
        DownloadingFile(service).update_download_files(projects, targets)
    assert service.mock_calls == []
