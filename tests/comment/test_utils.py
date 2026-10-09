import json

import pytest
from annofabapi.plugin import EditorPluginId

from annofabcli.comment.utils import resolve_inspection_comment_data


def test_standard_3d_editor_generates_default_cuboid() -> None:
    project = {"input_data_type": "custom", "configuration": {"plugin_id": EditorPluginId.THREE_DIMENSION.value}}

    actual = resolve_inspection_comment_data(project, None)

    assert actual["_type"] == "Custom"
    cuboid = json.loads(actual["data"])
    assert cuboid["kind"] == "CUBOID"
    assert cuboid["shape"]["dimensions"] == {"width": 1.0, "height": 1.0, "depth": 1.0}
    assert cuboid["shape"]["location"] == {"x": 0.0, "y": 0.0, "z": 0.0}


@pytest.mark.parametrize("input_data_type", ["image", "movie", "custom"])
def test_supported_project_preserves_explicit_comment_data(input_data_type: str) -> None:
    project = {"input_data_type": input_data_type, "configuration": {"plugin_id": EditorPluginId.THREE_DIMENSION.value}}
    data = {"_type": "Custom", "data": "explicit-position"}

    assert resolve_inspection_comment_data(project, data) == data
