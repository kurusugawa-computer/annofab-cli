from collections.abc import Iterable, Iterator
from itertools import islice
from typing import TypeVar

T = TypeVar("T")


def batched(iterable: Iterable[T], size: int) -> Iterator[tuple[T, ...]]:
    """指定した件数ごとに要素をまとめて返す。"""
    if size < 1:
        raise ValueError("size must be at least one")

    iterator = iter(iterable)
    while batch := tuple(islice(iterator, size)):
        yield batch
