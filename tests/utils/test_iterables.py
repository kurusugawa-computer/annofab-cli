import pytest

from annofabcli.utils.iterables import batched


def test_batched() -> None:
    actual = list(batched(range(5), 2))

    assert actual == [(0, 1), (2, 3), (4,)]


def test_batched_empty_iterable() -> None:
    actual = list(batched([], 2))

    assert actual == []


def test_batched_with_invalid_size() -> None:
    with pytest.raises(ValueError, match="size must be at least one"):
        list(batched([1], 0))
