import pandas


def get_frequency_of_monthend() -> str:
    """
    "MonthEnd"を表すfrequencyコードを取得する。
    pandas2.2から"M"は非推奨になったので、pandas2.2以上ならば"ME"を返す。そうでなければ"M"を返す。

    https://github.com/pandas-dev/pandas/issues/9586
    """
    major, minor, _ = pandas.__version__.split(".")
    if int(major) >= 2 and int(minor) >= 2:
        return "ME"
    return "M"
