from dataclasses import dataclass
from typing import Any, Dict

from dataclasses_json import DataClassJsonMixin


@dataclass(frozen=True)
class WaitOptions(DataClassJsonMixin):
    """
    最新化ジョブが完了するまで待つときのオプション
    """

    interval: int
    """ジョブにアクセスする間隔[秒]"""

    max_tries: int
    """最大ジョブに何回アクセスするか"""


@dataclass
class SimpleAnnotationDetail4Import(DataClassJsonMixin):
    """
    アノテーションインポート用の　``SimpleAnnotationDetail`` クラス。
    """

    label: str
    """アノテーション仕様のラベル名(英語)です。 """

    data: Dict[str, Any]
    """"""

    attributes: Dict[str, Any]
    """キーに属性の名前、値に各属性の値が入った辞書構造です。 """
