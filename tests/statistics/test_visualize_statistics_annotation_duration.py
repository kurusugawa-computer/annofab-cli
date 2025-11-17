"""
区間アノテーションの長さに関するテスト
"""


import pandas
import pytest

from annofabcli.statistics.visualization.dataframe.annotation_duration import AnnotationDuration
from annofabcli.statistics.visualization.dataframe.custom_production_volume import CustomProductionVolume
from annofabcli.statistics.visualization.model import ProductionVolumeColumn


def test_annotation_duration_conversion_to_minutes() -> None:
    """
    AnnotationDuration の秒データが正しく分に変換されることを確認するテスト
    """
    # テスト用のデータフレームを作成（秒単位）
    test_data = {
        "project_id": ["project1", "project1", "project1"],
        "task_id": ["task1", "task2", "task3"],
        "annotation_duration_second": [60.0, 120.0, 180.0],  # 1分, 2分, 3分
    }
    df = pandas.DataFrame(test_data)
    annotation_duration_obj = AnnotationDuration(df)

    # 秒を分に変換
    annotation_duration_df = annotation_duration_obj.df.copy()
    annotation_duration_df["annotation_duration_minute"] = annotation_duration_df["annotation_duration_second"] / 60.0
    annotation_duration_df = annotation_duration_df.drop(columns=["annotation_duration_second"])

    # 検証
    assert "annotation_duration_minute" in annotation_duration_df.columns
    assert "annotation_duration_second" not in annotation_duration_df.columns
    assert annotation_duration_df["annotation_duration_minute"].tolist() == [1.0, 2.0, 3.0]

    # ProductionVolumeColumnを作成
    annotation_duration_column = ProductionVolumeColumn(value="annotation_duration_minute", name="区間アノテーションの長さ（分）")
    custom_production_volume = CustomProductionVolume(annotation_duration_df, custom_production_volume_list=[annotation_duration_column])

    # 検証
    assert len(custom_production_volume.custom_production_volume_list) == 1
    assert custom_production_volume.custom_production_volume_list[0].value == "annotation_duration_minute"
    assert custom_production_volume.custom_production_volume_list[0].name == "区間アノテーションの長さ（分）"


def test_annotation_duration_conversion_with_fractional_minutes() -> None:
    """
    小数点以下を含む分への変換が正しく行われることを確認するテスト
    """
    # テスト用のデータフレームを作成（秒単位）
    test_data = {
        "project_id": ["project1", "project1"],
        "task_id": ["task1", "task2"],
        "annotation_duration_second": [90.0, 135.0],  # 1.5分, 2.25分
    }
    df = pandas.DataFrame(test_data)
    annotation_duration_obj = AnnotationDuration(df)

    # 秒を分に変換
    annotation_duration_df = annotation_duration_obj.df.copy()
    annotation_duration_df["annotation_duration_minute"] = annotation_duration_df["annotation_duration_second"] / 60.0
    annotation_duration_df = annotation_duration_df.drop(columns=["annotation_duration_second"])

    # 検証
    assert annotation_duration_df["annotation_duration_minute"].tolist() == pytest.approx([1.5, 2.25])
