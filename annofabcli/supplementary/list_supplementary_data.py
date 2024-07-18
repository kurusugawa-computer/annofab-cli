from __future__ import annotations

import argparse
import json
import logging
import tempfile
from pathlib import Path
from typing import Any, List, Optional

from annofabapi.models import SupplementaryData

import annofabcli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


def remove_unnecessary_keys_from_supplementary_data(supplementary_data: dict[str, Any]) -> None:
    """
    補助情報から不要なキーを取り除きます。
    システム内部用のプロパティなど、annofab-cliを使う上で不要な情報を削除します。

    Args:
        supplementary_data: (IN/OUT) 補助情報。引数が変更されます。
    """
    unnecessary_keys = [
        "url",  # システム内部用のプロパティ
        "etag",  # annofab-cliで見ることはない
    ]
    for key in unnecessary_keys:
        supplementary_data.pop(key, None)


class ListSupplementaryData(CommandLine):
    """
    補助情報一覧を表示する。
    """

    def get_input_data_id_from_task(self, project_id: str, task_id_list: List[str]) -> List[str]:
        all_input_data_id_list = []
        logger.info(f"{len(task_id_list)} 件のタスクを取得します。")
        for task_id in task_id_list:
            task = self.service.wrapper.get_task_or_none(project_id, task_id)
            if task is None:
                logger.warning(f"task_id='{task_id}'のタスクが見つかりませんでした。")
                continue
            all_input_data_id_list.extend(task["input_data_id_list"])
        return all_input_data_id_list

    def get_all_supplementary_data_list(self, project_id: str, input_data_id_list: List[str]) -> List[SupplementaryData]:
        """
        補助情報一覧を取得する。
        """
        all_supplementary_data_list: List[SupplementaryData] = []
        logger.info(f"{len(input_data_id_list)} 件の入力データに紐づく補助情報を取得します。")
        for index, input_data_id in enumerate(input_data_id_list):
            if (index + 1) % 100 == 0:
                logger.debug(f"{index+1} 件目の入力データを取得します。")

            supplementary_data_list = self.service.wrapper.get_supplementary_data_list_or_none(project_id, input_data_id)

            if supplementary_data_list is not None:
                # 補助情報から不要なキーを取り除く
                for supplementary_data in supplementary_data_list:
                    remove_unnecessary_keys_from_supplementary_data(supplementary_data)
                all_supplementary_data_list.extend(supplementary_data_list)
            else:
                logger.warning(f"入力データ '{input_data_id}' に紐づく補助情報が見つかりませんでした。")

        return all_supplementary_data_list

    def print_supplementary_data_list(self, project_id: str, input_data_id_list: Optional[List[str]]) -> None:
        """
        補助情報一覧を出力する

        """
        if input_data_id_list is None:
            downloading_obj = DownloadingFile(self.service)
            with tempfile.TemporaryDirectory() as str_temp_dir:
                input_data_json = Path(str_temp_dir) / f"{project_id}__input_data.json"
                downloading_obj.download_input_data_json(project_id, dest_path=input_data_json)
                with input_data_json.open() as f:
                    input_data_list = json.load(f)

            input_data_id_list = [e["input_data_id"] for e in input_data_list]

        supplementary_data_list = self.get_all_supplementary_data_list(project_id, input_data_id_list=input_data_id_list)
        logger.info(f"補助情報一覧の件数: {len(supplementary_data_list)}")
        self.print_according_to_format(supplementary_data_list)

    def main(self) -> None:
        args = self.args
        input_data_id_list = annofabcli.common.cli.get_list_from_args(args.input_data_id) if args.input_data_id is not None else None

        self.print_supplementary_data_list(project_id=args.project_id, input_data_id_list=input_data_id_list)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListSupplementaryData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    parser.add_argument(
        "-i",
        "--input_data_id",
        type=str,
        nargs="+",
        help=(
            "指定したinput_data_idの入力データに紐づく補助情報を出力します。\n"
            "未指定の場合は、入力データ全件ファイルをダウンロードして、すべての入力データに紐づく補助情報を出力します。ただし入力データの数だけAPIを実行するため、出力に時間がかかります。 \n"  # noqa: E501
            "``file://`` を先頭に付けると、input_data_idの一覧が記載されたファイルを指定できます。"
        ),
    )

    argument_parser.add_format(choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON], default=FormatArgument.CSV)
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list"
    subcommand_help = "補助情報一覧を出力します。"
    description = "補助情報一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
