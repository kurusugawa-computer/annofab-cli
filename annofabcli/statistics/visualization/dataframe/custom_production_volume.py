from __future__ import annotations

import logging

import pandas

from annofabcli.statistics.visualization.model import ProductionVolumeColumn

logger = logging.getLogger(__name__)


class CustomProductionVolume:
    """
    ユーザー独自の生産量が格納されたDataFrameをラップしたクラスです。

    DataFrameは`project_id`,`task_id`のペアがユニークなキーです。
    """

    @property
    def columns(self) -> list[str]:
        return [
            "project_id",
            "task_id",
            *[e.value for e in self.custom_production_volume_list],
        ]

    def required_columns_exist(self, df: pandas.DataFrame) -> bool:
        """
        必須の列が存在するかどうかを返します。

        Returns:
            必須の列が存在するかどうか
        """
        return len(set(self.columns) - set(df.columns)) == 0

    def __init__(self, df: pandas.DataFrame, *, custom_production_volume_list: list[ProductionVolumeColumn]) -> None:
        self.custom_production_volume_list = custom_production_volume_list
        assert len(custom_production_volume_list) > 0
        if not self.required_columns_exist(df):
            raise ValueError(f"引数`df`には、{self.columns}の列が必要です。 :: {df.columns=}")
        self.df = df

    def is_empty(self) -> bool:
        """
        空のデータフレームを持つかどうかを返します。

        Returns:
            空のデータフレームを持つかどうか
        """
        return len(self.df) == 0

    @classmethod
    def empty(cls, *, custom_production_volume_list: list[ProductionVolumeColumn]) -> CustomProductionVolume:
        """空のデータフレームを持つインスタンスを生成します。"""

        df_dtype: dict[str, str] = {
            "project_id": "string",
            "task_id": "string",
        }
        columns = ["project_id", "task_id", *[e.value for e in custom_production_volume_list]]
        df = pandas.DataFrame(columns=columns).astype(df_dtype)
        return cls(df, custom_production_volume_list=custom_production_volume_list)
