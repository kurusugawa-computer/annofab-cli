from dataclasses import dataclass

from dataclasses_json import dataclass_json


@dataclass_json
@dataclass(frozen=True)
class WaitOptions:
    """
    最新化ジョブが完了するまで待つときのオプション
    """
    interval: int
    """ジョブにアクセスする間隔[秒]"""

    max_tries: int
    """最大ジョブに何回アクセスするか"""
