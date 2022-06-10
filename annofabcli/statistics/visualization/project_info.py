from dataclasses import dataclass

from dataclasses_json import DataClassJsonMixin

from annofabcli.statistics.database import Query


@dataclass
class ProjectInfo(DataClassJsonMixin):
    """統計情報を出力したプロジェクトの情報"""

    project_id: str
    project_title: str
    input_data_type: str
    """入力データの種類"""
    measurement_datetime: str
    """計測日時。（2004-04-01T12:00+09:00形式）"""
    query: Query
    """集計対象を絞り込むためのクエリ"""
