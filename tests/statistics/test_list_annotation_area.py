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


def test__calculate_polygon_area():
    """ポリゴン面積計算のテスト"""
    # 正方形のテスト（面積100）
    square_data = {
        "points": [
            {"x": 0, "y": 0},
            {"x": 10, "y": 0},
            {"x": 10, "y": 10},
            {"x": 0, "y": 10},
        ]
    }
    assert calculate_polygon_area(square_data) == 100

    # 三角形のテスト（面積50）
    triangle_data = {
        "points": [
            {"x": 0, "y": 0},
            {"x": 10, "y": 0},
            {"x": 5, "y": 10},
        ]
    }
    assert calculate_polygon_area(triangle_data) == 50

    # 点が2個以下のテスト（面積0）
    invalid_data = {
        "points": [
            {"x": 0, "y": 0},
            {"x": 10, "y": 0},
        ]
    }
    assert calculate_polygon_area(invalid_data) == 0

    # 点が0個のテスト（面積0）
    empty_data = {"points": []}
    assert calculate_polygon_area(empty_data) == 0

    # pointsキーが存在しないテスト（面積0）  
    no_points_data = {}
    assert calculate_polygon_area(no_points_data) == 0


def test__calculate_bounding_box_area():
    """矩形面積計算のテスト（既存機能の確認）"""
    bounding_box_data = {
        "left_top": {"x": 0, "y": 0},
        "right_bottom": {"x": 10, "y": 5},
    }
    assert calculate_bounding_box_area(bounding_box_data) == 50
