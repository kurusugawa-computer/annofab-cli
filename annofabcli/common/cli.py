"""
Command Line Interfaceの共通部分
"""

import abc
import argparse
import getpass
import json
import logging
from typing import Any, Dict, List, Optional, Tuple  # pylint: disable=unused-import

import annofabapi
import requests
from annofabapi.exceptions import AnnofabApiException
from annofabapi.models import ProjectMemberRole  # pylint: disable=unused-import

import annofabcli
from annofabcli.common.enums import FormatArgument
from annofabcli.common.exceptions import AuthorizationError
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.typing import InputDataSize

logger = logging.getLogger(__name__)


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

    group.add_argument('--disable_log', action="store_true", help="ログを無効にします。")

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
        return annofabcli.utils.read_lines_except_blank_line(path)
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


def load_logging_config_from_args(args: argparse.Namespace):
    """
    args情報から、logging設定ファイルを読み込む
    Args:
        args: Command引数情報
    """
    log_dir = args.logdir
    logging_yaml_file = args.logging_yaml if hasattr(args, "logging_yaml") else None

    annofabcli.utils.load_logging_config(log_dir, logging_yaml_file)


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


class ArgumentParser:
    """
    共通のコマンドライン引数を追加するためのクラス
    """
    def __init__(self, parser: argparse.ArgumentParser):
        self.parser = parser

    def add_project_id(self, help_message: Optional[str] = None):
        """
        '--project_id` 引数を追加
        """
        if help_message is None:
            help_message = '対象のプロジェクトのproject_idを指定します。'

        self.parser.add_argument('-p', '--project_id', type=str, required=True, help=help_message)

    def add_task_id(self, help_message: Optional[str] = None):
        """
        '--task_id` 引数を追加
        """
        if help_message is None:
            help_message = ('対象のタスクのtask_idを指定します。' '`file://`を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。')

        self.parser.add_argument('-t', '--task_id', type=str, required=True, nargs='+', help=help_message)

    def add_format(self, choices: List[FormatArgument], default: FormatArgument, help_message: Optional[str] = None):
        """
        '--format` 引数を追加
        """
        if help_message is None:
            help_message = (f'出力フォーマットを指定します。指定しない場合は、{default.value} フォーマットになります。')

        self.parser.add_argument('-f', '--format', type=str, choices=[e.value for e in choices], default=default.value,
                                 help=help_message)

    def add_csv_format(self, help_message: Optional[str] = None):
        """
        '--csv_format` 引数を追加
        """
        if help_message is None:
            help_message = (
                'CSVのフォーマットをJSON形式で指定します。`--format`が`csv`でないときは、このオプションは無視されます。'
                '`file://`を先頭に付けると、JSON形式のファイルを指定できます。'
                '指定した値は、[pandas.DataFrame.to_csv](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.to_csv.html) の引数として渡されます。'  # noqa: E501
            )

        self.parser.add_argument('--csv_format', type=str, help=help_message)

    def add_output(self, help_message: Optional[str] = None):
        """
        '--csv_format` 引数を追加
        """
        if help_message is None:
            help_message = '出力先のファイルパスを指定します。指定しない場合は、標準出力に出力されます。'

        self.parser.add_argument('-o', '--output', type=str, help=help_message)


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

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        self.service = service
        self.facade = facade
        self.args = args
        self.process_common_args(args)

    def process_common_args(self, args: argparse.Namespace):
        """
        共通のコマンドライン引数を処理する。
        Args:
            args: コマンドライン引数
        """
        if not args.disable_log:
            load_logging_config_from_args(args)

        self.all_yes = args.yes
        logger.info(f"args: {args}")

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
        logger.info(f"project_title = {project_title}, project_id = {project_id}")

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
            logger.info(f"task_id = {task_id} をスキップします。")
            return False

        if all_yes:
            self.all_yes = True

        return True
