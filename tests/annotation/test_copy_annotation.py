from unittest.mock import Mock

import pytest
from annofabapi.models import ProjectMemberRole, TaskStatus

from annofabcli.annotation.copy_annotation import CopyAnnotationMain, CopyTargetByInputData, CopyTargetByTask, parse_copy_target


class TestCopyAnnotation:
    def test_copy_annotation__別担当のチェッカーは担当者変更オプションなしではスキップする(self):
        service = Mock()
        service.api.account_id = "account_id"
        service.api.get_my_member_in_project.return_value = ({"member_role": ProjectMemberRole.ACCEPTER.value}, None)
        service.wrapper.get_task_or_none.return_value = {
            "task_id": "dest_task",
            "phase": "annotation",
            "status": TaskStatus.NOT_STARTED.value,
            "account_id": "other_account_id",
            "updated_datetime": "2026-08-10T00:00:00+09:00",
        }
        obj = CopyAnnotationMain(
            service,
            project_id="prj1",
            all_yes=True,
            overwrite=False,
            merge=False,
            change_operator_to_me=False,
            include_complete_task=False,
            include_break_task=False,
            include_on_hold_task=False,
        )
        obj.confirm_processing = Mock(return_value=True)  # type: ignore[method-assign]

        actual = obj.copy_annotation(CopyTargetByInputData(src_task_id="src_task", dest_task_id="dest_task", src_input_data_id="src_input", dest_input_data_id="dest_input"))

        assert actual is False
        obj.confirm_processing.assert_not_called()

    def test_parse_copy_target__by_task(self):
        actual = parse_copy_target("task1:task2")
        assert isinstance(actual, CopyTargetByTask)
        assert actual.src_task_id == "task1"
        assert actual.dest_task_id == "task2"

    def test_parse_copy_target__by_input_data(self):
        actual = parse_copy_target("task1/input5:task2/input6")
        assert isinstance(actual, CopyTargetByInputData)
        assert actual.src_task_id == "task1"
        assert actual.src_input_data_id == "input5"
        assert actual.dest_task_id == "task2"
        assert actual.dest_input_data_id == "input6"

    def test_parse_copy_target__not_supported(self):
        with pytest.raises(ValueError):
            parse_copy_target("task1/input5:task2")

        with pytest.raises(ValueError):
            parse_copy_target("task1:task2/input6")

        with pytest.raises(ValueError):
            parse_copy_target("task1:task2:task3")

        with pytest.raises(ValueError):
            parse_copy_target("task1")
