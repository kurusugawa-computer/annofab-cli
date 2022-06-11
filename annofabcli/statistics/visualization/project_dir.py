from dataclasses import dataclass

from dataclasses_json import DataClassJsonMixin
from pathlib import Path
from annofabcli.statistics.database import Query
from annofabcli.statistics.visualization.dataframe.user_performance import UserPerformance, WholePerformance


class ProjectDir(DataClassJsonMixin):
    """``annofabcli statistics visualize``コマンドによって出力されたプロジェクトディレクトリ"""

    FILENAME_WHOLE_PERFORMANCE = "全体の生産性と品質.csv"

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir

    def read_whole_performance(self) -> WholePerformance:
        """`全体の生産性と品質.csv`を読み込む。"""
        return WholePerformance.from_csv(self.project_dir / self.FILENAME_WHOLE_PERFORMANCE)



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
