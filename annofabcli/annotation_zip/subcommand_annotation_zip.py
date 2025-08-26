"""サブコマンド annotation_zip"""

import argparse
from typing import Optional

import annofabcli
from annofabcli.annotation_zip.list_annotation_bounding_box_2d import add_parser as add_parser_list_annotation_bounding_box_2d


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    サブコマンドの引数を定義する
    Args:
        parser: パーサー
    """
    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    add_parser_list_annotation_bounding_box_2d(subparsers)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    """
    annotation_zipサブコマンドを追加する。
    Args:
        subparsers: 親パーサーのサブパーサー
    Returns:
        annotation_zipサブコマンドのパーサー
    """
    subcommand_name = "annotation_zip"
    subcommand_help = "アノテーションZIPに対する操作を行うサブコマンド"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, is_subcommand=False)
    parse_args(parser)
    return parser
