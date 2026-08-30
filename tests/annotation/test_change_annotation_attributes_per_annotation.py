from __future__ import annotations

import logging
from unittest.mock import Mock

import pytest

from annofabcli.annotation.change_annotation_attributes_per_annotation import (
    ChangeAnnotationAttributesPerAnnotationMain,
    TargetAnnotation,
)


def test_change_annotation_attributes_logs_each_task_progress(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    service = Mock()
    service.api.get_annotation_specs.return_value = ({}, None)
    main_obj = ChangeAnnotationAttributesPerAnnotationMain(service, project_id="project1", include_complete_task=False, all_yes=True)
    monkeypatch.setattr(main_obj, "change_annotation_attributes_for_task", Mock(return_value=(True, 1, 0)))
    annotation_list = [TargetAnnotation(task_id=f"task_{index:03d}", input_data_id="input1", annotation_id="annotation1", attributes={}) for index in range(3)]

    with caplog.at_level(logging.INFO):
        main_obj.change_annotation_attributes(annotation_list)

    assert "1 / 3 件目 :: task_id='task_000' のアノテーションの属性値を変更します。" in caplog.text
    assert "2 / 3 件目 :: task_id='task_001' のアノテーションの属性値を変更します。" in caplog.text
    assert "3 / 3 件目 :: task_id='task_002' のアノテーションの属性値を変更します。" in caplog.text


def test_change_annotation_attributes_by_frame_does_not_log_skip_when_all_attributes_are_changed(caplog: pytest.LogCaptureFixture) -> None:
    service = Mock()
    service.api.get_annotation_specs.return_value = ({"additionals": []}, None)
    service.api.get_editor_annotation.return_value = (
        {
            "project_id": "project1",
            "task_id": "task1",
            "input_data_id": "input1",
            "updated_datetime": "2026-08-30T23:17:58+09:00",
            "details": [{"annotation_id": "annotation1", "label_id": "label1"}],
        },
        None,
    )
    main_obj = ChangeAnnotationAttributesPerAnnotationMain(service, project_id="project1", include_complete_task=False, all_yes=True)

    with caplog.at_level(logging.DEBUG):
        actual = main_obj.change_annotation_attributes_by_frame(
            "task1",
            "input1",
            [TargetAnnotation(task_id="task1", input_data_id="input1", annotation_id="annotation1", attributes={})],
        )

    assert actual == (1, 0)
    assert "1/1件の属性値を変更しました。" in caplog.text
    assert "属性値の変更をスキップしました。" not in caplog.text
