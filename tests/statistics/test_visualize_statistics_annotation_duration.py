"""
区間アノテーションの長さに関するテスト
"""

import pandas
import pytest

from annofabcli.statistics.visualization.dataframe.annotation_duration import AnnotationDuration
from annofabcli.statistics.visualization.dataframe.custom_production_volume import CustomProductionVolume
from annofabcli.statistics.visualization.model import ProductionVolumeColumn


def test_annotation_duration_stored_in_minutes() -> None:
    """
    AnnotationDuration が分単位でデータを格納することを確認するテスト
    """
    # テスト用のデータフレームを作成（分単位）
    test_data = {
        "project_id": ["project1", "project1", "project1"],
        "task_id": ["task1", "task2", "task3"],
        "annotation_duration_minute": [1.0, 2.0, 3.0],  # 1分, 2分, 3分
    }
    df = pandas.DataFrame(test_data)
    annotation_duration_obj = AnnotationDuration(df)

    # 検証
    assert "annotation_duration_minute" in annotation_duration_obj.df.columns
    assert "annotation_duration_second" not in annotation_duration_obj.df.columns
    assert annotation_duration_obj.df["annotation_duration_minute"].tolist() == [1.0, 2.0, 3.0]

    # ProductionVolumeColumnを作成
    annotation_duration_column = ProductionVolumeColumn(value="annotation_duration_minute", name="区間アノテーションの長さ（分）")
    custom_production_volume = CustomProductionVolume(annotation_duration_obj.df, custom_production_volume_list=[annotation_duration_column])

    # 検証
    assert len(custom_production_volume.custom_production_volume_list) == 1
    assert custom_production_volume.custom_production_volume_list[0].value == "annotation_duration_minute"
    assert custom_production_volume.custom_production_volume_list[0].name == "区間アノテーションの長さ（分）"


def test_annotation_duration_with_fractional_minutes() -> None:
    """
    小数点以下を含む分のデータが正しく扱われることを確認するテスト
    """
    # テスト用のデータフレームを作成（分単位）
    test_data = {
        "project_id": ["project1", "project1"],
        "task_id": ["task1", "task2"],
        "annotation_duration_minute": [1.5, 2.25],  # 1.5分, 2.25分
    }
    df = pandas.DataFrame(test_data)
    annotation_duration_obj = AnnotationDuration(df)

    # 検証
    assert annotation_duration_obj.df["annotation_duration_minute"].tolist() == pytest.approx([1.5, 2.25])
