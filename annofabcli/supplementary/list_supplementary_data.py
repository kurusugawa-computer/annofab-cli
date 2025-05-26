from __future__ import annotations

import argparse
import itertools
import json
import logging
import multiprocessing
import tempfile
from pathlib import Path
from typing import Any, Optional

import annofabapi
from annofabapi.models import SupplementaryData

import annofabcli
from annofabcli.common.cli import PARALLELISM_CHOICES, ArgumentParser, CommandLine, build_annofabapi_resource_and_login
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


class ListSupplementaryDataMain:
    def __init__(self, service: annofabapi.Resource, project_id: str) -> None:
        self.service = service
        self.project_id = project_id

    def get_supplementary_data_list(self, input_data_id: str, input_data_index: int) -> list[dict[str, Any]]:
        """
        入力データに紐づく補助情報一覧を取得する。

        Args:
            input_data_id: 入力データID
            input_data_index: 0始まりのインデックス
        """
        if (input_data_index + 1) % 100 == 0:
            logger.debug(f"{input_data_index + 1} 件目の入力データに紐づく補助情報を取得します。")

        supplementary_data_list = self.service.wrapper.get_supplementary_data_list_or_none(self.project_id, input_data_id)

        if supplementary_data_list is not None:
            # 補助情報から不要なキーを取り除く
            for supplementary_data in supplementary_data_list:
                remove_unnecessary_keys_from_supplementary_data(supplementary_data)
            return supplementary_data_list
        else:
            logger.warning(f"input_data_id='{input_data_id}'である入力データは存在しません。")
            return []

    def get_supplementary_data_list_wrapper(self, tpl: tuple[int, str]) -> list[dict[str, Any]]:
        input_data_index, input_data_id = tpl
        try:
            return self.get_supplementary_data_list(input_data_id=input_data_id, input_data_index=input_data_index)
        except Exception:
            logger.warning(f"input_data_id='{input_data_index}': 補助情報の取得に失敗しました。", exc_info=True)
            return []

    def get_all_supplementary_data_list(self, input_data_id_list: list[str], *, parallelism: Optional[int] = None) -> list[SupplementaryData]:
        """
        補助情報一覧を取得する。
        """
        all_supplementary_data_list: list[SupplementaryData] = []
        logger.info(f"{len(input_data_id_list)} 件の入力データに紐づく補助情報を取得します。")

        if parallelism is not None:
            with multiprocessing.Pool(parallelism) as pool:
                result = pool.map(self.get_supplementary_data_list_wrapper, enumerate(input_data_id_list))
                return list(itertools.chain.from_iterable(result))

        else:
            # 逐次処理
            all_supplementary_data_list = []
            for input_data_index, input_data_id in enumerate(input_data_id_list):
                try:
                    sub_supplementary_data_list = self.get_supplementary_data_list(
                        input_data_id=input_data_id,
                        input_data_index=input_data_index,
                    )
                    all_supplementary_data_list.extend(sub_supplementary_data_list)
                except Exception:
                    logger.warning(f"input_data_id='{input_data_index}': 補助情報の取得に失敗しました。", exc_info=True)
                    continue

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
            input_data_json = Path(str_temp_dir) / f"{project_id}__input_data.json"
            downloading_obj.download_input_data_json(project_id, dest_path=input_data_json)
            with input_data_json.open() as f:
                input_data_list = json.load(f)

        return [e["input_data_id"] for e in input_data_list]

    def main(self) -> None:
        args = self.args
        input_data_id_list = annofabcli.common.cli.get_list_from_args(args.input_data_id) if args.input_data_id is not None else None
        project_id = args.project_id

        if input_data_id_list is None:
            input_data_id_list = self.get_input_data_id_list_from_input_data_json(project_id)

        main_obj = ListSupplementaryDataMain(self.service, project_id=project_id)
        all_supplementary_data_list = main_obj.get_all_supplementary_data_list(input_data_id_list, parallelism=args.parallelism)
        logger.info(f"補助情報一覧の件数: {len(all_supplementary_data_list)}")
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
            "未指定の場合は、入力データ全件ファイルをダウンロードして、すべての入力データに紐づく補助情報を出力します。ただし入力データの数だけAPIを実行するため、出力に時間がかかります。 \n"
            "``file://`` を先頭に付けると、input_data_idの一覧が記載されたファイルを指定できます。"
        ),
    )

    argument_parser.add_format(choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON], default=FormatArgument.CSV)
    argument_parser.add_output()

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="並列度。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list"
    subcommand_help = "補助情報一覧を出力します。"
    description = "補助情報一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
