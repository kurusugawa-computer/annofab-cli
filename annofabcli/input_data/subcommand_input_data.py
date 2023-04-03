import argparse
from typing import Optional

import annofabcli
import annofabcli.common.cli
import annofabcli.input_data.change_input_data_name
import annofabcli.input_data.delete_input_data
import annofabcli.input_data.download_input_data_json
import annofabcli.input_data.list_all_input_data
import annofabcli.input_data.list_input_data
import annofabcli.input_data.list_input_data_merged_task
import annofabcli.input_data.put_input_data
import annofabcli.input_data.put_input_data_with_zip
import annofabcli.input_data.update_metadata_of_input_data


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.input_data.change_input_data_name.add_parser(subparsers)
    annofabcli.input_data.delete_input_data.add_parser(subparsers)
    annofabcli.input_data.download_input_data_json.add_parser(subparsers)
    annofabcli.input_data.list_input_data.add_parser(subparsers)
    annofabcli.input_data.list_all_input_data.add_parser(subparsers)
    annofabcli.input_data.list_input_data_merged_task.add_parser(subparsers)
    annofabcli.input_data.put_input_data.add_parser(subparsers)
    annofabcli.input_data.put_input_data_with_zip.add_parser(subparsers)
    annofabcli.input_data.update_metadata_of_input_data.add_parser(subparsers)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "input_data"
    subcommand_help = "入力データ関係のサブコマンド"
    description = "入力データ関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description, is_subcommand=False
    )
    parse_args(parser)
    return parser
