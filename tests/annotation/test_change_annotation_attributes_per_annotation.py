from __future__ import annotations

import logging
from unittest.mock import Mock

import pytest

from annofabcli.annotation.change_annotation_attributes_per_annotation import (
    ChangeAnnotationAttributesPerAnnotationMain,
    TargetAnnotation,
)


def test_change_annotation_attributes_logs_progress_every_100_annotations(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    service = Mock()
    service.api.get_annotation_specs.return_value = ({}, None)
    main_obj = ChangeAnnotationAttributesPerAnnotationMain(service, project_id="project1", include_complete_task=False, all_yes=True)
    monkeypatch.setattr(main_obj, "change_annotation_attributes_for_task", Mock(return_value=(True, 1, 0)))
    annotation_list = [TargetAnnotation(task_id=f"task_{index:03d}", input_data_id="input1", annotation_id="annotation1", attributes={}) for index in range(205)]

    with caplog.at_level(logging.INFO):
        main_obj.change_annotation_attributes(annotation_list)

    assert "100 / 205 件のアノテーションの属性値の変更処理が完了しました。" in caplog.text
    assert "200 / 205 件のアノテーションの属性値の変更処理が完了しました。" in caplog.text
    assert "205 / 205 件のアノテーションの属性値の変更処理が完了しました。" in caplog.text
