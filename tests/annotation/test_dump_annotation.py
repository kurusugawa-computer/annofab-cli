from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from annofabcli.annotation.dump_annotation import DumpAnnotationMain


class TestDumpAnnotationMain:
    @pytest.mark.parametrize("format_version", [None, "1.0.0"])
    def test_dump_rejects_v1_without_writing_backup(self, tmp_path: Path, format_version: str | None) -> None:
        annotation: dict[str, Any] = {"details": []}
        if format_version is not None:
            annotation["format_version"] = format_version
        json_path = tmp_path / "input1.json"
        service = Mock()
        main_obj = DumpAnnotationMain(service, "prj1")

        with pytest.raises(ValueError):
            main_obj.dump_editor_annotation(annotation, json_path)

        assert not json_path.exists()
        service.wrapper.download.assert_not_called()

    @pytest.mark.parametrize("has_outer", [False, True])
    def test_dump_v2(self, tmp_path: Path, *, has_outer: bool) -> None:
        annotation: dict[str, Any] = {
            "format_version": "2.0.0",
            "input_data_id": "input1",
            "details": [{"annotation_id": "inner1", "body": {"_type": "Inner", "data": {"x": 1, "y": 2}}}],
        }
        if has_outer:
            annotation["details"].append({"annotation_id": "outer1", "body": {"_type": "Outer", "url": "https://example.com/outer1"}})
        json_path = tmp_path / "input1.json"
        service = Mock()
        outer_data = b'{"points":[1,2]}'

        def download(_url, dest_path):
            dest_path.write_bytes(outer_data)

        service.wrapper.download.side_effect = download
        main_obj = DumpAnnotationMain(service, "prj1")

        main_obj.dump_editor_annotation(annotation, json_path)

        assert json.loads(json_path.read_text(encoding="utf-8")) == annotation
        if has_outer:
            assert (tmp_path / "input1" / "outer1").read_bytes() == outer_data
        else:
            assert not (tmp_path / "input1").exists()
            service.wrapper.download.assert_not_called()
