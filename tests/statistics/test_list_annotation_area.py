from pathlib import Path

# ここから list_annotation_area.py のテスト
from annofabcli.statistics.list_annotation_area import get_annotation_area_info_list_from_annotation_path

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
