import copy
import json
import logging
import logging.config
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar, Union

import dateutil.parser
import isodate
import pandas

from annofabcli.common.enums import FormatArgument

logger = logging.getLogger(__name__)

T = TypeVar("T")  # Can be anything


DEFAULT_CSV_FORMAT = {"encoding": "utf_8_sig", "index": False}


def read_lines(filepath: str) -> list[str]:
    """ファイルを行単位で読み込む。改行コードを除く"""
    # BOM付きUTF-8のファイルも読み込めるようにする
    # annofabcliが出力するCSVはデフォルトでBOM付きUTF-8。これを加工してannofabcliに読み込ませる場合もあるので、BOM付きUTF-8に対応させた
    with open(filepath, encoding="utf-8-sig") as f:  # noqa: PTH123
        lines = f.readlines()
    return [e.rstrip("\r\n") for e in lines]


def read_lines_except_blank_line(filepath: str) -> list[str]:
    """ファイルを行単位で読み込む。ただし、改行コード、空行を除く"""
    lines = read_lines(filepath)
    return [line for line in lines if line != ""]


def duplicated_set(target_list: list[T]) -> set[T]:
    """
    重複しているsetを返す
    Args:
        target_list: 確認するList

    Returns:
        重複しているset

    """
    return {x for x in set(target_list) if target_list.count(x) > 1}


def output_string(target: str, output: Optional[Union[str, Path]] = None) -> None:
    """
    文字列を出力する。

    Args:
        target: 出力対象の文字列
        output: 出力先。Noneなら標準出力に出力する。
    """
    if output is None:
        print(target)  # noqa: T201
    else:
        p_output = output if isinstance(output, Path) else Path(output)
        p_output.parent.mkdir(parents=True, exist_ok=True)
        with p_output.open(mode="w", encoding="utf_8") as f:
            f.write(target)
            logger.info(f"'{output}'を出力しました。")


def print_json(target: Any, is_pretty: bool = False, output: Optional[Union[str, Path]] = None) -> None:  # noqa: ANN401, FBT001, FBT002
    """
    JSONを出力する。

    Args:
        target: 出力対象のJSON
        is_pretty: 人が見やすいJSONを出力するか
        output: 出力先。Noneなら標準出力に出力する。

    """
    if is_pretty:
        output_string(json.dumps(target, indent=2, ensure_ascii=False), output)
    else:
        output_string(json.dumps(target, ensure_ascii=False), output)


def print_csv(df: pandas.DataFrame, output: Optional[Union[str, Path]] = None, to_csv_kwargs: Optional[dict[str, Any]] = None) -> None:
    if output is not None:
        Path(output).parent.mkdir(parents=True, exist_ok=True)

    path_or_buf = sys.stdout if output is None else str(output)

    kwargs = copy.deepcopy(DEFAULT_CSV_FORMAT)
    if to_csv_kwargs is None:
        df.to_csv(path_or_buf, **kwargs)
    else:
        kwargs.update(to_csv_kwargs)
        df.to_csv(path_or_buf, **kwargs)

    if output is not None:
        logger.info(f"'{output}'を出力しました。")


def print_id_list(id_list: list[Any], output: Optional[Union[str, Path]]) -> None:
    s = "\n".join(id_list)
    output_string(s, output)


def print_according_to_format(
    target: Any,  # noqa: ANN401
    format: FormatArgument,  # noqa: A002
    output: Optional[Union[str, Path]] = None,
) -> None:
    """
    コマンドライン引数 ``--format`` の値にしたがって、内容を出力する。

    Args:
        target: 出力する内容
        format: 出力フォーマット
        output: 出力先（オプション）


    """

    if format == FormatArgument.PRETTY_JSON:
        print_json(target, is_pretty=True, output=output)

    elif format == FormatArgument.JSON:
        print_json(target, is_pretty=False, output=output)

    elif format == FormatArgument.CSV:
        df = pandas.DataFrame(target)
        print_csv(df, output=output)

    elif format == FormatArgument.TASK_ID_LIST:
        task_id_list = [e["task_id"] for e in target]
        print_id_list(task_id_list, output)

    elif format == FormatArgument.PROJECT_ID_LIST:
        project_id_list = [e["project_id"] for e in target]
        print_id_list(project_id_list, output)

    elif format == FormatArgument.INPUT_DATA_ID_LIST:
        input_data_id_list = [e["input_data_id"] for e in target]
        print_id_list(input_data_id_list, output)

    elif format == FormatArgument.USER_ID_LIST:
        user_id_list = [e["user_id"] for e in target]
        print_id_list(user_id_list, output)

    elif format == FormatArgument.INSPECTION_ID_LIST:
        inspection_id_list = [e["inspection_id"] for e in target]
        print_id_list(inspection_id_list, output)


def to_filename(s: str) -> str:
    """
    文字列をファイル名に使えるよう変換する。ファイル名に使えない文字は"__"に変換する。
    Args:
        s:

    Returns:
        ファイル名用の文字列

    """
    return re.sub(r'[\\|/|:|?|.|"|<|>|\|]', "__", s)


def is_file_scheme(str_value: str) -> bool:
    """
    file schemaかどうか

    """
    return str_value.startswith("file://")


def get_file_scheme_path(str_value: str) -> Optional[str]:
    """
    file schemaのパスを取得する。file schemeでない場合は、Noneを返す

    """
    if is_file_scheme(str_value):
        return str_value[len("file://") :]
    else:
        return None


def isoduration_to_hour(duration: str) -> float:
    """
    ISO 8601 duration を 時間に変換する
    Args:
        duration (str): ISO 8601 Durationの文字

    Returns:
        変換後の時間。

    """
    return isodate.parse_duration(duration).total_seconds() / 3600


def datetime_to_date(str_datetime: str) -> str:
    """
    ISO8601形式の日時を日付に変換する

    Args:
        str_datetime: ISO8601の拡張形式（YYYY-MM-DDThh:mm:ss+09:00）

    Returns:
        日時(YYYY-MM-DD)
    """
    return str(dateutil.parser.parse(str_datetime).date())


def get_cache_dir() -> Path:
    """
    環境変数から、annofabcliのキャシュディレクトリを取得する。
    キャッシュホームディレクトリは環境変数 ``XDG_CACHE_HOME`` から取得する。デフォルトは ``$HOME/.cache``である。

    Returns:
        annofabcliのキャッシュディレクトリ

    """
    cache_home_dir = os.environ.get("XDG_CACHE_HOME")
    if cache_home_dir is None:
        cache_home_dir_path = Path.home() / ".cache"
    else:
        cache_home_dir_path = Path(cache_home_dir)

    return cache_home_dir_path / "annofabcli"


def read_multiheader_csv(csv_file: str, header_row_count: int = 2, **kwargs) -> pandas.DataFrame:  # noqa: ANN003
    """
    複数ヘッダ行のCSVを読み込む。その際、"Unnamed"の列名は空文字に変更する。

    Args:
        csv_file:
        header_row_count: ヘッダの行数。2以上を指定する。

    Returns:
        pandas.DataFrame

    """
    kwargs["header"] = list(range(header_row_count))
    df = pandas.read_csv(csv_file, **kwargs)
    for level in range(header_row_count):
        columns = df.columns.levels[level]
        rename_columns = {c: "" for c in columns if re.fullmatch(r"Unnamed: .*", c) is not None}
        df.rename(
            columns=rename_columns,
            level=level,
            inplace=True,
        )
    return df


def get_columns_with_priority(df: pandas.DataFrame, prior_columns: list[Any]) -> list[str]:
    """
    優先順位の高い列を先頭にした、列名リストを取得します。

    Args:
        df: 対象のpandas.DataFrame
        prior_columns: 優先順位の高い列名リスト

    Returns:
        列名リスト
    """
    # 存在しない列名を取り除く
    tmp_prior_columns = [c for c in prior_columns if c in df.columns]
    remained_columns = list(df.columns.difference(tmp_prior_columns))
    all_columns = tmp_prior_columns + remained_columns
    return all_columns


def _catch_exception(function: Callable[..., Any]) -> Callable[..., Any]:
    """
    Exceptionをキャッチしてログにstacktraceを出力する。
    """

    def wrapped(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        try:
            return function(*args, **kwargs)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(e)
            logger.exception(e)  # noqa: TRY401
            return None

    return wrapped


def add_dryrun_prefix(lgr: logging.Logger) -> None:
    """
    ログメッセージにDRYRUNというプレフィックスを付加する。
    """
    # オリジナルのハンドラーを持っているLoggerを探す
    parent = lgr
    while len(parent.handlers) == 0 and parent.parent is not None:
        parent = parent.parent

    # オリジナルのフォーマットを探す
    fmt_original = logging.BASIC_FORMAT
    for handler in parent.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.formatter is not None and handler.formatter._fmt is not None:  # noqa: SLF001
            fmt_original = handler.formatter._fmt  # noqa: SLF001

    log_formatter = logging.Formatter(fmt_original.replace("%(message)s", "[DRYRUN] %(message)s"))
    log_handler = logging.StreamHandler()
    log_handler.setFormatter(log_formatter)
    lgr.addHandler(log_handler)
    lgr.propagate = False
