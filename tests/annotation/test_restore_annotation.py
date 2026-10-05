from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from annofabapi.models import ProjectMemberRole, TaskStatus
from annofabapi.parser import SimpleAnnotationDirParser

from annofabcli.annotation.restore_annotation import RestoreAnnotationMain


class TestRestoreAnnotationMain:
    @staticmethod
    def _create_main_obj(
        service: Mock,
        *,
        project_member_role: ProjectMemberRole,
        include_complete_task: bool = False,
        include_break_task: bool = False,
        include_on_hold_task: bool = False,
    ) -> RestoreAnnotationMain:
        service.api.account_id = "account_id"
        service.api.get_my_member_in_project.return_value = ({"member_role": project_member_role.value}, None)
        return RestoreAnnotationMain(
            service,
            project_id="prj1",
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
        main_obj = self._create_main_obj(service, project_member_role=ProjectMemberRole.OWNER)
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
        main_obj = self._create_main_obj(service, project_member_role=ProjectMemberRole.OWNER)
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
        main_obj = self._create_main_obj(service, project_member_role=ProjectMemberRole.ACCEPTER)
        main_obj.confirm_processing = Mock(return_value=True)  # type: ignore[method-assign]
        main_obj.put_annotation_for_task = Mock(return_value=1)  # type: ignore[method-assign]

        actual = main_obj.execute_task(task_parser)

        assert actual is True
        assert service.wrapper.change_task_operator.call_count == 2

    @pytest.mark.parametrize("format_version", [None, "1.0.0"])
    def test_put_annotation_rejects_v1_without_updating_annotation(self, tmp_path: Path, format_version: str | None) -> None:
        annotation: dict[str, Any] = {"details": []}
        if format_version is not None:
            annotation["format_version"] = format_version
        json_path = tmp_path / "input1.json"
        json_path.write_text(json.dumps(annotation), encoding="utf-8")
        service = Mock()
        main_obj = self._create_main_obj(service, project_member_role=ProjectMemberRole.OWNER)

        with pytest.raises(ValueError):
            main_obj.put_annotation_for_input_data(SimpleAnnotationDirParser(json_path))

        service.wrapper.upload_data_to_s3.assert_not_called()
        service.api.get_editor_annotation.assert_not_called()
        service.api.put_annotation.assert_not_called()

    def test_put_annotation_restores_v2_inner_and_outer(self, tmp_path: Path) -> None:
        task_dir = tmp_path / "task1"
        outer_dir = task_dir / "input1"
        outer_dir.mkdir(parents=True)
        outer_data = b'{"kind":"SEMANTIC_SEGMENT","points":[1,2]}'
        (outer_dir / "outer1").write_bytes(outer_data)
        inner_detail = {"annotation_id": "inner1", "label_id": "label1", "body": {"_type": "Inner", "data": {"x": 1, "y": 2}}}
        outer_detail = {"annotation_id": "outer1", "label_id": "label2", "body": {"_type": "Outer", "url": "https://example.com/outer1", "path": "old-path"}}
        annotation = {"format_version": "2.0.0", "details": [inner_detail, outer_detail]}
        json_path = task_dir / "input1.json"
        json_path.write_text(json.dumps(annotation), encoding="utf-8")
        service = Mock()
        service.api.get_editor_annotation.return_value = ({"updated_datetime": "2026-10-05T00:00:00+09:00"}, None)
        uploaded_data = []

        def upload_data_to_s3(project_id, data, *, content_type):
            uploaded_data.append((project_id, data.read(), content_type))
            return "s3://bucket/outer1"

        service.wrapper.upload_data_to_s3.side_effect = upload_data_to_s3
        main_obj = self._create_main_obj(service, project_member_role=ProjectMemberRole.OWNER)

        assert main_obj.put_annotation_for_input_data(SimpleAnnotationDirParser(json_path)) is True

        assert uploaded_data == [("prj1", outer_data, "application/octet-stream")]
        service.api.put_annotation.assert_called_once_with(
            "prj1",
            "task1",
            "input1",
            request_body={
                "project_id": "prj1",
                "task_id": "task1",
                "input_data_id": "input1",
                "format_version": "2.0.0",
                "updated_datetime": "2026-10-05T00:00:00+09:00",
                "details": [
                    {**inner_detail, "_type": "Import"},
                    {**outer_detail, "_type": "Import", "body": {"_type": "Outer", "path": "s3://bucket/outer1"}},
                ],
            },
        )
        assert json.loads(json_path.read_text(encoding="utf-8")) == annotation
