import pandas


def get_frequency_of_monthend() -> str:
    """
    "MonthEnd"を表すfrequencyコードを取得する。
    pandas2.2から"M"は非推奨になったので、pandas2.2以上ならば"ME"を返す。そうでなければ"M"を返す。

    https://github.com/pandas-dev/pandas/issues/9586
    """
    tmp = pandas.__version__.split(".")
    major = int(tmp[0])
    minor = int(tmp[1])

    # pandas 3.0以上、または pandas 2.2以上の場合は"ME"を返す
    if major >= 3 or (major == 2 and minor >= 2):
        return "ME"
    return "M"
