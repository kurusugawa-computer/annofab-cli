from threading import Barrier
from unittest.mock import Mock, call

import pytest
import requests
from annofabapi.models import JobStatus, ProjectJobType

from annofabcli.common.exceptions import UpdatedFileForDownloadingError
from annofabcli.project.update_download_files import DownloadFileTarget, UpdateDownloadFilesMain


@pytest.fixture
def service():
    service = Mock()
    service.api.post_project_tasks_update.return_value = ({"job": {"job_id": "task-job"}}, None)
    service.api.post_annotation_archive_update.return_value = ({"job": {"job_id": "annotation-job"}}, None)
    service.api.post_project_inputs_update.return_value = ({"job": {"job_id": "input-job"}}, None)
    service.api.get_project_job.return_value = ({"list": [{"job_id": "existing-job"}]}, None)
    service.wrapper.wait_until_job_finished.return_value = JobStatus.SUCCEEDED
    return service


def test_updates_all_targets_concurrently_and_waits_for_each_job(service, capsys):
    # 逐次実行では全対象がバリアに到達できず、テストが失敗する。
    barrier = Barrier(3, timeout=5)

    def wait_for_job(project_id, *, job_type, job_id, job_access_interval, max_job_access):
        barrier.wait()
        assert project_id == "p"
        assert job_access_interval == 60
        assert max_job_access == 360
        assert (
            job_id
            == {
                ProjectJobType.GEN_TASKS_LIST: "task-job",
                ProjectJobType.GEN_ANNOTATION: "annotation-job",
                ProjectJobType.GEN_INPUTS_LIST: "input-job",
            }[job_type]
        )
        return JobStatus.SUCCEEDED

    service.wrapper.wait_until_job_finished.side_effect = wait_for_job
    UpdateDownloadFilesMain(service).update_download_files(["p"], list(DownloadFileTarget))

    service.api.post_project_tasks_update.assert_called_once_with("p")
    service.api.post_annotation_archive_update.assert_called_once_with("p")
    service.api.post_project_inputs_update.assert_called_once_with("p")
    assert service.wrapper.wait_until_job_finished.call_count == 3
    assert capsys.readouterr().out == ""


def test_updates_only_selected_target_once(service):
    UpdateDownloadFilesMain(service).update_download_files(["p"], [DownloadFileTarget.TASK, DownloadFileTarget.TASK])

    service.api.post_project_tasks_update.assert_called_once_with("p")
    service.api.post_annotation_archive_update.assert_not_called()
    service.api.post_project_inputs_update.assert_not_called()
    assert service.wrapper.wait_until_job_finished.call_count == 1


@pytest.mark.parametrize("job_status", [JobStatus.FAILED, JobStatus.PROGRESS, None])
def test_failed_timed_out_or_missing_job_is_error_but_other_targets_finish(service, job_status):
    def wait_for_job(_project_id, *, job_type, **_kwargs):
        return job_status if job_type == ProjectJobType.GEN_TASKS_LIST else JobStatus.SUCCEEDED

    service.wrapper.wait_until_job_finished.side_effect = wait_for_job
    with pytest.raises(UpdatedFileForDownloadingError):
        UpdateDownloadFilesMain(service).update_download_files(["p"], list(DownloadFileTarget))

    assert service.wrapper.wait_until_job_finished.call_count == 3


def test_submission_failure_does_not_prevent_other_updates(service):
    service.api.post_project_tasks_update.side_effect = requests.ConnectionError()

    with pytest.raises(UpdatedFileForDownloadingError):
        UpdateDownloadFilesMain(service).update_download_files(["p"], list(DownloadFileTarget))

    service.api.post_annotation_archive_update.assert_called_once_with("p")
    service.api.post_project_inputs_update.assert_called_once_with("p")
    assert service.wrapper.wait_until_job_finished.call_count == 2


def test_conflict_waits_for_existing_job(service):
    response = requests.Response()
    response.status_code = 409
    response._content = b'{"errors": [{"message": "conflict"}]}'
    service.api.post_project_tasks_update.side_effect = requests.HTTPError(response=response)

    UpdateDownloadFilesMain(service).update_download_files(["p"], [DownloadFileTarget.TASK])

    service.wrapper.wait_until_job_finished.assert_called_once_with("p", job_type=ProjectJobType.GEN_TASKS_LIST, job_id="existing-job", job_access_interval=60, max_job_access=360)


@pytest.mark.parametrize("job_status", [JobStatus.FAILED, JobStatus.PROGRESS, None])
def test_conflicting_job_failure_is_reported(service, job_status):
    response = requests.Response()
    response.status_code = 409
    response._content = b'{"errors": [{"message": "conflict"}]}'
    service.api.post_project_tasks_update.side_effect = requests.HTTPError(response=response)
    service.wrapper.wait_until_job_finished.return_value = job_status

    with pytest.raises(UpdatedFileForDownloadingError):
        UpdateDownloadFilesMain(service).update_download_files(["p"], [DownloadFileTarget.TASK])


@pytest.mark.parametrize("targets", [[DownloadFileTarget.ANNOTATION], list(DownloadFileTarget)])
def test_four_projects_update_all_selected_targets_concurrently(service, targets):
    project_ids = ["p1", "p2", "p3", "p4"]
    job_count = len(project_ids) * len(targets)
    barrier = Barrier(job_count, timeout=5)

    def wait_for_job(_project_id, **_kwargs):
        barrier.wait()
        return JobStatus.SUCCEEDED

    service.wrapper.wait_until_job_finished.side_effect = wait_for_job
    UpdateDownloadFilesMain(service).update_download_files(project_ids, targets)

    expected_calls = [call(project_id) for project_id in project_ids]
    service.api.post_annotation_archive_update.assert_has_calls(expected_calls, any_order=True)
    if DownloadFileTarget.TASK in targets:
        service.api.post_project_tasks_update.assert_has_calls(expected_calls, any_order=True)
        service.api.post_project_inputs_update.assert_has_calls(expected_calls, any_order=True)
    else:
        service.api.post_project_tasks_update.assert_not_called()
        service.api.post_project_inputs_update.assert_not_called()
    assert service.wrapper.wait_until_job_finished.call_count == job_count


def test_five_projects_are_rejected_before_submitting_any_jobs(service):
    with pytest.raises(ValueError):
        UpdateDownloadFilesMain(service).update_download_files(["p1", "p2", "p3", "p4", "p5"], [DownloadFileTarget.ANNOTATION])

    assert service.api.mock_calls == []
    assert service.wrapper.mock_calls == []


def test_project_failure_does_not_prevent_other_projects_from_updating(service):
    def update_annotation(project_id):
        if project_id == "p2":
            raise requests.ConnectionError
        return {"job": {"job_id": f"{project_id}-job"}}, None

    service.api.post_annotation_archive_update.side_effect = update_annotation
    with pytest.raises(UpdatedFileForDownloadingError):
        UpdateDownloadFilesMain(service).update_download_files(["p1", "p2", "p3", "p4"], [DownloadFileTarget.ANNOTATION])

    assert service.api.post_annotation_archive_update.call_count == 4
    assert service.wrapper.wait_until_job_finished.call_count == 3
