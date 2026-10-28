"""サブコマンド annotation_zip"""

import argparse

import annofabcli
from annofabcli.annotation_zip.count_annotation_attribute_filled import create_parser as create_parser_count_annotation_attribute_filled
from annofabcli.annotation_zip.count_annotation_by_attribute_value import create_parser as create_parser_count_annotation_by_attribute_value
from annofabcli.annotation_zip.count_annotation_by_label import create_parser as create_parser_count_annotation_by_label
from annofabcli.annotation_zip.diff_annotation import create_parser as create_parser_diff
from annofabcli.annotation_zip.filter import create_parser as create_parser_filter
from annofabcli.annotation_zip.list_annotation_3d_bounding_box import create_parser as create_parser_list_annotation_3d_bounding_box
from annofabcli.annotation_zip.list_annotation_3d_segment import create_parser as create_parser_list_annotation_3d_segment
from annofabcli.annotation_zip.list_annotation_attribute import create_parser as create_parser_list_annotation_attribute
from annofabcli.annotation_zip.list_annotation_bounding_box_2d import create_parser as create_parser_list_annotation_bounding_box_2d
from annofabcli.annotation_zip.list_classification_annotation import create_parser as create_parser_list_classification_annotation
from annofabcli.annotation_zip.list_polygon_annotation import create_parser as create_parser_list_polygon_annotation
from annofabcli.annotation_zip.list_polyline_annotation import create_parser as create_parser_list_polyline_annotation
from annofabcli.annotation_zip.list_range_annotation import create_parser as create_parser_list_range_annotation
from annofabcli.annotation_zip.list_segmentation_annotation import create_parser as create_parser_list_segmentation_annotation
from annofabcli.annotation_zip.list_single_point_annotation import create_parser as create_parser_list_single_point_annotation
from annofabcli.annotation_zip.merge import create_parser as create_parser_merge
from annofabcli.annotation_zip.render import create_parser as create_parser_render
from annofabcli.annotation_zip.sum_annotation_duration_by_attribute_value import create_parser as create_parser_sum_annotation_duration_by_attribute_value
from annofabcli.annotation_zip.sum_annotation_duration_by_label import create_parser as create_parser_sum_annotation_duration_by_label
from annofabcli.annotation_zip.visualize_annotation_count_by_attribute_value import create_parser as create_parser_visualize_annotation_count_by_attribute_value
from annofabcli.annotation_zip.visualize_annotation_count_by_label import create_parser as create_parser_visualize_annotation_count_by_label
from annofabcli.annotation_zip.visualize_annotation_duration_by_attribute_value import create_parser as create_parser_visualize_annotation_duration_by_attribute_value
from annofabcli.annotation_zip.visualize_annotation_duration_by_label import create_parser as create_parser_visualize_annotation_duration_by_label


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    サブコマンドの引数を定義する
    Args:
        parser: パーサー
    """
    subparsers = parser.add_subparsers(dest="subcommand_name", required=True)

    # サブコマンドの定義
    create_parser_count_annotation_attribute_filled(subparsers)
    create_parser_count_annotation_by_attribute_value(subparsers)
    create_parser_count_annotation_by_label(subparsers)
    create_parser_diff(subparsers)
    create_parser_filter(subparsers)
    create_parser_list_annotation_3d_bounding_box(subparsers)
    create_parser_list_annotation_3d_segment(subparsers)
    create_parser_list_annotation_attribute(subparsers)
    create_parser_list_annotation_bounding_box_2d(subparsers)
    create_parser_list_classification_annotation(subparsers)
    create_parser_list_polygon_annotation(subparsers)
    create_parser_list_polyline_annotation(subparsers)
    create_parser_list_range_annotation(subparsers)
    create_parser_list_segmentation_annotation(subparsers)
    create_parser_list_single_point_annotation(subparsers)
    create_parser_merge(subparsers)
    create_parser_render(subparsers)
    create_parser_sum_annotation_duration_by_attribute_value(subparsers)
    create_parser_sum_annotation_duration_by_label(subparsers)
    create_parser_visualize_annotation_count_by_attribute_value(subparsers)
    create_parser_visualize_annotation_count_by_label(subparsers)
    create_parser_visualize_annotation_duration_by_attribute_value(subparsers)
    create_parser_visualize_annotation_duration_by_label(subparsers)


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    annotation_zipサブコマンドを追加する。
    Args:
        subparsers: 親パーサーのサブパーサー
    Returns:
        annotation_zipサブコマンドのパーサー
    """
    subcommand_name = "annotation_zip"
    subcommand_help = "アノテーションZIPに対する操作を行うサブコマンド"

    parser = annofabcli.common.cli.create_parser(subparsers, subcommand_name, subcommand_help, is_subcommand=False)
    parse_args(parser)
    return parser
