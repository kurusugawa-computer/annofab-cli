from __future__ import annotations

from unittest.mock import Mock

from annofabcli.annotation.restore_annotation import RestoreAnnotationMain


class TestRestoreAnnotationMain:
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
        main_obj = RestoreAnnotationMain(
            service,
            project_id="prj1",
            change_operator_to_me=True,
            include_break_task=False,
            all_yes=True,
        )
        main_obj.confirm_processing = Mock(return_value=True)  # type: ignore[method-assign]
        main_obj.put_annotation_for_task = Mock(return_value=1)  # type: ignore[method-assign]

        actual = main_obj.execute_task(task_parser)

        assert actual is False
        main_obj.confirm_processing.assert_not_called()
        main_obj.put_annotation_for_task.assert_not_called()
        service.wrapper.change_task_operator.assert_not_called()
