import pytest

from annofabcli.utils.iterables import batched


def test_batched() -> None:
    assert list(batched(range(5), 2)) == [(0, 1), (2, 3), (4,)]


def test_batched_empty_iterable() -> None:
    assert list(batched([], 2)) == []


def test_batched_with_invalid_size() -> None:
    with pytest.raises(ValueError):
        list(batched([1], 0))
