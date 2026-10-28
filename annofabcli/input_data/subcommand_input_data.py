import argparse

import annofabcli.common.cli
import annofabcli.input_data.copy_input_data
import annofabcli.input_data.create_input_data
import annofabcli.input_data.create_input_data_from_zip
import annofabcli.input_data.delete_input_data
import annofabcli.input_data.delete_metadata_key_of_input_data
import annofabcli.input_data.download_input_data_json
import annofabcli.input_data.list_all_input_data
import annofabcli.input_data.list_all_input_data_merged_task
import annofabcli.input_data.list_input_data
import annofabcli.input_data.put_input_data
import annofabcli.input_data.update_input_data
import annofabcli.input_data.update_metadata_of_input_data
import annofabcli.input_data.update_metadata_per_input_data


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="subcommand_name", required=True)

    # サブコマンドの定義
    annofabcli.input_data.copy_input_data.create_parser(subparsers)
    annofabcli.input_data.create_input_data.create_parser(subparsers)
    annofabcli.input_data.create_input_data_from_zip.create_parser(subparsers)
    annofabcli.input_data.delete_input_data.create_parser(subparsers)
    annofabcli.input_data.delete_metadata_key_of_input_data.create_parser(subparsers)
    annofabcli.input_data.download_input_data_json.create_parser(subparsers)
    annofabcli.input_data.list_input_data.create_parser(subparsers)
    annofabcli.input_data.list_all_input_data.create_parser(subparsers)
    annofabcli.input_data.list_all_input_data_merged_task.create_parser(subparsers)
    annofabcli.input_data.put_input_data.create_parser(subparsers)
    annofabcli.input_data.update_input_data.create_parser(subparsers)
    annofabcli.input_data.update_metadata_of_input_data.create_parser(subparsers)
    annofabcli.input_data.update_metadata_per_input_data.create_parser(subparsers)


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "input_data"
    subcommand_help = "入力データ関係のサブコマンド"
    description = "入力データ関係のサブコマンド"

    parser = annofabcli.common.cli.create_parser(subparsers, subcommand_name, subcommand_help, description, is_subcommand=False)
    parse_args(parser)
    return parser
