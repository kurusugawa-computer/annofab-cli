from typing import Never


def assert_noreturn(x: Never) -> Never:
    """到達不能な分岐を表す。"""
    raise AssertionError(f"Invalid value: {x!r}")  # x!rは repr(x)と等価
