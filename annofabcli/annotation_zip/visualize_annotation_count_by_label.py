from __future__ import annotations

import argparse

import annofabcli.common.cli
from annofabcli.annotation_zip.visualize_annotation_count import add_common_arguments, main_label


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    コマンドライン引数のパーサーを設定します。

    Args:
        parser: argparseのArgumentParserインスタンス
    """
    add_common_arguments(parser)
    parser.set_defaults(subcommand_func=main_label)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    visualize_annotation_count_by_labelサブコマンドのパーサーを追加します。

    Args:
        subparsers: 親パーサーのサブパーサーアクション

    Returns:
        作成されたArgumentParserインスタンス
    """
    subcommand_name = "visualize_annotation_count_by_label"
    subcommand_help = "ラベルごとのアノテーション数をヒストグラムで可視化します。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
