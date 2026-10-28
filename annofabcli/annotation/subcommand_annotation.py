import argparse

import annofabcli.annotation.change_annotation_attributes
import annofabcli.annotation.change_annotation_attributes_per_annotation
import annofabcli.annotation.change_annotation_data_per_annotation
import annofabcli.annotation.change_annotation_editor_props
import annofabcli.annotation.change_annotation_label
import annofabcli.annotation.change_annotation_label_per_annotation
import annofabcli.annotation.copy_annotation
import annofabcli.annotation.create_annotation
import annofabcli.annotation.create_classification_annotation
import annofabcli.annotation.delete_annotation
import annofabcli.annotation.delete_invalid_attribute_value
import annofabcli.annotation.delete_invalid_label_annotation
import annofabcli.annotation.download_annotation_zip
import annofabcli.annotation.dump_annotation
import annofabcli.annotation.export_annotation
import annofabcli.annotation.import_annotation
import annofabcli.annotation.list_annotation
import annofabcli.annotation.list_annotation_count
import annofabcli.annotation.merge_segmentation
import annofabcli.annotation.normalize_attribute_type
import annofabcli.annotation.remove_segmentation_overlap
import annofabcli.annotation.restore_annotation
import annofabcli.common.cli


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="subcommand_name", required=True)

    # サブコマンドの定義
    annofabcli.annotation.change_annotation_attributes.create_parser(subparsers)
    annofabcli.annotation.change_annotation_attributes_per_annotation.create_parser(subparsers)
    annofabcli.annotation.change_annotation_data_per_annotation.create_parser(subparsers)
    annofabcli.annotation.change_annotation_editor_props.create_parser(subparsers)
    annofabcli.annotation.change_annotation_label.create_parser(subparsers)
    annofabcli.annotation.change_annotation_label_per_annotation.create_parser(subparsers)
    annofabcli.annotation.copy_annotation.create_parser(subparsers)
    annofabcli.annotation.create_annotation.create_parser(subparsers)
    annofabcli.annotation.create_classification_annotation.create_parser(subparsers)
    annofabcli.annotation.delete_annotation.create_parser(subparsers)
    annofabcli.annotation.delete_invalid_attribute_value.create_parser(subparsers)
    annofabcli.annotation.delete_invalid_label_annotation.create_parser(subparsers)
    annofabcli.annotation.download_annotation_zip.create_parser(subparsers)
    annofabcli.annotation.dump_annotation.create_parser(subparsers)
    annofabcli.annotation.export_annotation.create_parser(subparsers)
    annofabcli.annotation.import_annotation.create_parser(subparsers)
    annofabcli.annotation.list_annotation.create_parser(subparsers)
    annofabcli.annotation.list_annotation_count.create_parser(subparsers)
    annofabcli.annotation.merge_segmentation.create_parser(subparsers)
    annofabcli.annotation.normalize_attribute_type.create_parser(subparsers)
    annofabcli.annotation.remove_segmentation_overlap.create_parser(subparsers)
    annofabcli.annotation.restore_annotation.create_parser(subparsers)


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "annotation"
    subcommand_help = "アノテーション関係のサブコマンド"
    description = "アノテーション関係のサブコマンド"

    parser = annofabcli.common.cli.create_parser(subparsers, subcommand_name, subcommand_help, description, is_subcommand=False)
    parse_args(parser)
    return parser
