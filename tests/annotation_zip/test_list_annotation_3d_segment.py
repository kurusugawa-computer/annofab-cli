"""Test cases for annofabcli.annotation_zip.list_annotation_3d_segment module."""

import io
import json
from pathlib import Path

import pytest
from annofabapi.exceptions import AnnotationOuterFileNotFoundError

from annofabcli.__main__ import main
from annofabcli.annotation_zip.list_annotation_3d_segment import create_df, get_annotation_3d_segment_info_list

data_dir = Path("tests/data/annotation_zip")


def create_simple_annotation() -> dict:
    return {
        "project_id": "project1",
        "task_id": "task1",
        "task_phase": "annotation",
        "task_phase_stage": 1,
        "task_status": "working",
        "input_data_id": "input1",
        "input_data_name": "input1.pcd",
        "updated_datetime": "2026-09-28T10:00:00+09:00",
        "details": [
            {
                "label": "Road",
                "annotation_id": "segment1",
                "data": {"data": "./input1/segment1", "_type": "Unknown"},
                "attributes": {"surface_type": "asphalt"},
            },
            {
                "label": "Building",
                "annotation_id": "segment2",
                "data": {"data": "./input1/segment2", "_type": "Unknown"},
                "attributes": {},
            },
            {
                "label": "Car",
                "annotation_id": "cuboid1",
                "data": {
                    "data": '{"kind":"CUBOID","shape":{"dimensions":{"width":2,"height":2,"depth":4},'
                    '"location":{"x":0,"y":0,"z":0},"rotation":{"x":0,"y":0,"z":0},'
                    '"direction":{"front":{"x":1,"y":0,"z":0},"up":{"x":0,"y":0,"z":1}}},"version":"2"}',
                    "_type": "Unknown",
                },
                "attributes": {},
            },
        ],
    }


class TestGetAnnotation3DSegmentInfoList:
    def test_basic(self):
        outer_files = {
            "segment1": {"kind": "SEGMENT", "points": [1, 3, 5], "version": "1"},
            "segment2": {"kind": "SEGMENT", "points": [2, 4], "version": "1"},
        }
        opened_data_uris = []

        def open_outer_file(data_uri: str) -> io.BytesIO:
            opened_data_uris.append(data_uri)
            return io.BytesIO(json.dumps(outer_files[data_uri]).encode())

        result = get_annotation_3d_segment_info_list(create_simple_annotation(), open_outer_file=open_outer_file)

        assert len(result) == 2
        assert opened_data_uris == ["segment1", "segment2"]
        assert result[0].label == "Road"
        assert result[0].annotation_id == "segment1"
        assert result[0].data_uri == "./input1/segment1"
        assert result[0].point_count == 3
        assert result[0].attributes == {"surface_type": "asphalt"}
        assert result[1].point_count == 2

    def test_label_filter(self):
        result = get_annotation_3d_segment_info_list(create_simple_annotation(), target_label_names=["Building"])

        assert len(result) == 1
        assert result[0].label == "Building"
        assert result[0].point_count is None

    def test_outer_file_not_found(self, caplog: pytest.LogCaptureFixture):
        def open_outer_file(_data_uri: str) -> io.BytesIO:
            raise AnnotationOuterFileNotFoundError("not found")

        result = get_annotation_3d_segment_info_list(create_simple_annotation(), open_outer_file=open_outer_file)

        assert len(result) == 2
        assert result[0].point_count is None
        assert "point_countをNoneにします" in caplog.text

    def test_invalid_outer_file(self, caplog: pytest.LogCaptureFixture):
        def open_outer_file(_data_uri: str) -> io.BytesIO:
            return io.BytesIO(b'{"kind":"SEGMENT","points":"invalid"}')

        result = get_annotation_3d_segment_info_list(create_simple_annotation(), open_outer_file=open_outer_file)

        assert len(result) == 2
        assert all(e.point_count is None for e in result)
        assert "pointsが配列ではありません" in caplog.text


class TestCreateDf:
    def test_with_attributes(self):
        result = get_annotation_3d_segment_info_list(create_simple_annotation())
        df = create_df(result)

        assert list(df.columns) == [
            "project_id",
            "task_id",
            "task_phase",
            "task_phase_stage",
            "task_status",
            "input_data_id",
            "input_data_name",
            "updated_datetime",
            "label",
            "annotation_id",
            "annotation_editor_url",
            "data_uri",
            "point_count",
            "attributes.surface_type",
        ]
        assert len(df) == 2
        assert df.iloc[0]["attributes.surface_type"] == "asphalt"

    def test_empty(self):
        df = create_df([])

        assert df.empty
        assert "point_count" in df.columns
        assert len(df.columns) == 13


@pytest.mark.access_webapi
class TestCommandLine:
    def test_list_3d_segment_annotation(self, tmp_path: Path):
        output = tmp_path / "list_3d_segment_annotation-out.json"
        main(
            [
                "annotation_zip",
                "list_3d_segment_annotation",
                "--annotation",
                str(data_dir / "3dpc-annotation"),
                "--output",
                str(output),
                "--format",
                "pretty_json",
                "--disable_log",
            ]
        )

        result = json.loads(output.read_text())
        assert len(result) == 3
        assert {e["label"]: e["point_count"] for e in result} == {"Road": 57746, "Building": 34429, "Motorcycle": 146}
