"""
Command Line Interfaceの共通部分
"""
import abc
import argparse
import dataclasses
import getpass
import json
import logging
import os
import pkgutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import annofabapi
import jmespath
import pandas
import requests
import yaml
from annofabapi.api import DEFAULT_ENDPOINT_URL
from annofabapi.exceptions import AnnofabApiException
from annofabapi.models import OrganizationMemberRole, ProjectMemberRole
from more_itertools import first_true

from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.enums import FormatArgument
from annofabcli.common.exceptions import AnnofabCliException, AuthenticationError
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.typing import InputDataSize
from annofabcli.common.utils import (
    DEFAULT_CSV_FORMAT,
    get_file_scheme_path,
    print_according_to_format,
    print_csv,
    read_lines_except_blank_line,
)

logger = logging.getLogger(__name__)


COMMAND_LINE_ERROR_STATUS_CODE = 2
"""コマンドラインエラーが発生したときに返すステータスコード"""


def build_annofabapi_resource_and_login(args: argparse.Namespace) -> annofabapi.Resource:
    """
    annofabapi.Resourceインスタンスを生成したあと、ログインする。

    Args:
        args: コマンドライン引数の情報

    Returns:
        annofabapi.Resourceインスタンス

    """

    service = build_annofabapi_resource(args)

    try:
        service.api.login()
        return service

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == requests.codes.unauthorized:
            raise AuthenticationError(service.api.login_user_id) from e
        raise e


def add_parser(
    subparsers: Optional[argparse._SubParsersAction],
    command_name: str,
    command_help: str,
    description: Optional[str] = None,
    is_subcommand: bool = True,
    epilog: Optional[str] = None,
) -> argparse.ArgumentParser:
    """
    サブコマンド用にparserを追加する

    Args:
        subparsers:
        command_name:
        command_help: 1階層上のコマンドヘルプに表示される コマンドの説明（簡易的な説明）
        description: ヘルプ出力に表示される説明（詳細な説明）。未指定の場合は command_help と同じ値です。
        is_subcommand: サブコマンドかどうか. `annofabcli project`はコマンド、`annofabcli project list`はサブコマンドとみなす。
        epilog: ヘルプ出力後に表示される内容。デフォルトはNoneです。

    Returns:
        サブコマンドのparser

    """
    GLOBAL_OPTIONAL_ARGUMENTS_TITLE = "global optional arguments"

    def create_parent_parser() -> argparse.ArgumentParser:
        """
        共通の引数セットを生成する。
        """
        parent_parser = argparse.ArgumentParser(add_help=False)
        group = parent_parser.add_argument_group(GLOBAL_OPTIONAL_ARGUMENTS_TITLE)

        group.add_argument("--yes", action="store_true", help="処理中に現れる問い合わせに対して、常に ``yes`` と回答します。")

        group.add_argument(
            "--endpoint_url", type=str, help=f"Annofab WebAPIのエンドポイントを指定します。指定しない場合は ``{DEFAULT_ENDPOINT_URL}`` です。"
        )

        group.add_argument(
            "--logdir",
            type=Path,
            default=".log",
            help="ログファイルを保存するディレクトリを指定します。指定しない場合は ``.log`` ディレクトリ'にログファイルが保存されます。",
        )

        group.add_argument("--disable_log", action="store_true", help="ログを無効にします。")

        group.add_argument("--debug", action="store_true", help="HTTPリクエストの内容やレスポンスのステータスコードなど、デバッグ用のログが出力されます。")

        return parent_parser

    if subparsers is None:
        subparsers = argparse.ArgumentParser().add_subparsers()

    parents = [create_parent_parser()] if is_subcommand else []
    parser = subparsers.add_parser(
        command_name,
        parents=parents,
        description=description if description is not None else command_help,
        help=command_help,
        epilog=epilog,
        formatter_class=PrettyHelpFormatter,
    )
    parser.set_defaults(command_help=parser.print_help)

    # 引数グループに"global optional group"がある場合は、"--help"オプションをデフォルトの"optional"グループから、"global optional arguments"グループに移動する
    # https://ja.stackoverflow.com/a/57313/19524
    global_optional_argument_group = first_true(
        parser._action_groups, pred=lambda e: e.title == GLOBAL_OPTIONAL_ARGUMENTS_TITLE
    )
    if global_optional_argument_group is not None:
        # optional グループの 0番目が help なので取り出す
        help_action = parser._optionals._group_actions.pop(0)
        assert help_action.dest == "help"
        # global optional group の 先頭にhelpを追加
        global_optional_argument_group._group_actions.insert(0, help_action)
    return parser


def get_list_from_args(str_list: Optional[List[str]] = None) -> List[str]:
    """
    文字列のListのサイズが1で、プレフィックスが`file://`ならば、ファイルパスとしてファイルを読み込み、行をListとして返す。
    そうでなければ、引数の値をそのまま返す。
    ただしNoneの場合は空Listを返す。

    Args:
        str_list: コマンドライン引数で指定されたリスト、またはfileスキームのURL

    Returns:
        コマンドライン引数で指定されたリスト。
    """
    if str_list is None or len(str_list) == 0:
        return []

    if len(str_list) > 1:
        return str_list

    str_value = str_list[0]
    path = get_file_scheme_path(str_value)
    if path is not None:
        return read_lines_except_blank_line(path)
    else:
        return str_list


def get_csv_format_from_args(target: Optional[str] = None) -> Dict[str, Any]:
    """
    コマンドライン引数の値から csv_format を取得する。
    Default: {"encoding": "utf_8_sig", "index": False}

    """
    csv_format = DEFAULT_CSV_FORMAT.copy()
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

    path = get_file_scheme_path(target)
    if path is not None:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    else:
        return json.loads(target)


def get_input_data_size(str_input_data_size: str) -> Optional[InputDataSize]:
    """400x300を(400,300)に変換する"""
    splitted_list = str_input_data_size.split("x")
    if len(splitted_list) < 2:
        return None

    return (int(splitted_list[0]), int(splitted_list[1]))


def get_wait_options_from_args(
    dict_wait_options: Optional[Dict[str, Any]], default_wait_options: WaitOptions
) -> WaitOptions:
    """
    デフォルト値とマージして、wait_optionsを取得する。

    Args:
        dict_wait_options: dictのwait_options(コマンドラインから取得した値など）
        default_wait_options: デフォルトのwait_options

    Returns:
        デフォルト値とマージしたwait_options

    """
    if dict_wait_options is not None:
        dataclasses.asdict(default_wait_options)
        return WaitOptions.from_dict({**dataclasses.asdict(default_wait_options), **dict_wait_options})
    else:
        return default_wait_options


def load_logging_config_from_args(args: argparse.Namespace) -> None:
    """
    args情報から、logging設定ファイルを読み込む.
    以下のコマンドライン引数からlogging設定ファイルを読み込む。
    ``--disable_log`` が指定されている場合は、loggerを設定しない。

    * --logdir
    * --disable_log
    * --logging_yaml

    Args:
        args: Command引数情報
    """

    if args.disable_log:
        return

    data = pkgutil.get_data("annofabcli", "data/logging.yaml")
    if data is None:
        logger.warning("annofabcli/data/logging.yaml が読み込めませんでした")
        raise AnnofabCliException("annofabcli/data/logging.yaml が読み込めませんでした")

    logging_config = yaml.safe_load(data.decode("utf-8"))

    log_file = args.logdir / "annofabcli.log"
    log_file.parent.mkdir(exist_ok=True, parents=True)
    logging_config["handlers"]["fileRotatingHandler"]["filename"] = str(log_file)

    if args.debug:
        logging_config["loggers"]["annofabapi"]["level"] = "DEBUG"

    logging.config.dictConfig(logging_config)


def get_endpoint_url(args: argparse.Namespace) -> str:
    """
    Annofab WebAPIのエンドポイントURLを、以下の優先順位で取得する。

    1. コマンドライン引数 ``--endpoint_url``
    2. 環境変数 ``ANNOFAB_ENDPOINT_URL``

    取得できない場合は、デフォルトの ``https://annofab.com`` を返す。

    Args:
        args: コマンドライン引数情報

    Returns:
        Annofab WebAPIのエンドポイントURL

    """
    endpoint_url = args.endpoint_url
    if endpoint_url is not None:
        return endpoint_url

    endpoint_url = os.environ.get("ANNOFAB_ENDPOINT_URL")
    if endpoint_url is not None:
        return endpoint_url

    return DEFAULT_ENDPOINT_URL


def build_annofabapi_resource(args: argparse.Namespace) -> annofabapi.Resource:
    """
    annofabapi.Resourceインスタンスを生成する。
    以下の順にAnnofabの認証情報を読み込む。
    1. `.netrc`ファイル
    2. 環境変数`ANNOFAB_USER_ID` , `ANNOFAB_PASSWORD`

    認証情報を読み込めなかった場合は、標準入力からUser IDとパスワードを入力させる。

    Returns:
        annofabapi.Resourceインスタンス

    """
    endpoint_url = get_endpoint_url(args)
    if endpoint_url != DEFAULT_ENDPOINT_URL:
        logger.info(f"Annofab WebAPIのエンドポイントURL: {endpoint_url}")

    try:
        return annofabapi.build_from_netrc(endpoint_url)
    except AnnofabApiException:
        pass

    # 環境変数から認証情報を取得する
    try:
        return annofabapi.build_from_env(endpoint_url)
    except AnnofabApiException:
        pass

    # 標準入力から入力させる
    login_user_id = ""
    while login_user_id == "":
        login_user_id = input("Enter Annofab User ID: ")

    login_password = ""
    while login_password == "":
        login_password = getpass.getpass("Enter Annofab Password: ")

    return annofabapi.build(login_user_id, login_password, endpoint_url=endpoint_url)


def prompt_yesno(msg: str) -> bool:
    """
    標準入力で yes, noを選択できるようにする。
    Args:
        msg: 確認メッセージ

    Returns:
        True: Yes, False: No

    """
    while True:
        choice = input(f"{msg} [y/N] : ")
        if choice == "y":
            return True

        elif choice == "N":
            return False


def prompt_yesnoall(msg: str) -> Tuple[bool, bool]:
    """
    標準入力で yes, no, all(すべてyes)を選択できるようにする。
    Args:
        msg: 確認メッセージ

    Returns:
        Tuple[yesno, allflag]. yesno:Trueならyes. allflag: Trueならall.

    """
    while True:
        choice = input(f"{msg} [y/N/ALL] : ")
        if choice == "y":
            return True, False

        elif choice == "N":
            return False, False

        elif choice == "ALL":
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
            help_message = "対象のプロジェクトのproject_idを指定します。"

        self.parser.add_argument("-p", "--project_id", type=str, required=True, help=help_message)

    def add_task_id(self, required: bool = True, help_message: Optional[str] = None):
        """
        '--task_id` 引数を追加
        """
        if help_message is None:
            help_message = "対象のタスクのtask_idを指定します。" + " ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。"

        self.parser.add_argument("-t", "--task_id", type=str, required=required, nargs="+", help=help_message)

    def add_input_data_id(self, required: bool = True, help_message: Optional[str] = None):
        """
        '--input_data_id` 引数を追加
        """
        if help_message is None:
            help_message = "対象の入力データのinput_data_idを指定します。" + " ``file://`` を先頭に付けると、input_data_idの一覧が記載されたファイルを指定できます。"

        self.parser.add_argument("-i", "--input_data_id", type=str, required=required, nargs="+", help=help_message)

    def add_format(self, choices: List[FormatArgument], default: FormatArgument, help_message: Optional[str] = None):
        """
        '--format` 引数を追加
        """
        if help_message is None:
            help_message = f"出力フォーマットを指定します。指定しない場合は、{default.value} フォーマットになります。"

        self.parser.add_argument(
            "-f", "--format", type=str, choices=[e.value for e in choices], default=default.value, help=help_message
        )

    def add_csv_format(self, help_message: Optional[str] = None):
        """
        '--csv_format` 引数を追加
        """
        if help_message is None:
            help_message = (
                "CSVのフォーマットをJSON形式で指定します。 ``--format`` が ``csv`` でないときは、このオプションは無視されます。"
                " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
                "指定した値は、`pandas.DataFrame.to_csv <https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.to_csv.html>`_ の引数として渡されます。"  # noqa: E501
            )

        self.parser.add_argument("--csv_format", type=str, help=help_message)

    def add_output(self, required: bool = False, help_message: Optional[str] = None):
        """
        '--output` 引数を追加
        """
        if help_message is None:
            help_message = "出力先のファイルパスを指定します。指定しない場合は、標準出力に出力されます。"

        self.parser.add_argument("-o", "--output", type=str, required=required, help=help_message)

    def add_query(self, help_message: Optional[str] = None):
        """
        '--query` 引数を追加
        """
        if help_message is None:
            help_message = "JMESPath形式で指定します。出力結果の抽出や、出力内容の変更に利用できます。"

        self.parser.add_argument("-q", "--query", type=str, help=help_message)

    def add_task_query(self, required: bool = False, help_message: Optional[str] = None):
        if help_message is None:
            help_message = (
                "タスクを絞り込むためのクエリ条件をJSON形式で指定します。"
                " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
                "使用できるキーは、``task_id`` , ``phase`` , ``phase_stage`` , ``status`` , ``user_id`` ,"
                " ``account_id`` , ``no_user``  (bool値)  のみです。"
            )
        self.parser.add_argument("-tq", "--task_query", type=str, required=required, help=help_message)


class AbstractCommandLineWithConfirmInterface(abc.ABC):
    """
    コマンドライン上でpromptを表示するときのインターフェイス
    """

    def __init__(self, all_yes: bool = False):
        self.all_yes = all_yes

    def confirm_processing(self, confirm_message: str) -> bool:
        """
        `all_yes`属性を見て、処理するかどうかユーザに問い合わせる。
        "ALL"が入力されたら、`all_yes`属性をTrueにする

        Returns:
            True: Yes, False: No

        """
        if self.all_yes:
            return True
        yes, all_yes = prompt_yesnoall(confirm_message)
        if all_yes:
            self.all_yes = True
        return yes


class AbstractCommandLineWithoutWebapiInterface(abc.ABC):
    """
    webapiにアクセスしないCLI用の抽象クラス
    """

    #: Trueならば、処理中に現れる問い合わせに対して、常に'yes'と回答したものとして処理する。
    all_yes: bool = False

    #: JMesPath
    query: Optional[str] = None

    #: 出力先
    output: Optional[str] = None

    #: CSVのフォーマット
    csv_format: Optional[Dict[str, Any]] = None

    #: 出力フォーマット
    str_format: Optional[str] = None

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.process_common_args(args)

    def process_common_args(self, args: argparse.Namespace):
        """
        共通のコマンドライン引数を処理する。
        Args:
            args: コマンドライン引数
        """
        self.all_yes = args.yes
        if hasattr(args, "query"):
            self.query = args.query

        if hasattr(args, "csv_format"):
            self.csv_format = get_csv_format_from_args(args.csv_format)

        if hasattr(args, "output"):
            self.output = args.output

        if hasattr(args, "format"):
            self.str_format = args.format

    def confirm_processing(self, confirm_message: str) -> bool:
        """
        `all_yes`属性を見て、処理するかどうかユーザに問い合わせる。
        "ALL"が入力されたら、`all_yes`属性をTrueにする

        Args:
            task_id: 処理するtask_id
            confirm_message: 確認メッセージ

        Returns:
            True: Yes, False: No

        """
        if self.all_yes:
            return True

        yes, all_yes = prompt_yesnoall(confirm_message)

        if all_yes:
            self.all_yes = True

        return yes

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

        yes, all_yes = prompt_yesnoall(confirm_message)

        if not yes:
            logger.info(f"task_id = {task_id} をスキップします。")
            return False

        if all_yes:
            self.all_yes = True

        return True

    def search_with_jmespath_expression(self, target: Any) -> Any:
        """
        インスタンスで保持しているJMespath情報で、targetの中身を探す。
        Args:
            target: 検索対象

        Returns:
            JMesPathで検索した結果。``self.query`` がNoneなら引数 ``target`` を返す。

        """
        if self.query is not None:
            return jmespath.search(self.query, target)
        return target

    def print_csv(self, df: pandas.DataFrame):
        print_csv(df, output=self.output, to_csv_kwargs=self.csv_format)

    def print_according_to_format(self, target: Any):
        target = self.search_with_jmespath_expression(target)

        print_according_to_format(
            target, arg_format=FormatArgument(self.str_format), output=self.output, csv_format=self.csv_format
        )


class PrettyHelpFormatter(argparse.RawTextHelpFormatter, argparse.ArgumentDefaultsHelpFormatter):
    def _format_action(self, action: argparse.Action) -> str:
        # ヘルプメッセージを見やすくするために、引数と引数の説明の間に空行を入れる
        # https://qiita.com/yuji38kwmt/items/c7c4d487e3188afd781e 参照
        return super()._format_action(action) + "\n"

    def _get_help_string(self, action):
        # 必須な引数には、引数の説明の後ろに"(required)"を付ける
        help = action.help  # pylint: disable=redefined-builtin
        if action.required:
            help += " (required)"

        # 不要なデフォルト値（--debug や オプショナルな引数）を表示させないようにする
        # super()._get_help_string の中身を、そのまま持ってきた。
        # https://qiita.com/yuji38kwmt/items/c7c4d487e3188afd781e 参照
        if "%(default)" not in action.help:
            if action.default is not argparse.SUPPRESS:
                defaulting_nargs = [argparse.OPTIONAL, argparse.ZERO_OR_MORE]
                if action.option_strings or action.nargs in defaulting_nargs:
                    # 以下の条件だけ、annofabcli独自の設定
                    if action.default is not None and not action.const:
                        help += " (default: %(default)s)"
        return help


class AbstractCommandLineInterface(AbstractCommandLineWithoutWebapiInterface):
    """
    CLI用の抽象クラス
    """

    #: annofabapi.Resourceインスタンス
    service: annofabapi.Resource

    #: AnnofabApiFacadeインスタンス
    facade: AnnofabApiFacade

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        self.service = service
        self.facade = facade
        super().__init__(args)

    def validate_project(
        self,
        project_id: str,
        project_member_roles: Optional[List[ProjectMemberRole]] = None,
        organization_member_roles: Optional[List[OrganizationMemberRole]] = None,
    ):
        """
        プロジェクト or 組織に対して、必要な権限が付与されているかを確認する。

        Args:
            project_id:
            project_member_roles: プロジェクトメンバロールの一覧. Noneの場合はチェックしない。
            organization_member_roles: 組織メンバロールの一覧。Noneの場合はチェックしない。

        Raises:
             AuthorizationError: 自分自身のRoleがいずれかのRoleにも合致しなければ、AuthorizationErrorが発生する。

        """
        self.facade.validate_project(
            project_id=project_id,
            project_member_roles=project_member_roles,
            organization_member_roles=organization_member_roles,
        )
