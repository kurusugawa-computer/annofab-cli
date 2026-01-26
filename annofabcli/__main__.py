from __future__ import annotations

import argparse
import copy
import logging
import sys

import pandas

import annofabcli.common.cli

logger = logging.getLogger(__name__)


def warn_pandas_copy_on_write() -> None:
    """
    pandas2.2以上ならば、Copy-on-Writeの警告を出す。
    pandas 3.0で予期しない挙動になるのを防ぐため。
    https://pandas.pydata.org/docs/user_guide/copy_on_write.html
    """
    tmp = pandas.__version__.split(".")
    major = tmp[0]
    minor = tmp[1]
    if int(major) >= 2 and int(minor) >= 2:
        pandas.options.mode.copy_on_write = "warn"


def mask_sensitive_value_in_argv(argv: list[str]) -> list[str]:
    """
    `argv`にセンシティブな情報が含まれている場合は、`***`に置き換える。
    """
    tmp_argv = copy.deepcopy(argv)
    for masked_option in ["--annofab_user_id", "--annofab_password", "--annofab_pat"]:
        try:
            start_index = 0
            # `--annofab_password a --annofab_password b`のように複数指定された場合でもマスクできるようにする
            while True:
                index = tmp_argv.index(masked_option, start_index)
                tmp_argv[index + 1] = "***"
                start_index = index + 2

        except ValueError:
            continue
    return tmp_argv


# サブコマンドの情報を定義（インポートなし）
SUBCOMMANDS = {
    "annotation": {
        "module": "annofabcli.annotation.subcommand_annotation",
        "help": "アノテーション関係のサブコマンド",
    },
    "annotation_specs": {
        "module": "annofabcli.annotation_specs.subcommand_annotation_specs",
        "help": "アノテーション仕様関係のサブコマンド",
    },
    "annotation_zip": {
        "module": "annofabcli.annotation_zip.subcommand_annotation_zip",
        "help": "アノテーションZIPに対する操作を行うサブコマンド",
    },
    "comment": {
        "module": "annofabcli.comment.subcommand_comment",
        "help": "コメント関係のサブコマンド",
    },
    "experimental": {
        "module": "annofabcli.experimental.subcommand_experimental",
        "help": "アルファ版のサブコマンド。予告なしに削除されたり、コマンドライン引数が変わったりします。",
    },
    "filesystem": {
        "module": "annofabcli.filesystem.subcommand_filesystem",
        "help": "ファイル操作関係（Web APIにアクセスしない）のサブコマンド",
    },
    "input_data": {
        "module": "annofabcli.input_data.subcommand_input_data",
        "help": "入力データ関係のサブコマンド",
    },
    "instruction": {
        "module": "annofabcli.instruction.subcommand_instruction",
        "help": "作業ガイド関係のサブコマンド",
    },
    "job": {
        "module": "annofabcli.job.subcommand_job",
        "help": "ジョブ関係のサブコマンド",
    },
    "my_account": {
        "module": "annofabcli.my_account.subcommand_my_account",
        "help": "自分のアカウント関係のサブコマンド",
    },
    "organization": {
        "module": "annofabcli.organization.subcommand_organization",
        "help": "組織関係のサブコマンド",
    },
    "organization_member": {
        "module": "annofabcli.organization_member.subcommand_organization_member",
        "help": "組織メンバ関係のサブコマンド",
    },
    "project": {
        "module": "annofabcli.project.subcommand_project",
        "help": "プロジェクト関係のサブコマンド",
    },
    "project_member": {
        "module": "annofabcli.project_member.subcommand_project_member",
        "help": "プロジェクトメンバ関係のサブコマンド",
    },
    "stat_visualization": {
        "module": "annofabcli.stat_visualization.subcommand_stat_visualization",
        "help": "`annofabcli statistics visualization` コマンドの出力結果を加工するサブコマンド（アルファ版）",
    },
    "statistics": {
        "module": "annofabcli.statistics.subcommand_statistics",
        "help": "統計関係のサブコマンド",
    },
    "supplementary": {
        "module": "annofabcli.supplementary.subcommand_supplementary",
        "help": "補助情報関係のサブコマンド",
    },
    "task": {
        "module": "annofabcli.task.subcommand_task",
        "help": "タスク関係のサブコマンド",
    },
    "task_count": {
        "module": "annofabcli.task_count.subcommand_task_count",
        "help": "タスク数関係のサブコマンド",
    },
    "task_history": {
        "module": "annofabcli.task_history.subcommand_task_history",
        "help": "タスク履歴関係のサブコマンド",
    },
    "task_history_event": {
        "module": "annofabcli.task_history_event.subcommand_task_history_event",
        "help": "タスク履歴イベント関係のサブコマンド。task_history_eventコマンドはベータ版です。予告なく変更される場合があります。",
    },
}


def create_parser_lazy() -> argparse.ArgumentParser:
    """
    遅延インポート版のパーサー作成。
    ヘルプ表示時は最小限の情報のみ表示し、実行時に必要なモジュールをインポートする。
    """
    import annofabcli  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="Command Line Interface for Annofab", formatter_class=annofabcli.common.cli.PrettyHelpFormatter)
    parser.add_argument("--version", action="version", version=f"annofabcli {annofabcli.__version__}")
    parser.set_defaults(command_help=parser.print_help)

    subparsers = parser.add_subparsers(dest="command_name")

    # サブコマンドの簡易登録（遅延ロード用）
    for cmd_name, cmd_info in SUBCOMMANDS.items():
        subparser = subparsers.add_parser(cmd_name, help=cmd_info["help"], add_help=False)
        # 実際のサブコマンドは実行時にロードする
        subparser.set_defaults(_lazy_module=cmd_info["module"], _lazy_command=cmd_name)

    return parser


def load_subcommand_parser(module_path: str) -> argparse.ArgumentParser:
    """
    指定されたサブコマンドのパーサーを遅延ロードする。
    """
    import importlib  # noqa: PLC0415

    # モジュールをインポート
    module = importlib.import_module(module_path)

    # 新しいパーサーを作成して、サブコマンドを追加
    import annofabcli  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="Command Line Interface for Annofab", formatter_class=annofabcli.common.cli.PrettyHelpFormatter)
    parser.add_argument("--version", action="version", version=f"annofabcli {annofabcli.__version__}")
    parser.set_defaults(command_help=parser.print_help)

    subparsers = parser.add_subparsers(dest="command_name")

    # 該当するサブコマンドのパーサーを追加
    module.add_parser(subparsers)

    return parser


def main(arguments: list[str] | None = None) -> None:
    """
    annofabcliコマンドのメイン処理
    注意： `deprecated`なツールは、サブコマンド化しない。

    Args:
        arguments: コマンドライン引数。テストコード用

    """
    warn_pandas_copy_on_write()

    # 引数の準備
    if arguments is None:
        argv = sys.argv[1:]
    else:
        argv = list(arguments)

    # ヘルプ表示のみの場合は遅延パーサーを使う
    if len(argv) == 0 or argv[0] in ["-h", "--help"]:
        parser = create_parser_lazy()
        args = parser.parse_args(argv)
        if hasattr(args, "command_help"):
            args.command_help()
        return

    # バージョン表示
    if argv[0] in ["--version"]:
        parser = create_parser_lazy()
        args = parser.parse_args(argv)
        return

    # サブコマンドが指定されている場合
    # まず遅延パーサーで解析して、どのサブコマンドか特定
    parser_lazy = create_parser_lazy()
    args_lazy, _remaining = parser_lazy.parse_known_args(argv)

    if hasattr(args_lazy, "_lazy_module"):
        # 実際のサブコマンドパーサーをロード
        parser = load_subcommand_parser(args_lazy._lazy_module)  # noqa: SLF001
        args = parser.parse_args(argv)

        if hasattr(args, "subcommand_func"):
            try:
                annofabcli.common.cli.load_logging_config_from_args(args)
                if arguments is None:
                    full_argv = sys.argv
                else:
                    full_argv = ["annofabcli", *list(arguments)]
                logger.info(f"argv={mask_sensitive_value_in_argv(full_argv)}")
                args.subcommand_func(args)
            except Exception as e:
                logger.exception(e)  # noqa: TRY401
                raise e  # noqa: TRY201
        else:
            # 未知のサブコマンドの場合はヘルプを表示
            args.command_help()
    else:
        # サブコマンドが見つからない場合
        parser_lazy.print_help()


def create_parser() -> argparse.ArgumentParser:
    """
    パーサーを作成する（後方互換性のため残している）。

    Note:
        この関数は遅延インポートを使用しないため、全サブコマンドをロードする。
        テストコードなどで使用されている可能性があるため、後方互換性のために残している。
    """
    import annofabcli  # noqa: PLC0415
    import annofabcli.annotation.subcommand_annotation  # noqa: PLC0415
    import annofabcli.annotation_specs.subcommand_annotation_specs  # noqa: PLC0415
    import annofabcli.annotation_zip.subcommand_annotation_zip  # noqa: PLC0415
    import annofabcli.comment.subcommand_comment  # noqa: PLC0415
    import annofabcli.experimental.subcommand_experimental  # noqa: PLC0415
    import annofabcli.filesystem.subcommand_filesystem  # noqa: PLC0415
    import annofabcli.input_data.subcommand_input_data  # noqa: PLC0415
    import annofabcli.instruction.subcommand_instruction  # noqa: PLC0415
    import annofabcli.job.subcommand_job  # noqa: PLC0415
    import annofabcli.my_account.subcommand_my_account  # noqa: PLC0415
    import annofabcli.organization.subcommand_organization  # noqa: PLC0415
    import annofabcli.organization_member.subcommand_organization_member  # noqa: PLC0415
    import annofabcli.project.subcommand_project  # noqa: PLC0415
    import annofabcli.project_member.subcommand_project_member  # noqa: PLC0415
    import annofabcli.stat_visualization.subcommand_stat_visualization  # noqa: PLC0415
    import annofabcli.statistics.subcommand_statistics  # noqa: PLC0415
    import annofabcli.supplementary.subcommand_supplementary  # noqa: PLC0415
    import annofabcli.task.subcommand_task  # noqa: PLC0415
    import annofabcli.task_count.subcommand_task_count  # noqa: PLC0415
    import annofabcli.task_history.subcommand_task_history  # noqa: PLC0415
    import annofabcli.task_history_event.subcommand_task_history_event  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="Command Line Interface for Annofab", formatter_class=annofabcli.common.cli.PrettyHelpFormatter)
    parser.add_argument("--version", action="version", version=f"annofabcli {annofabcli.__version__}")
    parser.set_defaults(command_help=parser.print_help)

    subparsers = parser.add_subparsers(dest="command_name")

    annofabcli.annotation.subcommand_annotation.add_parser(subparsers)
    annofabcli.annotation_specs.subcommand_annotation_specs.add_parser(subparsers)
    annofabcli.annotation_zip.subcommand_annotation_zip.add_parser(subparsers)
    annofabcli.comment.subcommand_comment.add_parser(subparsers)
    annofabcli.input_data.subcommand_input_data.add_parser(subparsers)
    annofabcli.instruction.subcommand_instruction.add_parser(subparsers)
    annofabcli.job.subcommand_job.add_parser(subparsers)
    annofabcli.my_account.subcommand_my_account.add_parser(subparsers)
    annofabcli.organization.subcommand_organization.add_parser(subparsers)
    annofabcli.organization_member.subcommand_organization_member.add_parser(subparsers)
    annofabcli.project.subcommand_project.add_parser(subparsers)
    annofabcli.project_member.subcommand_project_member.add_parser(subparsers)
    annofabcli.statistics.subcommand_statistics.add_parser(subparsers)
    annofabcli.stat_visualization.subcommand_stat_visualization.add_parser(subparsers)
    annofabcli.supplementary.subcommand_supplementary.add_parser(subparsers)
    annofabcli.task.subcommand_task.add_parser(subparsers)
    annofabcli.task_count.subcommand_task_count.add_parser(subparsers)
    annofabcli.task_history.subcommand_task_history.add_parser(subparsers)
    annofabcli.task_history_event.subcommand_task_history_event.add_parser(subparsers)

    annofabcli.filesystem.subcommand_filesystem.add_parser(subparsers)
    annofabcli.experimental.subcommand_experimental.add_parser(subparsers)

    return parser


if __name__ == "__main__":
    main()
