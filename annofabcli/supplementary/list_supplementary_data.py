from __future__ import annotations

import argparse
import json
import logging
import tempfile
from pathlib import Path
from typing import Any

import annofabapi
from annofabapi.models import SupplementaryData

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


BULK_REQUEST_SIZE = 100
"""補助情報バルク取得APIの1リクエストで指定する入力データIDの上限。"""


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


class ListSupplementaryDataMain:
    def __init__(self, service: annofabapi.Resource, project_id: str) -> None:
        self.service = service
        self.project_id = project_id

    def get_all_supplementary_data_list(self, input_data_id_list: list[str]) -> list[SupplementaryData]:
        """
        複数の入力データに紐づく補助情報一覧をバルク取得する。

        Args:
            input_data_id_list: 入力データIDのリスト

        Returns:
            取得に成功した補助情報のリスト
        """
        all_supplementary_data_list: list[SupplementaryData] = []
        failed_input_data_count = 0
        logger.info(f"{len(input_data_id_list)} 件の入力データに紐づく補助情報を取得します。")

        for initial_index in range(0, len(input_data_id_list), BULK_REQUEST_SIZE):
            batch_input_data_id_list = input_data_id_list[initial_index : initial_index + BULK_REQUEST_SIZE]
            processed_input_data_count = initial_index + len(batch_input_data_id_list)
            try:
                response, _ = self.service.api.get_supplementary_data_in_bulk(
                    self.project_id,
                    query_params={"input_data_id": ",".join(batch_input_data_id_list)},
                )
            except Exception:
                failed_input_data_count += len(batch_input_data_id_list)
                logger.warning(
                    f"入力データ {initial_index + 1}〜{processed_input_data_count} 件（{len(batch_input_data_id_list)}件）の補助情報バルク取得に失敗しました。",
                    exc_info=True,
                )
                logger.info(f"{processed_input_data_count} / {len(input_data_id_list)} 件の入力データに紐づく補助情報の取得を試みました。")
                continue

            supplementary_data_list = response["success"]
            for supplementary_data in supplementary_data_list:
                remove_unnecessary_keys_from_supplementary_data(supplementary_data)
            all_supplementary_data_list.extend(supplementary_data_list)

            for failure_info in response["failure"]:
                logger.warning(f"input_data_id='{failure_info['input_data_id']}': 補助情報の取得に失敗しました。")
            failed_input_data_count += len(response["failure"])

            logger.info(f"{processed_input_data_count} / {len(input_data_id_list)} 件の入力データに紐づく補助情報を取得しました。")

        logger.info(f"補助情報の取得が完了しました。取得件数: {len(all_supplementary_data_list)} 件, 失敗した入力データ数: {failed_input_data_count} 件")
        return all_supplementary_data_list


class ListSupplementaryData(CommandLine):
    """
    補助情報一覧を表示する。
    """

    def get_input_data_id_list_from_input_data_json(self, project_id: str) -> list[str]:
        """
        入力データ全件ファイルをダウンロードして、そのファイルからinput_data_idのlistを取得します。
        """
        downloading_obj = DownloadingFile(self.service)
        with tempfile.TemporaryDirectory() as str_temp_dir:
            input_data_json = downloading_obj.download_input_data_json_to_dir(project_id, Path(str_temp_dir))
            with input_data_json.open(encoding="utf-8") as f:
                input_data_list = json.load(f)

        return [e["input_data_id"] for e in input_data_list]

    def main(self) -> None:
        args = self.args
        input_data_id_list = annofabcli.common.cli.get_list_from_args(args.input_data_id) if args.input_data_id is not None else None
        project_id = args.project_id

        if input_data_id_list is None:
            input_data_id_list = self.get_input_data_id_list_from_input_data_json(project_id)

        main_obj = ListSupplementaryDataMain(self.service, project_id=project_id)
        all_supplementary_data_list = main_obj.get_all_supplementary_data_list(input_data_id_list)
        self.print_according_to_format(all_supplementary_data_list)


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
            "未指定の場合は、入力データ全件ファイルをダウンロードして、すべての入力データに紐づく補助情報を出力します。\n"
            "``file://`` を先頭に付けると、input_data_idの一覧が記載されたファイルを指定できます。"
        ),
    )

    argument_parser.add_format(choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON], default=OutputFormat.CSV)
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list"
    subcommand_help = "補助情報一覧を出力します。"
    description = "補助情報一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
