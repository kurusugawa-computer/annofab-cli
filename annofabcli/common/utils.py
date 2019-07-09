import argparse
import getpass
import logging.config
import os
import pkgutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Set, Optional, TypeVar, Tuple  # pylint: disable=unused-import

import sys
import pandas
import annofabapi
import requests
import yaml
import json
from annofabapi.exceptions import AnnofabApiException

import annofabcli
from annofabcli.common.typing import InputDataSize

logger = logging.getLogger(__name__)

T = TypeVar('T')  # Can be anything

def create_parent_parser() -> argparse.ArgumentParser:
    """
    共通の引数セットを生成する。
    """
    parent_parser = argparse.ArgumentParser(add_help=False)
    group = parent_parser.add_argument_group("global optional arguments")

    group.add_argument('--yes', action="store_true", help="処理中に現れる問い合わせに対して、常に'yes'と回答します。")

    group.add_argument('--logdir', type=str, default=".log",
                       help="ログファイルを保存するディレクトリを指定します。指定しない場合は`.log`ディレクトリ'にログファイルが保存されます。")

    group.add_argument(
        "--logging_yaml", type=str, help="ロギグングの設定ファイル(YAML)を指定します。指定した場合、`--logdir`オプションは無視されます。"
        "指定しない場合、デフォルトのロギングが設定されます。"
        "設定ファイルの書き方は https://docs.python.org/ja/3/howto/logging.html 参照してください。")
    return parent_parser


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

def get_list_from_args(str_list: Optional[List[str]] = None) -> List[str]:
    """
    文字列のListのサイズが1で、プレフィックスが`file://`ならば、ファイルパスとしてファイルを読み込み、行をListとして返す。
    そうでなければ、引数の値をそのままかえす。
    ただしNoneの場合は空Listを変えす
    Listが1小
    """
    if str_list is None or len(str_list) == 0:
        return []

    if len(str_list) > 1:
        return str_list

    str_value = str_list[0]
    if str_value.startswith('file://'):
        path = str_value[len('file://'):]
        return read_lines_except_blank_line(path)
    else:
        return str_list

def get_json_from_args(target: Optional[str] = None) -> Any:
    """
    JSON形式をPythonオブジェクトに変換する。
    プレフィックスが`file://`ならば、ファイルパスとしてファイルを読み込み、Pythonオブジェクトを返す。
    """

    if target is None:
        return None

    if target.startswith('file://'):
        path = target[len('file://'):]
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    else:
        return json.loads(target)

def get_input_data_size(str_input_data_size: str) -> InputDataSize:
    """400x300を(400,300)に変換する"""
    splited_list = str_input_data_size.split("x")
    return (int(splited_list[0]), int(splited_list[1]))


def add_parser(subparsers: argparse._SubParsersAction, subcommand_name: str, subcommand_help: str,
               description: str, epilog: Optional[str] = None) -> argparse.ArgumentParser:
    """
    サブコマンド用にparserを追加する

    Args:
        subparsers:
        subcommand_name:
        subcommand_help:
        description:
        epilog:

    Returns:
        サブコマンドのparser

    """
    return subparsers.add_parser(subcommand_name, parents=[create_parent_parser()], description=description,
                                 help=subcommand_help, epilog=epilog)


def load_logging_config_from_args(args: argparse.Namespace, py_filepath: str):
    """
    args情報から、logging設定ファイルを読み込む
    Args:
        args: Command引数情報
        py_filepath: Python Filepath. この名前を元にログファイル名が決まる。
    """
    log_dir = args.logdir
    logging_yaml_file = args.logging_yaml if hasattr(args, "logging_yaml") else None

    log_filename = f"{os.path.basename(py_filepath)}.log"
    load_logging_config(log_dir, log_filename, logging_yaml_file)


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
        else:
            logger.warning(f"{logging_yaml_file} does not exist.")

    else:
        _set_default_logger(log_dir, log_filename)


    if logging_yaml_file is not None and os.path.exists(logging_yaml_file):
        with open(logging_yaml_file, encoding='utf-8') as f:
            logging_config = yaml.safe_load(f)

    else:
        data = pkgutil.get_data('annofabcli', 'data/logging.yaml')
        if data is None:
            logger.warning("data/logging.yaml が読み込めませんでした")
            return

        logging_config = yaml.safe_load(data.decode("utf-8"))
        log_filename = f"{str(log_dir)}/{log_filename}"
        logging_config["handlers"]["fileRotatingHandler"]["filename"] = log_filename
        Path(log_dir).mkdir(exist_ok=True, parents=True)

    logging.config.dictConfig(logging_config)


def _set_default_logger(log_dir:str, log_filename):
    """
    デフォルトのロガーを設定する。パッケージ内のlogging.yamlを読み込む。
    """
    data = pkgutil.get_data('annofabcli', 'data/logging.yaml')
    if data is None:
        logger.warning("data/logging.yaml が読み込めませんでした")
        return

    logging_config = yaml.safe_load(data.decode("utf-8"))

    log_filename = f"{str(log_dir)}/{log_filename}"
    logging_config["handlers"]["fileRotatingHandler"]["filename"] = log_filename
    Path(log_dir).mkdir(exist_ok=True, parents=True)

    logging.config.dictConfig(logging_config)


def build_annofabapi_resource() -> annofabapi.Resource:
    """
    annofabapi.Resourceインスタナスを生成する。
    以下の順にAnnoFabの認証情報を読み込む。
    1. `.netrc`ファイル
    2. 環境変数`ANNOFAB_USER_ID` , `ANNOFAB_PASSWORD`

    認証情報を読み込めなかった場合は、標準入力からUser IDとパスワードを入力させる。

    Returns:
        annofabapi.Resourceインスタンス

    """

    try:
        return annofabapi.build_from_netrc()
    except AnnofabApiException:
        logger.debug("`.netrc`ファイルにはAnnoFab認証情報が存在しなかった")

    try:
        return annofabapi.build_from_env()
    except AnnofabApiException:
        logger.debug("`環境変数`ANNOFAB_USER_ID` or  `ANNOFAB_PASSWORD`が空だった")

    # 標準入力から入力させる
    login_user_id = ""
    while login_user_id == "":
        login_user_id = input("Enter AnnoFab User ID: ")

    login_password = ""
    while login_password == "":
        login_password = getpass.getpass("Enter AnnoFab Password: ")

    return annofabapi.build(login_user_id, login_password)


def build_annofabapi_resource_and_login() -> annofabapi.Resource:
    """
    annofabapi.Resourceインスタナスを生成する。
    ログインできなければ、UnauthorizationErrorをraiseする。

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
        else:
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

def progress_msg(index:int, size: int):
    """
    `1/100件目`という進捗率を表示する
    """
    digit = len(str(size))
    str_format = f'{{:{digit}}} / {{:{digit}}} 件目'
    return str_format.format(index, size)


def prompt_yesno(msg: str) -> Tuple[bool, bool]:
    """
    標準入力で yes, no, all(すべてyes)を選択できるようにする。
    Args:
        msg: 確認メッセージ

    Returns:
        Tuple[yesno, allflag]. yesno:Trueならyes. allflag: Trueならall.

    """
    while True:
        choice = input(f"{msg} [y/N/ALL] : ")
        if choice == 'y':
            return True, False

        elif choice == 'N':
            return False, False

        elif choice == 'ALL':
            return True, True



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
