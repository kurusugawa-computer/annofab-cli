from collections.abc import Iterable, Iterator
from itertools import islice


def batched[T](iterable: Iterable[T], size: int) -> Iterator[tuple[T, ...]]:
    """指定した件数ごとに要素をまとめて返す。"""
    if size < 1:
        raise ValueError("size must be at least one")

    iterator = iter(iterable)
    while batch := tuple(islice(iterator, size)):
        yield batch
