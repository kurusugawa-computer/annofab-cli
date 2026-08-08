from __future__ import annotations

from unittest.mock import Mock

from annofabapi.models import ProjectMemberRole, TaskStatus

from annofabcli.annotation.restore_annotation import RestoreAnnotationMain


class TestRestoreAnnotationMain:
    @staticmethod
    def _create_main_obj(
        service: Mock,
        *,
        project_member_role: ProjectMemberRole,
        change_operator_to_me: bool = False,
        include_complete_task: bool = False,
        include_break_task: bool = False,
        include_on_hold_task: bool = False,
    ) -> RestoreAnnotationMain:
        service.api.account_id = "account_id"
        service.api.get_my_member_in_project.return_value = ({"member_role": project_member_role.value}, None)
        return RestoreAnnotationMain(
            service,
            project_id="prj1",
            change_operator_to_me=change_operator_to_me,
            include_complete_task=include_complete_task,
            include_break_task=include_break_task,
            include_on_hold_task=include_on_hold_task,
            all_yes=True,
        )

    def test_execute_task_skips_break_task_before_confirmation(self) -> None:
        service = Mock()
        service.wrapper.get_task_or_none.return_value = {
            "task_id": "task1",
            "phase": "annotation",
            "status": "break",
            "account_id": "operator1",
            "updated_datetime": "2026-05-22T00:00:00+09:00",
        }
        task_parser = Mock()
        task_parser.task_id = "task1"
        main_obj = self._create_main_obj(service, project_member_role=ProjectMemberRole.OWNER, change_operator_to_me=True)
        main_obj.confirm_processing = Mock(return_value=True)  # type: ignore[method-assign]
        main_obj.put_annotation_for_task = Mock(return_value=1)  # type: ignore[method-assign]

        actual = main_obj.execute_task(task_parser)

        assert actual is False
        main_obj.confirm_processing.assert_not_called()
        main_obj.put_annotation_for_task.assert_not_called()
        service.wrapper.change_task_operator.assert_not_called()

    def test_execute_task_owner_does_not_change_operator(self) -> None:
        service = Mock()
        service.wrapper.get_task_or_none.return_value = {
            "task_id": "task1",
            "phase": "annotation",
            "status": TaskStatus.NOT_STARTED.value,
            "account_id": "other_account_id",
            "updated_datetime": "2026-05-22T00:00:00+09:00",
        }
        task_parser = Mock()
        task_parser.task_id = "task1"
        main_obj = self._create_main_obj(service, project_member_role=ProjectMemberRole.OWNER, change_operator_to_me=True)
        main_obj.confirm_processing = Mock(return_value=True)  # type: ignore[method-assign]
        main_obj.put_annotation_for_task = Mock(return_value=1)  # type: ignore[method-assign]

        actual = main_obj.execute_task(task_parser)

        assert actual is True
        service.wrapper.change_task_operator.assert_not_called()

    def test_execute_task_skips_on_hold_task_before_confirmation(self) -> None:
        service = Mock()
        service.wrapper.get_task_or_none.return_value = {
            "task_id": "task1",
            "phase": "annotation",
            "status": TaskStatus.ON_HOLD.value,
            "account_id": "account_id",
            "updated_datetime": "2026-05-22T00:00:00+09:00",
        }
        task_parser = Mock()
        task_parser.task_id = "task1"
        main_obj = self._create_main_obj(service, project_member_role=ProjectMemberRole.OWNER)
        main_obj.confirm_processing = Mock(return_value=True)  # type: ignore[method-assign]
        main_obj.put_annotation_for_task = Mock(return_value=1)  # type: ignore[method-assign]

        actual = main_obj.execute_task(task_parser)

        assert actual is False
        main_obj.confirm_processing.assert_not_called()
        main_obj.put_annotation_for_task.assert_not_called()

    def test_execute_task_owner_can_restore_complete_task_when_option_is_specified(self) -> None:
        service = Mock()
        service.wrapper.get_task_or_none.return_value = {
            "task_id": "task1",
            "phase": "annotation",
            "status": TaskStatus.COMPLETE.value,
            "account_id": "other_account_id",
            "updated_datetime": "2026-05-22T00:00:00+09:00",
        }
        task_parser = Mock()
        task_parser.task_id = "task1"
        main_obj = self._create_main_obj(service, project_member_role=ProjectMemberRole.OWNER, include_complete_task=True)
        main_obj.confirm_processing = Mock(return_value=True)  # type: ignore[method-assign]
        main_obj.put_annotation_for_task = Mock(return_value=1)  # type: ignore[method-assign]

        actual = main_obj.execute_task(task_parser)

        assert actual is True
        service.wrapper.change_task_operator.assert_not_called()

    def test_execute_task_checker_assigned_to_task_does_not_change_operator(self) -> None:
        service = Mock()
        service.wrapper.get_task_or_none.return_value = {
            "task_id": "task1",
            "phase": "annotation",
            "status": TaskStatus.NOT_STARTED.value,
            "account_id": "account_id",
            "updated_datetime": "2026-05-22T00:00:00+09:00",
        }
        task_parser = Mock()
        task_parser.task_id = "task1"
        main_obj = self._create_main_obj(service, project_member_role=ProjectMemberRole.ACCEPTER)
        main_obj.confirm_processing = Mock(return_value=True)  # type: ignore[method-assign]
        main_obj.put_annotation_for_task = Mock(return_value=1)  # type: ignore[method-assign]

        actual = main_obj.execute_task(task_parser)

        assert actual is True
        service.wrapper.change_task_operator.assert_not_called()

    def test_execute_task_checker_not_assigned_to_task_requires_option(self) -> None:
        service = Mock()
        service.wrapper.get_task_or_none.return_value = {
            "task_id": "task1",
            "phase": "annotation",
            "status": TaskStatus.NOT_STARTED.value,
            "account_id": "other_account_id",
            "updated_datetime": "2026-05-22T00:00:00+09:00",
        }
        task_parser = Mock()
        task_parser.task_id = "task1"
        main_obj = self._create_main_obj(service, project_member_role=ProjectMemberRole.ACCEPTER)
        main_obj.confirm_processing = Mock(return_value=True)  # type: ignore[method-assign]
        main_obj.put_annotation_for_task = Mock(return_value=1)  # type: ignore[method-assign]

        actual = main_obj.execute_task(task_parser)

        assert actual is False
        main_obj.confirm_processing.assert_not_called()
        main_obj.put_annotation_for_task.assert_not_called()

    def test_execute_task_checker_not_assigned_to_task_changes_operator(self) -> None:
        service = Mock()
        task = {
            "task_id": "task1",
            "phase": "annotation",
            "status": TaskStatus.NOT_STARTED.value,
            "account_id": "other_account_id",
            "updated_datetime": "2026-05-22T00:00:00+09:00",
        }
        service.wrapper.get_task_or_none.return_value = task
        service.wrapper.change_task_operator.return_value = task
        task_parser = Mock()
        task_parser.task_id = "task1"
        main_obj = self._create_main_obj(service, project_member_role=ProjectMemberRole.ACCEPTER, change_operator_to_me=True)
        main_obj.confirm_processing = Mock(return_value=True)  # type: ignore[method-assign]
        main_obj.put_annotation_for_task = Mock(return_value=1)  # type: ignore[method-assign]

        actual = main_obj.execute_task(task_parser)

        assert actual is True
        assert service.wrapper.change_task_operator.call_count == 2
