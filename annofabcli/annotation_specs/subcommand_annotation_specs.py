import argparse
from typing import Optional

import annofabcli
import annofabcli.annotation_specs.get_annotation_specs_with_attribute_id_replaced
import annofabcli.annotation_specs.get_annotation_specs_with_choice_id_replaced
import annofabcli.annotation_specs.get_annotation_specs_with_label_id_replaced
import annofabcli.annotation_specs.list_annotation_specs_history
import annofabcli.annotation_specs.list_annotation_specs_label
import annofabcli.annotation_specs.list_attribute_restriction
import annofabcli.annotation_specs.print_label_color
import annofabcli.common.cli


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.annotation_specs.get_annotation_specs_with_attribute_id_replaced.add_parser(subparsers)
    annofabcli.annotation_specs.get_annotation_specs_with_choice_id_replaced.add_parser(subparsers)
    annofabcli.annotation_specs.get_annotation_specs_with_label_id_replaced.add_parser(subparsers)
    annofabcli.annotation_specs.list_attribute_restriction.add_parser(subparsers)
    annofabcli.annotation_specs.list_annotation_specs_history.add_parser(subparsers)
    annofabcli.annotation_specs.list_annotation_specs_label.add_parser(subparsers)
    annofabcli.annotation_specs.print_label_color.add_parser(subparsers)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "annotation_specs"
    subcommand_help = "アノテーション仕様関係のサブコマンド"
    description = "アノテーション仕様関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description, is_subcommand=False
    )
    parse_args(parser)
    return parser
