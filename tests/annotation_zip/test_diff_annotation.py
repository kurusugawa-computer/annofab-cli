from __future__ import annotations

import json
from pathlib import Path

import pytest

from annofabcli.__main__ import main
from annofabcli.annotation_zip.diff_annotation import create_annotation_zip_diff, create_detail_df, create_summary_df


def _create_simple_annotation(details: list[dict], *, task_id: str = "task1") -> dict:
    return {
        "project_id": "project1",
        "annotation_format_version": "1.2.0",
        "task_id": task_id,
        "task_phase": "annotation",
        "task_phase_stage": 1,
        "task_status": "working",
        "input_data_id": "input1",
        "input_data_name": "input1.jpg",
        "details": details,
        "updated_datetime": "2026-05-22T00:00:00.000+09:00",
    }


def _write_annotation(annotation_dir: Path, simple_annotation: dict) -> Path:
    json_file = annotation_dir / simple_annotation["task_id"] / "input1.json"
    json_file.parent.mkdir(parents=True)
    json_file.write_text(json.dumps(simple_annotation, ensure_ascii=False), encoding="utf-8")
    return annotation_dir


def _bbox_detail(annotation_id: str, left: int, top: int, right: int, bottom: int, *, label: str = "car", attributes: dict | None = None) -> dict:
    return {
        "label": label,
        "annotation_id": annotation_id,
        "data": {
            "_type": "BoundingBox",
            "left_top": {"x": left, "y": top},
            "right_bottom": {"x": right, "y": bottom},
        },
        "attributes": attributes if attributes is not None else {},
    }


class TestCreateAnnotationZipDiff:
    def test__create_annotation_zip_diff__added_deleted_changed_unchanged(self, tmp_path: Path):
        left_dir = _write_annotation(
            tmp_path / "left",
            _create_simple_annotation(
                [
                    _bbox_detail("changed", 0, 0, 10, 10, attributes={"occluded": False}),
                    _bbox_detail("deleted", 20, 20, 40, 40),
                    _bbox_detail("unchanged", 50, 50, 80, 80),
                ]
            ),
        )
        right_dir = _write_annotation(
            tmp_path / "right",
            _create_simple_annotation(
                [
                    _bbox_detail("changed", 0, 0, 20, 10, attributes={"occluded": True}),
                    _bbox_detail("added", 100, 100, 120, 130),
                    _bbox_detail("unchanged", 50, 50, 80, 80),
                ]
            ),
        )

        diff = create_annotation_zip_diff(left_dir, right_dir, annotation_type="bounding_box")

        summary_df = create_summary_df(diff)
        assert summary_df.to_dict("records") == [
            {
                "project_id": "project1",
                "task_id": "task1",
                "input_data_id": "input1",
                "annotation_type": "bounding_box",
                "left_annotation_count": 3,
                "right_annotation_count": 3,
                "added_count": 1,
                "deleted_count": 1,
                "changed_count": 1,
                "unchanged_count": 1,
            }
        ]

        detail_df = create_detail_df(diff, annotation_type="bounding_box")
        assert list(detail_df["diff_type"]) == ["added", "changed", "deleted"]

        changed_row = detail_df[detail_df["annotation_id"] == "changed"].iloc[0].to_dict()
        assert changed_row["label_changed"] is False
        assert changed_row["attributes_changed"] is True
        assert changed_row["data_changed"] is True
        assert changed_row["changed_attribute_keys"] == '["occluded"]'
        assert changed_row["iou"] == pytest.approx(0.5)
        assert changed_row["center_distance"] == pytest.approx(5.0)
        assert changed_row["area_change_ratio"] == pytest.approx(1.0)

    def test__create_annotation_zip_diff__include_unchanged(self, tmp_path: Path):
        left_dir = _write_annotation(tmp_path / "left", _create_simple_annotation([_bbox_detail("same", 0, 0, 10, 10)]))
        right_dir = _write_annotation(tmp_path / "right", _create_simple_annotation([_bbox_detail("same", 0, 0, 10, 10)]))

        diff = create_annotation_zip_diff(left_dir, right_dir, annotation_type="bounding_box", include_unchanged=True)

        assert [detail.diff_type for detail in diff.details] == ["unchanged"]

    def test__create_annotation_zip_diff__json_can_compare_multiple_annotation_types(self, tmp_path: Path):
        left_dir = _write_annotation(
            tmp_path / "left",
            _create_simple_annotation(
                [
                    _bbox_detail("bbox", 0, 0, 10, 10),
                    {
                        "label": "eye",
                        "annotation_id": "point",
                        "data": {"_type": "SinglePoint", "point": {"x": 1, "y": 2}},
                        "attributes": {},
                    },
                ]
            ),
        )
        right_dir = _write_annotation(
            tmp_path / "right",
            _create_simple_annotation(
                [
                    _bbox_detail("bbox", 0, 0, 20, 10),
                    {
                        "label": "eye",
                        "annotation_id": "point",
                        "data": {"_type": "SinglePoint", "point": {"x": 4, "y": 6}},
                        "attributes": {},
                    },
                ]
            ),
        )

        diff = create_annotation_zip_diff(left_dir, right_dir)

        assert {detail.annotation_type for detail in diff.details} == {"bounding_box", "single_point"}

    def test__create_annotation_zip_diff__target_task_ids(self, tmp_path: Path):
        left_dir = _write_annotation(tmp_path / "left", _create_simple_annotation([_bbox_detail("task1-annotation", 0, 0, 10, 10)], task_id="task1"))
        _write_annotation(left_dir, _create_simple_annotation([_bbox_detail("task2-annotation", 0, 0, 10, 10)], task_id="task2"))
        right_dir = _write_annotation(tmp_path / "right", _create_simple_annotation([_bbox_detail("task1-annotation", 0, 0, 20, 10)], task_id="task1"))
        _write_annotation(right_dir, _create_simple_annotation([_bbox_detail("task2-annotation", 0, 0, 20, 10)], task_id="task2"))

        diff = create_annotation_zip_diff(left_dir, right_dir, annotation_type="bounding_box", target_task_ids=["task2"])

        assert [summary.task_id for summary in diff.summary] == ["task2"]
        assert [detail.task_id for detail in diff.details] == ["task2"]


class TestCommandLine:
    def test__annotation_zip_diff(self, tmp_path: Path):
        left_dir = _write_annotation(tmp_path / "left", _create_simple_annotation([_bbox_detail("same", 0, 0, 10, 10)]))
        right_dir = _write_annotation(tmp_path / "right", _create_simple_annotation([_bbox_detail("same", 0, 0, 20, 10)]))
        output_file = tmp_path / "diff.csv"

        main(
            [
                "annotation_zip",
                "diff",
                "--left_annotation",
                str(left_dir),
                "--right_annotation",
                str(right_dir),
                "--annotation_type",
                "bounding_box",
                "--task_id",
                "task1",
                "--format",
                "detail_csv",
                "--output",
                str(output_file),
            ]
        )

        assert output_file.exists()
