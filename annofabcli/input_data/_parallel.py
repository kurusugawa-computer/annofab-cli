"""入力データコマンドのスレッド並列処理。"""

import copy
from collections.abc import Callable, Mapping


def isolate_thread_call[T, R](func: Callable[..., R], *, get_input_data_id: Callable[[T], str], **bulk_data: Mapping[str, object]) -> Callable[[T], R]:
    """呼び出しごとに処理オブジェクトと引数を複製する関数を返す。

    バルク取得結果は対象IDのレコードだけに絞ってから複製する。
    APIクライアント、確認状態、入力データ情報などの可変データは
    スレッド間で共有せず、ログ設定は同じプロセス内で共有する。

    Args:
        func: スレッドで実行する関数。束縛メソッドやpartialの引数も複製する。
        get_input_data_id: 入力から処理対象の入力データIDを取得する関数。
        **bulk_data: 関数にキーワード引数として渡す、入力データIDをキーとするバルク取得結果。

    Returns:
        関数、入力、対象IDのレコードをまとめてdeepcopyしてから呼び出す関数。
    """

    def _call(item: T) -> R:
        input_data_id = get_input_data_id(item)
        kwargs = {name: {input_data_id: data[input_data_id]} if input_data_id in data else {} for name, data in bulk_data.items()}
        worker_func, worker_item, worker_kwargs = copy.deepcopy((func, item, kwargs))
        return worker_func(worker_item, **worker_kwargs)

    return _call
