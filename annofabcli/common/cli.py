"""
Command Line Interfaceの共通部分
"""

import argparse
import getpass
import json
import logging
import os
import pkgutil
from pathlib import Path
from typing import Any, Optional

import annofabapi
import pandas
import requests
import yaml
from annofabapi.api import DEFAULT_ENDPOINT_URL
from annofabapi.exceptions import AnnofabApiException
from annofabapi.models import OrganizationMemberRole, ProjectMemberRole
from more_itertools import first_true

from annofabcli.common.enums import FormatArgument
from annofabcli.common.exceptions import AnnofabCliException, AuthenticationError
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.typing import InputDataSize
from annofabcli.common.utils import (
    get_file_scheme_path,
    print_according_to_format,
    print_csv,
    read_lines_except_blank_line,
)

logger = logging.getLogger(__name__)


class ExitCode:
    """
    BashのExit Codes
    https://tldp.org/LDP/abs/html/exitcodes.html
    """

    GENERAL_ERROR = 1
    """一般的なエラー全般"""
    MISUSE_OF_COMMAND = 2
    """コマンドの誤用"""


COMMAND_LINE_ERROR_STATUS_CODE = 2
"""コマンドラインエラーが発生したときに返すステータスコード"""

PARALLELISM_CHOICES = range(2, 5)
"""
`--parallelism`に指定できる値
AnnofabのRate Limit的に最大4並列なので（これ以上並列度を上げてもRate Limitにひっかかる）ので、2-4の範囲にしている。
"""


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
        return service  # noqa: TRY300

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == requests.codes.unauthorized:
            raise AuthenticationError(service.api.login_user_id) from e
        raise e  # noqa: TRY201


def add_parser(
    subparsers: Optional[argparse._SubParsersAction],
    command_name: str,
    command_help: str,
    description: Optional[str] = None,
    is_subcommand: bool = True,  # noqa: FBT001, FBT002
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
    GLOBAL_OPTIONAL_ARGUMENTS_TITLE = "global optional arguments"  # noqa: N806

    def create_parent_parser() -> argparse.ArgumentParser:
        """
        共通の引数セットを生成する。
        """
        parent_parser = argparse.ArgumentParser(add_help=False)
        group = parent_parser.add_argument_group(GLOBAL_OPTIONAL_ARGUMENTS_TITLE)

        group.add_argument("--yes", action="store_true", help="処理中に現れる問い合わせに対して、常に ``yes`` と回答します。")

        group.add_argument("--endpoint_url", type=str, help="Annofab WebAPIのエンドポイントを指定します。", default=DEFAULT_ENDPOINT_URL)

        group.add_argument("--annofab_user_id", type=str, help="Annofabにログインする際のユーザーID")
        group.add_argument("--annofab_password", type=str, help="Annofabにログインする際のパスワード")
        group.add_argument("--annofab_pat", type=str, help="Annofabにログインする際のパーソナルアクセストークン")

        group.add_argument(
            "--logdir",
            type=Path,
            default=".log",
            help="ログファイルを保存するディレクトリを指定します。",
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
    global_optional_argument_group = first_true(parser._action_groups, pred=lambda e: e.title == GLOBAL_OPTIONAL_ARGUMENTS_TITLE)  # noqa: SLF001
    if global_optional_argument_group is not None:
        # optional グループの 0番目が help なので取り出す
        help_action = parser._optionals._group_actions.pop(0)  # noqa: SLF001
        assert help_action.dest == "help"
        # global optional group の 先頭にhelpを追加
        global_optional_argument_group._group_actions.insert(0, help_action)  # noqa: SLF001
    return parser


def get_list_from_args(str_list: Optional[list[str]] = None) -> list[str]:
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


def get_json_from_args(target: Optional[str] = None) -> Any:  # noqa: ANN401
    """
    JSON形式をPythonオブジェクトに変換する。
    プレフィックスが`file://`ならば、ファイルパスとしてファイルを読み込み、Pythonオブジェクトを返す。
    """

    if target is None:
        return None

    path = get_file_scheme_path(target)
    if path is not None:
        with open(path, encoding="utf-8") as f:  # noqa: PTH123
            return json.load(f)
    else:
        return json.loads(target)


def get_input_data_size(str_input_data_size: str) -> Optional[InputDataSize]:
    """400x300を(400,300)に変換する"""
    splitted_list = str_input_data_size.split("x")
    if len(splitted_list) < 2:
        return None

    return (int(splitted_list[0]), int(splitted_list[1]))


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
    1. 環境変数`ANNOFAB_USER_ID` , `ANNOFAB_PASSWORD`
    2. `.netrc`ファイル

    認証情報を読み込めなかった場合は、標準入力からUser IDとパスワードを入力させる。

    Returns:
        annofabapi.Resourceインスタンス

    """
    endpoint_url = get_endpoint_url(args)
    if endpoint_url != DEFAULT_ENDPOINT_URL:
        logger.info(f"Annofab WebAPIのエンドポイントURL: {endpoint_url}")

    kwargs = {"endpoint_url": endpoint_url, "input_mfa_code_via_stdin": True}

    # コマンドライン引数からパーソナルアクセストークンが指定された場合
    if args.annofab_pat is not None:
        return annofabapi.build(pat=args.annofab_pat, **kwargs)  # type: ignore[arg-type]

    # コマンドライン引数からユーザーIDが指定された場合
    if args.annofab_user_id is not None:
        login_user_id: str = args.annofab_user_id
        if args.annofab_password is not None:
            return annofabapi.build(login_user_id, args.annofab_password, **kwargs)  # type: ignore[arg-type]
        else:
            # コマンドライン引数にパスワードが指定されなければ、標準入力からパスワードを取得する
            login_password = ""
            while login_password == "":
                login_password = getpass.getpass("Enter Annofab Password: ")
            return annofabapi.build(login_user_id, login_password, **kwargs)  # type: ignore[arg-type]

    # 環境変数から認証情報を取得する
    try:
        return annofabapi.build_from_env(**kwargs)  # type: ignore[arg-type]
    except AnnofabApiException:
        pass

    # .netrcファイルから認証情報を取得する
    try:
        return annofabapi.build_from_netrc(**kwargs)  # type: ignore[arg-type]
    except AnnofabApiException:
        pass

    # 標準入力から入力させる
    login_user_id = ""
    while login_user_id == "":
        login_user_id = input("Enter Annofab User ID: ")

    login_password = ""
    while login_password == "":
        login_password = getpass.getpass("Enter Annofab Password: ")

    return annofabapi.build(login_user_id, login_password, **kwargs)  # type: ignore[arg-type]


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


def prompt_yesnoall(msg: str) -> tuple[bool, bool]:
    """
    標準入力で yes, no, all(すべてyes)を選択できるようにする。
    Args:
        msg: 確認メッセージ

    Returns:
        Tuple[yesno, all_flag]. yesno:Trueならyes. all_flag: Trueならall.

    """
    while True:
        choice = input(f"{msg} [y/N/ALL] : ")
        if choice == "y":  # noqa: SIM116
            return True, False

        elif choice == "N":
            return False, False

        elif choice == "ALL":
            return True, True


class ArgumentParser:
    """
    共通のコマンドライン引数を追加するためのクラス
    """

    def __init__(self, parser: argparse.ArgumentParser) -> None:
        self.parser = parser

    def add_project_id(self, help_message: Optional[str] = None) -> None:
        """
        '--project_id` 引数を追加
        """
        if help_message is None:
            help_message = "対象のプロジェクトのproject_idを指定します。"

        self.parser.add_argument("-p", "--project_id", type=str, required=True, help=help_message)

    def add_task_id(self, *, required: bool = True, help_message: Optional[str] = None) -> None:
        """
        '--task_id` 引数を追加
        """
        if help_message is None:
            help_message = "対象のタスクのtask_idを指定します。" + " ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。"

        self.parser.add_argument("-t", "--task_id", type=str, required=required, nargs="+", help=help_message)

    def add_input_data_id(self, *, required: bool = True, help_message: Optional[str] = None) -> None:
        """
        '--input_data_id` 引数を追加
        """
        if help_message is None:
            help_message = "対象の入力データのinput_data_idを指定します。 ``file://`` を先頭に付けると、input_data_idの一覧が記載されたファイルを指定できます。"

        self.parser.add_argument("-i", "--input_data_id", type=str, required=required, nargs="+", help=help_message)

    def add_format(self, choices: list[FormatArgument], default: FormatArgument, help_message: Optional[str] = None) -> None:
        """
        '--format` 引数を追加
        """
        if help_message is None:
            help_message = "出力フォーマットを指定します。"

        self.parser.add_argument("-f", "--format", type=str, choices=[e.value for e in choices], default=default.value, help=help_message)

    def add_output(self, *, required: bool = False, help_message: Optional[str] = None) -> None:
        """
        '--output` 引数を追加
        """
        if help_message is None:
            help_message = "出力先のファイルパスを指定します。未指定の場合は、標準出力に出力されます。"

        self.parser.add_argument("-o", "--output", type=str, required=required, help=help_message)

    def add_task_query(self, *, required: bool = False, help_message: Optional[str] = None) -> None:
        if help_message is None:
            help_message = (
                "タスクを絞り込むためのクエリ条件をJSON形式で指定します。"
                " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。\n"
                "以下のキーを指定できます。\n\n"
                " * ``task_id``\n"
                " * ``phase``\n"
                " * ``phase_stage``\n"
                " * ``status``\n"
                " * ``user_id``\n"
                " * ``account_id``\n"
                " * ``no_user``"
            )
        self.parser.add_argument("-tq", "--task_query", type=str, required=required, help=help_message)


class CommandLineWithConfirm:
    """
    コマンドライン上でpromptを表示するときのクラス
    """

    def __init__(self, all_yes: bool = False) -> None:  # noqa: FBT001, FBT002
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


class CommandLineWithoutWebapi:
    """
    webapiにアクセスしないCLI用の抽象クラス
    """

    #: Trueならば、処理中に現れる問い合わせに対して、常に'yes'と回答したものとして処理する。
    all_yes: bool = False

    #: 出力先
    output: Optional[str] = None

    #: 出力フォーマット
    str_format: Optional[str] = None

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.process_common_args(args)

    def process_common_args(self, args: argparse.Namespace) -> None:
        """
        共通のコマンドライン引数を処理する。
        Args:
            args: コマンドライン引数
        """
        self.all_yes = args.yes
        if hasattr(args, "query"):
            self.query = args.query

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

    def print_csv(self, df: pandas.DataFrame) -> None:
        print_csv(df, output=self.output)

    def print_according_to_format(self, target: Any) -> None:  # noqa: ANN401
        print_according_to_format(target, format=FormatArgument(self.str_format), output=self.output)


class PrettyHelpFormatter(argparse.RawTextHelpFormatter, argparse.ArgumentDefaultsHelpFormatter):
    def _format_action(self, action: argparse.Action) -> str:
        # ヘルプメッセージを見やすくするために、引数と引数の説明の間に空行を入れる
        # https://qiita.com/yuji38kwmt/items/c7c4d487e3188afd781e 参照
        return super()._format_action(action) + "\n"

    def _get_help_string(self, action):  # noqa: ANN001, ANN202
        # 必須な引数には、引数の説明の後ろに"(required)"を付ける
        help = action.help  # noqa: A001 # pylint: disable=redefined-builtin
        if action.required:
            help += " (required)"  # noqa: A001

        # 不要なデフォルト値（--debug や オプショナルな引数）を表示させないようにする
        # super()._get_help_string の中身を、そのまま持ってきた。
        # https://qiita.com/yuji38kwmt/items/c7c4d487e3188afd781e 参照
        if "%(default)" not in action.help:  # noqa: SIM102
            if action.default is not argparse.SUPPRESS:
                defaulting_nargs = [argparse.OPTIONAL, argparse.ZERO_OR_MORE]
                if action.option_strings or action.nargs in defaulting_nargs:  # noqa: SIM102
                    # 以下の条件だけ、annofabcli独自の設定
                    if action.default is not None and not action.const:
                        help += " (default: %(default)s)"  # noqa: A001
        return help


class CommandLine(CommandLineWithoutWebapi):
    """
    CLI用のクラス
    """

    #: annofabapi.Resourceインスタンス
    service: annofabapi.Resource

    #: AnnofabApiFacadeインスタンス
    facade: AnnofabApiFacade

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace) -> None:
        self.service = service
        self.facade = facade
        super().__init__(args)

    def validate_project(
        self,
        project_id: str,
        project_member_roles: Optional[list[ProjectMemberRole]] = None,
        organization_member_roles: Optional[list[OrganizationMemberRole]] = None,
    ) -> None:
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
