import argparse
from typing import Optional

import annofabcli
import annofabcli.annotation.change_annotation_attributes
import annofabcli.annotation.change_annotation_properties
import annofabcli.annotation.copy_annotation
import annofabcli.annotation.delete_annotation
import annofabcli.annotation.dump_annotation
import annofabcli.annotation.import_annotation
import annofabcli.annotation.list_annotation
import annofabcli.annotation.list_annotation_count
import annofabcli.annotation.restore_annotation
import annofabcli.common.cli


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.annotation.change_annotation_attributes.add_parser(subparsers)
    annofabcli.annotation.change_annotation_properties.add_parser(subparsers)
    annofabcli.annotation.copy_annotation.add_parser(subparsers)
    annofabcli.annotation.delete_annotation.add_parser(subparsers)
    annofabcli.annotation.dump_annotation.add_parser(subparsers)
    annofabcli.annotation.import_annotation.add_parser(subparsers)
    annofabcli.annotation.list_annotation.add_parser(subparsers)
    annofabcli.annotation.list_annotation_count.add_parser(subparsers)
    annofabcli.annotation.restore_annotation.add_parser(subparsers)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "annotation"
    subcommand_help = "アノテーション関係のサブコマンド"
    description = "アノテーション関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description, is_subcommand=False
    )
    parse_args(parser)
    return parser
