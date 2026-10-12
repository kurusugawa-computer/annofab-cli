import uuid

import pytest
import ulid
from annofabapi.plugin import EditorPluginId

from annofabcli.annotation.annotation_id import resolve_annotation_id


@pytest.mark.parametrize("annotation_id", [None, "label_id", "wrong_id", ""])
def test_resolve_annotation_id__全体アノテーションはlabel_idを使用する(annotation_id, caplog):
    label = {"annotation_type": "classification", "label_id": "label_id"}
    project = {"input_data_type": "image", "configuration": {"plugin_id": None}}

    actual = resolve_annotation_id(label, project, annotation_id)

    assert actual == "label_id"
    assert bool(caplog.records) == (annotation_id not in {None, "label_id"})
    if caplog.records:
        assert "label_id" in caplog.text
        assert f"annotation_id='{annotation_id}'" in caplog.text


@pytest.mark.parametrize("input_data_type", ["image", "custom"])
def test_resolve_annotation_id__全体以外は指定されたIDを使用する(input_data_type):
    label = {"annotation_type": "bounding_box", "label_id": "label_id"}
    project = {"input_data_type": input_data_type, "configuration": {"plugin_id": EditorPluginId.THREE_DIMENSION.value}}

    assert resolve_annotation_id(label, project, "specified_id") == "specified_id"


@pytest.mark.parametrize("annotation_type", ["bounding_box", "classification"])
@pytest.mark.parametrize("annotation_id", [None, ""])
def test_resolve_annotation_id__3次元プロジェクトはULIDを生成する(annotation_type, annotation_id):
    label = {"annotation_type": annotation_type, "label_id": "label_id"}
    project = {"input_data_type": "custom", "configuration": {"plugin_id": EditorPluginId.THREE_DIMENSION.value}}

    actual = resolve_annotation_id(label, project, annotation_id)

    assert str(ulid.from_str(actual)) == actual
    assert resolve_annotation_id(label, project, "specified_id") == "specified_id"


@pytest.mark.parametrize("annotation_id", [None, ""])
def test_resolve_annotation_id__画像の矩形アノテーションはUUIDを生成する(annotation_id):
    label = {"annotation_type": "bounding_box", "label_id": "label_id"}
    project = {"input_data_type": "image", "configuration": {"plugin_id": None}}

    actual = resolve_annotation_id(label, project, annotation_id)

    assert str(uuid.UUID(actual, version=4)) == actual


@pytest.mark.parametrize("annotation_id", [None, "specified_id"])
def test_resolve_annotation_id__動画の全体アノテーションは指定IDを維持する(annotation_id, caplog):
    label = {"annotation_type": "classification", "label_id": "label_id"}
    project = {"input_data_type": "movie", "configuration": {"plugin_id": None}}

    actual = resolve_annotation_id(label, project, annotation_id)

    assert actual == (annotation_id if annotation_id is not None else "label_id")
    assert not caplog.records
