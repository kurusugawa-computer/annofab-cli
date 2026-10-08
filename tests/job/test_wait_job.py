from unittest.mock import Mock

import pytest
from annofabapi.models import ProjectJobType

from annofabcli.job.wait_job import WaitJobMain


@pytest.mark.parametrize("job_id", [None, "job1"])
def test_wait_job_uses_fixed_wait_settings(job_id: str | None) -> None:
    service = Mock()
    service.wrapper.wait_until_job_finished.return_value = {"status": "complete"}

    WaitJobMain(service).wait_job("project1", job_type=ProjectJobType.GEN_ANNOTATION, job_id=job_id)

    service.wrapper.wait_until_job_finished.assert_called_once_with(
        "project1",
        job_type=ProjectJobType.GEN_ANNOTATION,
        job_id=job_id,
        job_access_interval=60,
        max_job_access=360,
    )
