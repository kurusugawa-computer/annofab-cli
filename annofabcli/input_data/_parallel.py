"""入力データコマンドのスレッド並列処理。"""

import copy
from collections.abc import Callable


def isolate_thread_call[T, R](func: Callable[[T], R]) -> Callable[[T], R]:
    """呼び出しごとに処理オブジェクトと引数を複製する関数を返す。

    APIクライアント、確認状態、バルク取得した入力データ情報などの可変データを
    スレッド間で共有せずに処理する。ログ設定は同じプロセス内で共有する。

    Args:
        func: スレッドで実行する関数。束縛メソッドやpartialの引数も複製する。

    Returns:
        関数と入力をまとめてdeepcopyしてから呼び出す関数。
    """

    def _call(item: T) -> R:
        worker_func, worker_item = copy.deepcopy((func, item))
        return worker_func(worker_item)

    return _call
