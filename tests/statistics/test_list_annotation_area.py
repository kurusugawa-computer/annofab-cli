from pathlib import Path

# ここから list_annotation_area.py のテスト
from annofabcli.statistics.list_annotation_area import (
    calculate_bounding_box_area,
    calculate_polygon_area,
    get_annotation_area_info_list_from_annotation_path,
)

output_dir = Path("./tests/out/statistics/list_annotation_count")
data_dir = Path("./tests/data/statistics/list_annotation_area")
output_dir.mkdir(exist_ok=True, parents=True)


def test__get_annotation_area_info_list_from_annotation_path():
    # テスト用のアノテーションファイルを作成
    annotation_area_info_list = get_annotation_area_info_list_from_annotation_path(data_dir / "annotation")
    assert len(annotation_area_info_list) == 4
    assert annotation_area_info_list[0].annotation_area == 1680
    # 1pxも塗られていないアノテーション
    assert annotation_area_info_list[2].annotation_area == 0


def test__calculate_polygon_area__triangle():
    """三角形のポリゴン面積計算テスト"""
    triangle_points = [
        {"x": 0, "y": 0},
        {"x": 10, "y": 0},
        {"x": 5, "y": 10},
    ]
    assert calculate_polygon_area(triangle_points) == 50


def test__calculate_polygon_area__invalid_points():
    """点が2個以下の無効なポリゴンのテスト"""
    invalid_points = [
        {"x": 0, "y": 0},
        {"x": 10, "y": 0},
    ]
    assert calculate_polygon_area(invalid_points) == 0


def test__calculate_bounding_box_area():
    """矩形面積計算のテスト（既存機能の確認）"""
    bounding_box_data = {
        "left_top": {"x": 0, "y": 0},
        "right_bottom": {"x": 10, "y": 5},
    }
    assert calculate_bounding_box_area(bounding_box_data) == 50
