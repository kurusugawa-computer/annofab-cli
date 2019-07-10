import json
import logging.config
import os
import pkgutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TypeVar  # pylint: disable=unused-import

import annofabapi
import pandas
import requests
import yaml

import annofabcli
from annofabcli.common.cli import build_annofabapi_resource
from annofabcli.common.exceptions import AnnofabCliException

logger = logging.getLogger(__name__)

T = TypeVar('T')  # Can be anything


def read_lines(filepath: str) -> List[str]:
    """ファイルを行単位で読み込む。改行コードを除く"""
    with open(filepath) as f:
        lines = f.readlines()
    return [e.rstrip('\r\n') for e in lines]


def read_lines_except_blank_line(filepath: str) -> List[str]:
    """ファイルを行単位で読み込む。ただし、改行コード、空行を除く"""
    lines = read_lines(filepath)
    return [line for line in lines if line != ""]


def _is_file_scheme(value: str):
    return value.startswith('file://')


def load_logging_config(log_dir: str, log_filename: str, logging_yaml_file: Optional[str] = None):
    """
    ログ設定ファイルを読み込み、loggingを設定する。

    Args:
        log_dir: ログの出力先
        log_filename: ログのファイル名
        logging_yaml_file: ログ設定ファイル。指定しない場合、`data/logging.yaml`を読み込む. 指定した場合、log_dir, log_filenameは無視する。

    """

    if logging_yaml_file is not None:
        if os.path.exists(logging_yaml_file):
            with open(logging_yaml_file, encoding='utf-8') as f:
                logging_config = yaml.safe_load(f)
                logging.config.dictConfig(logging_config)
        else:
            logger.warning(f"{logging_yaml_file} does not exist.")
            set_default_logger(log_dir, log_filename)

    else:
        set_default_logger(log_dir, log_filename)


def set_default_logger(log_dir: str = ".log", log_filename: str = "annofabcli.log"):
    """
    デフォルトのロガーを設定する。パッケージ内のlogging.yamlを読み込む。
    """
    data = pkgutil.get_data('annofabcli', 'data/logging.yaml')
    if data is None:
        logger.warning("annofabcli/data/logging.yaml が読み込めませんでした")
        raise AnnofabCliException("annofabcli/data/logging.yaml が読み込めませんでした")

    logging_config = yaml.safe_load(data.decode("utf-8"))

    log_filename = f"{str(log_dir)}/{log_filename}"
    logging_config["handlers"]["fileRotatingHandler"]["filename"] = log_filename
    Path(log_dir).mkdir(exist_ok=True, parents=True)

    logging.config.dictConfig(logging_config)


def build_annofabapi_resource_and_login() -> annofabapi.Resource:
    """
    annofabapi.Resourceインスタンスを生成する。

    Returns:
        annofabapi.Resourceインスタンス

    """

    service = build_annofabapi_resource()

    try:
        service.api.login()
        return service

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == requests.codes.unauthorized:
            raise annofabcli.exceptions.AuthenticationError(service.api.login_user_id)
        raise e


def duplicated_set(l: List[T]) -> Set[T]:
    """
    重複しているsetを返す
    Args:
        l: 確認するList

    Returns:
        重複しているset

    """
    return {x for x in set(l) if l.count(x) > 1}


def progress_msg(index: int, size: int):
    """
    `1/100件目`という進捗率を表示する
    """
    digit = len(str(size))
    str_format = f'{{:{digit}}} / {{:{digit}}} 件目'
    return str_format.format(index, size)


def output_string(target: str, output: Optional[str] = None):
    """
    ファイルパスが指定されていればファイルに、指定しなければ標準出力に出力する。

    Args:
        target:
        output:
    """
    if output is None:
        print(target)
    else:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        with open(output, mode='w', encoding='utf-8') as f:
            f.write(target)


def print_json(target: Any, output: Optional[str] = None):
    output_string(json.dumps(target, indent=2, ensure_ascii=False), output)


def print_csv(df: pandas.DataFrame, output: Optional[str] = None, to_csv_kwargs: Optional[Dict[str, Any]] = None):
    if output is None:
        df.to_csv(sys.stdout, **to_csv_kwargs)

    else:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output, **to_csv_kwargs)
