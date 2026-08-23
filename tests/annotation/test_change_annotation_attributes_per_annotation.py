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
