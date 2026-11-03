import threading
from unittest.mock import Mock

import pytest
from annofabapi.models import ProjectMemberRole


@pytest.fixture
def threaded_task_lookup() -> tuple[Mock, list[str]]:
    service = Mock()
    service.api.get_project.return_value = ({"title": "project"}, None)
    service.api.get_my_member_in_project.return_value = ({"member_role": ProjectMemberRole.OWNER.value}, None)
    service.api.get_annotation_specs.return_value = ({"labels": [], "additionals": [], "inspection_phrases": []}, None)
    barrier = threading.Barrier(2)
    main_thread_id = threading.get_ident()
    looked_up: list[str] = []

    def get_task(project_id, task_id):
        assert project_id == "project1"
        assert threading.get_ident() != main_thread_id
        looked_up.append(task_id)
        barrier.wait(timeout=10)
        if task_id == "task2":
            raise RuntimeError("task API failure")

    service.wrapper.get_task_or_none.side_effect = get_task
    return service, looked_up
