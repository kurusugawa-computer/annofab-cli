from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from collections import defaultdict
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal, cast

import pandas
from annofab_3dpc.annotation import CuboidAnnotationDetailDataV2, convert_annotation_detail_data
from pydantic import BaseModel, ConfigDict
from shapely.errors import ShapelyError
from shapely.geometry import Polygon

import annofabcli.common.cli
from annofabcli.common.annofab.annotation_zip import lazy_parse_simple_annotation_by_input_data
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE
from annofabcli.common.utils import print_csv, print_json

logger = logging.getLogger(__name__)

AnnotationType = Literal["bounding_box", "single_point", "polygon", "polyline", "range", "3d_bounding_box"]
DiffType = Literal["added", "deleted", "changed", "unchanged"]


class AnnotationZipDiffOutputFormat(Enum):
    """アノテーションZIP差分の出力フォーマット。"""

    SUMMARY_CSV = "summary_csv"
    DETAIL_CSV = "detail_csv"
    JSON = "json"
    PRETTY_JSON = "pretty_json"


ANNOTATION_TYPE_LIST: list[AnnotationType] = ["bounding_box", "single_point", "polygon", "polyline", "range", "3d_bounding_box"]

DATA_TYPE_DICT: dict[AnnotationType, str] = {
    "bounding_box": "BoundingBox",
    "single_point": "SinglePoint",
    "polygon": "Points",
    "polyline": "Points",
    "range": "Range",
    "3d_bounding_box": "Unknown",
}

SUMMARY_COLUMNS = [
    "project_id",
    "task_id",
    "input_data_id",
    "annotation_type",
    "left_annotation_count",
    "right_annotation_count",
    "added_count",
    "deleted_count",
    "changed_count",
    "unchanged_count",
]

DETAIL_BASE_COLUMNS = [
    "project_id",
    "task_id",
    "input_data_id",
    "input_data_name",
    "annotation_id",
    "annotation_type",
    "diff_type",
    "left_label",
    "right_label",
    "label_changed",
    "attributes_changed",
    "data_changed",
    "changed_attribute_keys",
]

DETAIL_METRIC_COLUMNS: dict[AnnotationType, list[str]] = {
    "bounding_box": ["iou", "center_distance", "area_change_ratio"],
    "single_point": ["point_distance", "x_diff", "y_diff"],
    "polygon": ["iou", "centroid_distance", "area_change_ratio", "point_count_diff"],
    "polyline": ["length_change_ratio", "start_point_distance", "end_point_distance", "midpoint_distance", "point_count_diff"],
    "range": ["begin_diff_second", "end_diff_second", "duration_change_ratio", "overlap_ratio"],
    "3d_bounding_box": ["center_distance", "size_change_ratio", "rotation_diff"],
}


@dataclass(frozen=True)
class AnnotationKey:
    """アノテーションを突き合わせるためのキー。"""

    project_id: str
    task_id: str
    input_data_id: str
    annotation_id: str


@dataclass(frozen=True)
class AnnotationItem:
    """差分計算対象のアノテーション。"""

    key: AnnotationKey
    input_data_name: str
    annotation_type: str
    label: str
    attributes: dict[str, Any]
    data: dict[str, Any]


class AnnotationDiffDetail(BaseModel):
    """アノテーション単位の差分。"""

    model_config = ConfigDict(frozen=True)

    project_id: str
    task_id: str
    input_data_id: str
    input_data_name: str
    annotation_id: str
    annotation_type: str
    diff_type: DiffType
    left_label: str | None
    right_label: str | None
    label_changed: bool | None
    attributes_changed: bool | None
    data_changed: bool | None
    changed_attribute_keys: list[str] | None
    metrics: dict[str, float | int | None]


class AnnotationDiffSummary(BaseModel):
    """入力データ単位の差分サマリ。"""

    model_config = ConfigDict(frozen=True)

    project_id: str
    task_id: str
    input_data_id: str
    annotation_type: str
    left_annotation_count: int
    right_annotation_count: int
    added_count: int
    deleted_count: int
    changed_count: int
    unchanged_count: int


class AnnotationZipDiff(BaseModel):
    """アノテーションZIP同士の差分。"""

    model_config = ConfigDict(frozen=True)

    summary: list[AnnotationDiffSummary]
    details: list[AnnotationDiffDetail]


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _euclidean_distance(left: Mapping[str, float | int], right: Mapping[str, float | int], *, keys: Collection[str]) -> float:
    return math.sqrt(sum((float(right[key]) - float(left[key])) ** 2 for key in keys))


def _change_ratio(left_value: float, right_value: float) -> float | None:
    if left_value == 0:
        return None
    return (right_value - left_value) / left_value


def _bounding_box_properties(data: Mapping[str, Any]) -> dict[str, Any]:
    left_top = data["left_top"]
    right_bottom = data["right_bottom"]
    min_x = min(left_top["x"], right_bottom["x"])
    max_x = max(left_top["x"], right_bottom["x"])
    min_y = min(left_top["y"], right_bottom["y"])
    max_y = max(left_top["y"], right_bottom["y"])
    width = max_x - min_x
    height = max_y - min_y
    return {
        "min_x": min_x,
        "max_x": max_x,
        "min_y": min_y,
        "max_y": max_y,
        "center": {"x": (min_x + max_x) / 2, "y": (min_y + max_y) / 2},
        "area": width * height,
    }


def _calculate_bbox_iou(left_data: Mapping[str, Any], right_data: Mapping[str, Any]) -> float | None:
    left = _bounding_box_properties(left_data)
    right = _bounding_box_properties(right_data)
    intersection_width = max(0, min(left["max_x"], right["max_x"]) - max(left["min_x"], right["min_x"]))
    intersection_height = max(0, min(left["max_y"], right["max_y"]) - max(left["min_y"], right["min_y"]))
    intersection_area = intersection_width * intersection_height
    union_area = left["area"] + right["area"] - intersection_area
    if union_area == 0:
        return None
    return intersection_area / union_area


def _polygon_from_points(data: Mapping[str, Any]) -> Polygon | None:
    points = data["points"]
    if len(points) < 3:
        return None

    try:
        return Polygon([(point["x"], point["y"]) for point in points])
    except (ValueError, ShapelyError):
        return None


def _calculate_polygon_iou(left_data: Mapping[str, Any], right_data: Mapping[str, Any]) -> float | None:
    left_polygon = _polygon_from_points(left_data)
    right_polygon = _polygon_from_points(right_data)
    if left_polygon is None or right_polygon is None:
        return None

    try:
        union_area = left_polygon.union(right_polygon).area
        if union_area == 0:
            return None
        return left_polygon.intersection(right_polygon).area / union_area
    except ShapelyError:
        return None


def _point_list_length(points: list[Mapping[str, float | int]]) -> float:
    length = 0.0
    for index in range(len(points) - 1):
        length += _euclidean_distance(points[index], points[index + 1], keys=["x", "y"])
    return length


def _point_list_center(points: list[Mapping[str, float | int]]) -> dict[str, float]:
    return {"x": sum(float(point["x"]) for point in points) / len(points), "y": sum(float(point["y"]) for point in points) / len(points)}


def _get_cuboid_data(data: Mapping[str, Any]) -> CuboidAnnotationDetailDataV2 | None:
    try:
        annotation_data = convert_annotation_detail_data(dict(data))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if isinstance(annotation_data, CuboidAnnotationDetailDataV2):
        return annotation_data
    return None


def _calculate_bounding_box_metrics(left_data: Mapping[str, Any], right_data: Mapping[str, Any]) -> dict[str, float | int | None]:
    left_bbox = _bounding_box_properties(left_data)
    right_bbox = _bounding_box_properties(right_data)
    return {
        "iou": _calculate_bbox_iou(left_data, right_data),
        "center_distance": _euclidean_distance(left_bbox["center"], right_bbox["center"], keys=["x", "y"]),
        "area_change_ratio": _change_ratio(left_bbox["area"], right_bbox["area"]),
    }


def _calculate_single_point_metrics(left_data: Mapping[str, Any], right_data: Mapping[str, Any]) -> dict[str, float | int | None]:
    left_point = left_data["point"]
    right_point = right_data["point"]
    return {
        "point_distance": _euclidean_distance(left_point, right_point, keys=["x", "y"]),
        "x_diff": right_point["x"] - left_point["x"],
        "y_diff": right_point["y"] - left_point["y"],
    }


def _calculate_polygon_metrics(left_data: Mapping[str, Any], right_data: Mapping[str, Any]) -> dict[str, float | int | None]:
    left_polygon = _polygon_from_points(left_data)
    right_polygon = _polygon_from_points(right_data)
    left_area = left_polygon.area if left_polygon is not None else 0
    right_area = right_polygon.area if right_polygon is not None else 0
    left_centroid = {"x": left_polygon.centroid.x, "y": left_polygon.centroid.y} if left_polygon is not None else None
    right_centroid = {"x": right_polygon.centroid.x, "y": right_polygon.centroid.y} if right_polygon is not None else None
    return {
        "iou": _calculate_polygon_iou(left_data, right_data),
        "centroid_distance": _euclidean_distance(left_centroid, right_centroid, keys=["x", "y"]) if left_centroid is not None and right_centroid is not None else None,
        "area_change_ratio": _change_ratio(left_area, right_area),
        "point_count_diff": len(right_data["points"]) - len(left_data["points"]),
    }


def _calculate_polyline_metrics(left_data: Mapping[str, Any], right_data: Mapping[str, Any]) -> dict[str, float | int | None]:
    left_points = left_data["points"]
    right_points = right_data["points"]
    left_length = _point_list_length(left_points)
    right_length = _point_list_length(right_points)
    return {
        "length_change_ratio": _change_ratio(left_length, right_length),
        "start_point_distance": _euclidean_distance(left_points[0], right_points[0], keys=["x", "y"]),
        "end_point_distance": _euclidean_distance(left_points[-1], right_points[-1], keys=["x", "y"]),
        "midpoint_distance": _euclidean_distance(_point_list_center(left_points), _point_list_center(right_points), keys=["x", "y"]),
        "point_count_diff": len(right_points) - len(left_points),
    }


def _calculate_range_metrics(left_data: Mapping[str, Any], right_data: Mapping[str, Any]) -> dict[str, float | int | None]:
    left_begin = left_data["begin"] / 1000
    left_end = left_data["end"] / 1000
    right_begin = right_data["begin"] / 1000
    right_end = right_data["end"] / 1000
    left_duration = left_end - left_begin
    right_duration = right_end - right_begin
    overlap_duration = max(0, min(left_end, right_end) - max(left_begin, right_begin))
    union_duration = max(left_end, right_end) - min(left_begin, right_begin)
    return {
        "begin_diff_second": right_begin - left_begin,
        "end_diff_second": right_end - left_end,
        "duration_change_ratio": _change_ratio(left_duration, right_duration),
        "overlap_ratio": overlap_duration / union_duration if union_duration != 0 else None,
    }


def _calculate_3d_bounding_box_metrics(left_data: Mapping[str, Any], right_data: Mapping[str, Any]) -> dict[str, float | int | None]:
    left_cuboid = _get_cuboid_data(left_data)
    right_cuboid = _get_cuboid_data(right_data)
    if left_cuboid is None or right_cuboid is None:
        return {}

    left_shape = left_cuboid.shape
    right_shape = right_cuboid.shape
    left_location = cast(Mapping[str, float | int], left_shape.location.to_dict())
    right_location = cast(Mapping[str, float | int], right_shape.location.to_dict())
    left_dimensions = left_shape.dimensions
    right_dimensions = right_shape.dimensions
    left_volume = left_dimensions.width * left_dimensions.height * left_dimensions.depth
    right_volume = right_dimensions.width * right_dimensions.height * right_dimensions.depth
    return {
        "center_distance": _euclidean_distance(left_location, right_location, keys=["x", "y", "z"]),
        "size_change_ratio": _change_ratio(left_volume, right_volume),
        "rotation_diff": right_shape.rotation.z - left_shape.rotation.z,
    }


def _calculate_metrics(annotation_type: str, left_data: Mapping[str, Any], right_data: Mapping[str, Any]) -> dict[str, float | int | None]:
    metric_function_dict = {
        "bounding_box": _calculate_bounding_box_metrics,
        "single_point": _calculate_single_point_metrics,
        "polygon": _calculate_polygon_metrics,
        "polyline": _calculate_polyline_metrics,
        "range": _calculate_range_metrics,
        "3d_bounding_box": _calculate_3d_bounding_box_metrics,
    }
    metric_function = metric_function_dict.get(annotation_type)
    if metric_function is None:
        return {}
    return metric_function(left_data, right_data)


def _get_annotation_type(data: Mapping[str, Any], annotation_type: AnnotationType | None) -> str | None:
    data_type = data.get("_type")
    if annotation_type is not None:
        expected_data_type = DATA_TYPE_DICT[annotation_type]
        if data_type != expected_data_type:
            return None
        if annotation_type == "3d_bounding_box" and _get_cuboid_data(data) is None:
            return None
        return annotation_type

    annotation_type_dict = {
        "BoundingBox": "bounding_box",
        "SinglePoint": "single_point",
        "Range": "range",
        "Points": "points",
    }
    if data_type in annotation_type_dict:
        return annotation_type_dict[data_type]
    if data_type == "Unknown" and _get_cuboid_data(data) is not None:
        return "3d_bounding_box"
    return None


def _load_annotation_items(annotation_path: Path, *, annotation_type: AnnotationType | None) -> dict[AnnotationKey, AnnotationItem]:
    logger.info(f"アノテーションZIPまたはディレクトリ'{annotation_path}'を読み込みます。")
    result: dict[AnnotationKey, AnnotationItem] = {}

    for index, parser in enumerate(lazy_parse_simple_annotation_by_input_data(annotation_path)):
        if (index + 1) % 10000 == 0:
            logger.info(f"{index + 1} 件目のJSONを読み込み中")

        simple_annotation = parser.load_json()
        for detail in simple_annotation["details"]:
            item_annotation_type = _get_annotation_type(detail["data"], annotation_type)
            if item_annotation_type is None:
                continue

            key = AnnotationKey(
                project_id=simple_annotation["project_id"],
                task_id=simple_annotation["task_id"],
                input_data_id=simple_annotation["input_data_id"],
                annotation_id=detail["annotation_id"],
            )
            if key in result:
                logger.warning(f"同じアノテーションIDが複数存在するため、後に読み込んだアノテーションで上書きします。 :: key='{key}'")

            result[key] = AnnotationItem(
                key=key,
                input_data_name=simple_annotation["input_data_name"],
                annotation_type=item_annotation_type,
                label=detail["label"],
                attributes=detail["attributes"],
                data=detail["data"],
            )

    return result


def _get_changed_attribute_keys(left_attributes: Mapping[str, Any], right_attributes: Mapping[str, Any]) -> list[str]:
    keys = set(left_attributes.keys()) | set(right_attributes.keys())
    return sorted(key for key in keys if left_attributes.get(key) != right_attributes.get(key))


def _create_diff_detail(key: AnnotationKey, left_item: AnnotationItem | None, right_item: AnnotationItem | None) -> AnnotationDiffDetail:
    base_item = right_item if right_item is not None else left_item
    assert base_item is not None

    if left_item is None:
        return AnnotationDiffDetail(
            project_id=key.project_id,
            task_id=key.task_id,
            input_data_id=key.input_data_id,
            input_data_name=base_item.input_data_name,
            annotation_id=key.annotation_id,
            annotation_type=base_item.annotation_type,
            diff_type="added",
            left_label=None,
            right_label=right_item.label if right_item is not None else None,
            label_changed=None,
            attributes_changed=None,
            data_changed=None,
            changed_attribute_keys=None,
            metrics={},
        )

    if right_item is None:
        return AnnotationDiffDetail(
            project_id=key.project_id,
            task_id=key.task_id,
            input_data_id=key.input_data_id,
            input_data_name=base_item.input_data_name,
            annotation_id=key.annotation_id,
            annotation_type=base_item.annotation_type,
            diff_type="deleted",
            left_label=left_item.label,
            right_label=None,
            label_changed=None,
            attributes_changed=None,
            data_changed=None,
            changed_attribute_keys=None,
            metrics={},
        )

    label_changed = left_item.label != right_item.label
    attributes_changed = left_item.attributes != right_item.attributes
    data_changed = _json_dumps(left_item.data) != _json_dumps(right_item.data)
    diff_type: DiffType = "changed" if label_changed or attributes_changed or data_changed else "unchanged"
    metrics = _calculate_metrics(left_item.annotation_type, left_item.data, right_item.data) if data_changed else {}

    return AnnotationDiffDetail(
        project_id=key.project_id,
        task_id=key.task_id,
        input_data_id=key.input_data_id,
        input_data_name=base_item.input_data_name,
        annotation_id=key.annotation_id,
        annotation_type=base_item.annotation_type,
        diff_type=diff_type,
        left_label=left_item.label,
        right_label=right_item.label,
        label_changed=label_changed,
        attributes_changed=attributes_changed,
        data_changed=data_changed,
        changed_attribute_keys=_get_changed_attribute_keys(left_item.attributes, right_item.attributes),
        metrics=metrics,
    )


def create_annotation_zip_diff(
    left_annotation_path: Path,
    right_annotation_path: Path,
    *,
    annotation_type: AnnotationType | None = None,
    include_unchanged: bool = False,
) -> AnnotationZipDiff:
    """2つのアノテーションZIPまたはディレクトリの差分を作成する。"""
    left_items = _load_annotation_items(left_annotation_path, annotation_type=annotation_type)
    right_items = _load_annotation_items(right_annotation_path, annotation_type=annotation_type)
    all_keys = sorted(set(left_items.keys()) | set(right_items.keys()), key=lambda key: (key.project_id, key.task_id, key.input_data_id, key.annotation_id))

    all_details = [_create_diff_detail(key, left_items.get(key), right_items.get(key)) for key in all_keys]
    details = [detail for detail in all_details if include_unchanged or detail.diff_type != "unchanged"]
    summary = _create_summary(all_details)
    return AnnotationZipDiff(summary=summary, details=details)


def _create_summary(details: Collection[AnnotationDiffDetail]) -> list[AnnotationDiffSummary]:
    counter: dict[tuple[str, str, str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for detail in details:
        key = (detail.project_id, detail.task_id, detail.input_data_id, detail.annotation_type)
        if detail.diff_type != "added":
            counter[key]["left_annotation_count"] += 1
        if detail.diff_type != "deleted":
            counter[key]["right_annotation_count"] += 1
        counter[key][f"{detail.diff_type}_count"] += 1

    result = []
    for key in sorted(counter.keys()):
        project_id, task_id, input_data_id, annotation_type = key
        value = counter[key]
        result.append(
            AnnotationDiffSummary(
                project_id=project_id,
                task_id=task_id,
                input_data_id=input_data_id,
                annotation_type=annotation_type,
                left_annotation_count=value["left_annotation_count"],
                right_annotation_count=value["right_annotation_count"],
                added_count=value["added_count"],
                deleted_count=value["deleted_count"],
                changed_count=value["changed_count"],
                unchanged_count=value["unchanged_count"],
            )
        )
    return result


def create_summary_df(diff: AnnotationZipDiff) -> pandas.DataFrame:
    """サマリCSV用のDataFrameを作成する。"""
    if len(diff.summary) == 0:
        return pandas.DataFrame(columns=SUMMARY_COLUMNS)
    return pandas.DataFrame([summary.model_dump() for summary in diff.summary], columns=SUMMARY_COLUMNS)


def create_detail_df(diff: AnnotationZipDiff, *, annotation_type: AnnotationType) -> pandas.DataFrame:
    """詳細CSV用のDataFrameを作成する。"""
    metric_columns = DETAIL_METRIC_COLUMNS[annotation_type]
    columns = DETAIL_BASE_COLUMNS + metric_columns
    if len(diff.details) == 0:
        return pandas.DataFrame(columns=columns)

    rows = []
    for detail in diff.details:
        row = detail.model_dump(exclude={"metrics"})
        row["changed_attribute_keys"] = _json_dumps(row["changed_attribute_keys"]) if row["changed_attribute_keys"] is not None else None
        row.update({metric_column: detail.metrics.get(metric_column) for metric_column in metric_columns})
        rows.append(row)
    return pandas.DataFrame(rows, columns=columns)


class AnnotationZipDiffCommand:
    """アノテーションZIPの差分を出力する。"""

    COMMON_MESSAGE = "annofabcli annotation_zip diff: error:"

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args

    def validate(self) -> bool:
        output_format = AnnotationZipDiffOutputFormat(self.args.format)
        if output_format in {AnnotationZipDiffOutputFormat.SUMMARY_CSV, AnnotationZipDiffOutputFormat.DETAIL_CSV} and self.args.annotation_type is None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --annotation_type: CSV形式で出力するときは '--annotation_type' を指定してください。",
                file=sys.stderr,
            )
            return False
        return True

    def main(self) -> None:
        if not self.validate():
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        output_format = AnnotationZipDiffOutputFormat(self.args.format)
        annotation_type = self.args.annotation_type
        diff = create_annotation_zip_diff(
            self.args.left_annotation,
            self.args.right_annotation,
            annotation_type=annotation_type,
            include_unchanged=self.args.include_unchanged,
        )

        if output_format == AnnotationZipDiffOutputFormat.SUMMARY_CSV:
            print_csv(create_summary_df(diff), self.args.output)
            return

        if output_format == AnnotationZipDiffOutputFormat.DETAIL_CSV:
            assert annotation_type is not None
            print_csv(create_detail_df(diff, annotation_type=annotation_type), self.args.output)
            return

        if output_format in {AnnotationZipDiffOutputFormat.JSON, AnnotationZipDiffOutputFormat.PRETTY_JSON}:
            print_json(
                diff.model_dump(),
                is_pretty=output_format == AnnotationZipDiffOutputFormat.PRETTY_JSON,
                output=self.args.output,
            )
            return

        raise RuntimeError(f"未対応の出力フォーマットです。 :: format='{self.args.format}'")


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--left_annotation", type=Path, required=True, help="比較元のアノテーションZIP、またはzipを展開したディレクトリを指定します。")
    parser.add_argument("--right_annotation", type=Path, required=True, help="比較先のアノテーションZIP、またはzipを展開したディレクトリを指定します。")
    parser.add_argument(
        "--annotation_type",
        choices=ANNOTATION_TYPE_LIST,
        help="比較対象のアノテーション種類を指定します。CSV形式で出力するときは指定してください。",
    )
    parser.add_argument("--include_unchanged", action="store_true", help="詳細出力に変更がないアノテーションも含めます。")
    parser.add_argument(
        "-f",
        "--format",
        choices=[e.value for e in AnnotationZipDiffOutputFormat],
        default=AnnotationZipDiffOutputFormat.SUMMARY_CSV.value,
        help="出力フォーマット",
    )
    parser.add_argument("--output", type=Path, help="出力先のファイルパス")
    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    AnnotationZipDiffCommand(args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "diff"
    subcommand_help = "アノテーションZIPの差分を出力します。"
    description = "2つのアノテーションZIPまたはzipを展開したディレクトリを比較して、アノテーションの追加、削除、変更を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
