"""
Command Line Interfaceの共通部分
"""

import abc
import argparse
import getpass
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple  # pylint: disable=unused-import

import annofabapi
from annofabapi.exceptions import AnnofabApiException
from annofabapi.models import ProjectMemberRole  # pylint: disable=unused-import

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.exceptions import AuthorizationError
# TODO argsparser系のメソッドを作成する
from annofabcli.common.typing import InputDataSize
from annofabcli.common.utils import load_logging_config, logger, read_lines_except_blank_line


def add_parser(subparsers: argparse._SubParsersAction, subcommand_name: str, subcommand_help: str, description: str,
               epilog: Optional[str] = None) -> argparse.ArgumentParser:
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


def get_csv_format_from_args(target: Optional[str] = None) -> Dict[str, Any]:
    """
    コマンドライン引数の値から csv_format を取得する。
    Default: {"encoding": "utf_8_sig", "index": True}

    """
    csv_format = {"encoding": "utf_8_sig", "index": True}
    if target is not None:
        arg_csv_format = get_json_from_args(target)
        csv_format.update(arg_csv_format)

    return csv_format


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
        logger.info("`.netrc`ファイルにはAnnoFab認証情報が存在しなかった")

    try:
        return annofabapi.build_from_env()
    except AnnofabApiException:
        logger.info("`環境変数`ANNOFAB_USER_ID` or  `ANNOFAB_PASSWORD`が空だった")

    # 標準入力から入力させる
    login_user_id = ""
    while login_user_id == "":
        login_user_id = input("Enter AnnoFab User ID: ")

    login_password = ""
    while login_password == "":
        login_password = getpass.getpass("Enter AnnoFab Password: ")

    return annofabapi.build(login_user_id, login_password)


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


class AbstractCommandLineInterface(abc.ABC):
    """
    CLI用の抽象クラス
    """

    #: annofabapi.Resourceインスタンス
    service: annofabapi.Resource

    #: AnnofabApiFacadeインスタンス
    facade: annofabcli.AnnofabApiFacade

    #: Trueならば、処理中に現れる問い合わせに対して、常に'yes'と回答したものとして処理する。
    all_yes: bool = False

    #: サブコマンドpyファイルで設定されたlogger
    logger: logging.Logger

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade):
        self.service = service
        self.facade = facade

    def process_common_args(self, args: argparse.Namespace, py_filepath: str, logger: logging.Logger):
        """
        共通のコマンドライン引数を処理する。
        Args:
            args: コマンドライン引数
            py_filepath: Python Filepath. この名前を元にログファイル名が決まる。


        """
        self.logger = logger
        load_logging_config_from_args(args, py_filepath)
        self.all_yes = args.yes

        logger.info(f"args: {args}")

    @abc.abstractmethod
    def main(self, args: argparse.Namespace):
        pass

    def validate_project(self, project_id, roles: List[ProjectMemberRole]):
        """
        プロジェクトに対する権限が付与されているかを確認する。
        Args:
            project_id:　
            roles: Roleの一覧。

        Raises:
             AuthorizationError: 自分自身のRoleがいずれかのRoleにも合致しなければ、AuthorizationErrorが発生する。

        """
        project_title = self.facade.get_project_title(project_id)
        self.logger.info(f"project_title = {project_title}, project_id = {project_id}")

        if not self.facade.contains_anys_role(project_id, roles):
            raise AuthorizationError(project_title, roles)

    def confirm_processing_task(self, task_id: str, confirm_message: str) -> bool:
        """
        タスクに対して処理するかどうか問い合わせる。
        `all_yes`属性も設定する。

        Args:
            task_id: 処理するtask_id
            confirm_message: 確認メッセージ

        Returns:
            Trueならば対象のタスクを処理する。

        """
        if self.all_yes:
            return True

        yes, all_yes = prompt_yesno(confirm_message)

        if not yes:
            self.logger.info(f"task_id = {task_id} をスキップします。")
            return False

        if all_yes:
            self.all_yes = True

        return True
