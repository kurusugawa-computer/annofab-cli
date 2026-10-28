import argparse

import annofabcli.annotation_specs.add_attribute
import annofabcli.annotation_specs.add_attribute_restriction
import annofabcli.annotation_specs.add_attributes
import annofabcli.annotation_specs.add_choice_attribute
import annofabcli.annotation_specs.add_choices_to_attribute
import annofabcli.annotation_specs.add_choices_to_attributes
import annofabcli.annotation_specs.add_existing_attribute_to_labels
import annofabcli.annotation_specs.add_inspection_phrases
import annofabcli.annotation_specs.add_label
import annofabcli.annotation_specs.add_labels
import annofabcli.annotation_specs.change_attribute_type
import annofabcli.annotation_specs.delete_attribute_restriction
import annofabcli.annotation_specs.delete_attributes
import annofabcli.annotation_specs.delete_choices
import annofabcli.annotation_specs.delete_inspection_phrases
import annofabcli.annotation_specs.delete_labels
import annofabcli.annotation_specs.describe_label_attributes
import annofabcli.annotation_specs.diff_annotation_specs
import annofabcli.annotation_specs.export_annotation_specs
import annofabcli.annotation_specs.import_annotation_specs
import annofabcli.annotation_specs.list_annotation_import_info
import annofabcli.annotation_specs.list_annotation_specs_attribute
import annofabcli.annotation_specs.list_annotation_specs_choice
import annofabcli.annotation_specs.list_annotation_specs_history
import annofabcli.annotation_specs.list_annotation_specs_inspection_phrase
import annofabcli.annotation_specs.list_annotation_specs_label
import annofabcli.annotation_specs.list_annotation_specs_label_attribute
import annofabcli.annotation_specs.list_attribute_restriction
import annofabcli.annotation_specs.reorder_attributes
import annofabcli.annotation_specs.reorder_choices
import annofabcli.annotation_specs.reorder_labels
import annofabcli.annotation_specs.set_attribute_required
import annofabcli.annotation_specs.unset_attribute_required
import annofabcli.annotation_specs.update_attributes
import annofabcli.annotation_specs.update_choices
import annofabcli.annotation_specs.update_inspection_phrases
import annofabcli.annotation_specs.update_label_field_values
import annofabcli.annotation_specs.update_labels
import annofabcli.annotation_specs.update_option
import annofabcli.common.cli


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="subcommand_name", required=True)

    # サブコマンドの定義
    annofabcli.annotation_specs.add_attribute.create_parser(subparsers)
    annofabcli.annotation_specs.add_attribute_restriction.create_parser(subparsers)
    annofabcli.annotation_specs.add_attributes.create_parser(subparsers)
    annofabcli.annotation_specs.add_choice_attribute.create_parser(subparsers)
    annofabcli.annotation_specs.add_choices_to_attribute.create_parser(subparsers)
    annofabcli.annotation_specs.add_choices_to_attributes.create_parser(subparsers)
    annofabcli.annotation_specs.add_existing_attribute_to_labels.create_parser(subparsers)
    annofabcli.annotation_specs.add_inspection_phrases.create_parser(subparsers)
    annofabcli.annotation_specs.add_label.create_parser(subparsers)
    annofabcli.annotation_specs.add_labels.create_parser(subparsers)
    annofabcli.annotation_specs.change_attribute_type.create_parser(subparsers)
    annofabcli.annotation_specs.delete_attribute_restriction.create_parser(subparsers)
    annofabcli.annotation_specs.delete_attributes.create_parser(subparsers)
    annofabcli.annotation_specs.delete_choices.create_parser(subparsers)
    annofabcli.annotation_specs.delete_inspection_phrases.create_parser(subparsers)
    annofabcli.annotation_specs.delete_labels.create_parser(subparsers)
    annofabcli.annotation_specs.describe_label_attributes.create_parser(subparsers)
    annofabcli.annotation_specs.diff_annotation_specs.create_parser(subparsers)
    annofabcli.annotation_specs.export_annotation_specs.create_parser(subparsers)
    annofabcli.annotation_specs.import_annotation_specs.create_parser(subparsers)
    annofabcli.annotation_specs.list_annotation_import_info.create_parser(subparsers)
    annofabcli.annotation_specs.list_annotation_specs_attribute.create_parser(subparsers)
    annofabcli.annotation_specs.list_attribute_restriction.create_parser(subparsers)
    annofabcli.annotation_specs.list_annotation_specs_choice.create_parser(subparsers)
    annofabcli.annotation_specs.list_annotation_specs_history.create_parser(subparsers)
    annofabcli.annotation_specs.list_annotation_specs_inspection_phrase.create_parser(subparsers)
    annofabcli.annotation_specs.list_annotation_specs_label.create_parser(subparsers)
    annofabcli.annotation_specs.list_annotation_specs_label_attribute.create_parser(subparsers)
    annofabcli.annotation_specs.reorder_attributes.create_parser(subparsers)
    annofabcli.annotation_specs.reorder_choices.create_parser(subparsers)
    annofabcli.annotation_specs.reorder_labels.create_parser(subparsers)
    annofabcli.annotation_specs.set_attribute_required.create_parser(subparsers)
    annofabcli.annotation_specs.unset_attribute_required.create_parser(subparsers)
    annofabcli.annotation_specs.update_attributes.create_parser(subparsers)
    annofabcli.annotation_specs.update_choices.create_parser(subparsers)
    annofabcli.annotation_specs.update_inspection_phrases.create_parser(subparsers)
    annofabcli.annotation_specs.update_label_field_values.create_parser(subparsers)
    annofabcli.annotation_specs.update_labels.create_parser(subparsers)
    annofabcli.annotation_specs.update_option.create_parser(subparsers)


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "annotation_specs"
    subcommand_help = "アノテーション仕様関係のサブコマンド"
    description = "アノテーション仕様関係のサブコマンド"

    parser = annofabcli.common.cli.create_parser(subparsers, subcommand_name, subcommand_help, description, is_subcommand=False)
    parse_args(parser)
    return parser
