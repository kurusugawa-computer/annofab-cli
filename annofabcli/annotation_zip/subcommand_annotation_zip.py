"""サブコマンド annotation_zip"""

import argparse

import annofabcli
from annofabcli.annotation_zip.list_annotation_3d_bounding_box import add_parser as add_parser_list_annotation_3d_bounding_box
from annofabcli.annotation_zip.list_annotation_bounding_box_2d import add_parser as add_parser_list_annotation_bounding_box_2d
from annofabcli.annotation_zip.list_polygon_annotation import add_parser as add_parser_list_polygon_annotation
from annofabcli.annotation_zip.list_polyline_annotation import add_parser as add_parser_list_polyline_annotation
from annofabcli.annotation_zip.list_range_annotation import add_parser as add_parser_list_range_annotation
from annofabcli.annotation_zip.list_single_point_annotation import add_parser as add_parser_list_single_point_annotation


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    サブコマンドの引数を定義する
    Args:
        parser: パーサー
    """
    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    add_parser_list_annotation_3d_bounding_box(subparsers)
    add_parser_list_annotation_bounding_box_2d(subparsers)
    add_parser_list_polygon_annotation(subparsers)
    add_parser_list_polyline_annotation(subparsers)
    add_parser_list_range_annotation(subparsers)
    add_parser_list_single_point_annotation(subparsers)
    # 作成中のためコメントアウト
    # add_parser_validate_annotation(subparsers)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
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
