from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import annofabapi
import pandas
import requests
from annofabapi.models import ProjectMemberRole
from more_itertools import first_true

import annofabcli.common.cli
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)

InputDataSupplementaryDataDict = dict[str, list[str]]
"""入力データIDと削除対象の補助情報ID一覧の対応。"""


def get_input_data_supplementary_data_dict_from_csv(csv_path: Path) -> InputDataSupplementaryDataDict:
    """CSVから入力データ別の削除対象IDを読み込みます。

    Args:
        csv_path: 削除対象のCSV。

    Returns:
        入力データIDと補助情報ID一覧の対応。
    """
    df: pandas.DataFrame = pandas.read_csv(
        csv_path,
        dtype={"input_data_id": "string", "supplementary_data_id": "string"},
    )
    input_data_dict: InputDataSupplementaryDataDict = defaultdict(list)
    for input_data_id, supplementary_data_id in zip(df["input_data_id"], df["supplementary_data_id"], strict=False):
        input_data_dict[input_data_id].append(supplementary_data_id)
    return input_data_dict


def get_input_data_supplementary_data_dict_from_list(supplementary_data_list: list[dict[str, Any]]) -> InputDataSupplementaryDataDict:
    """JSON配列から入力データ別の削除対象IDをまとめます。

    Args:
        supplementary_data_list: 削除対象の補助情報一覧。

    Returns:
        入力データIDと補助情報ID一覧の対応。
    """
    input_data_dict = defaultdict(list)
    for supplementary_data in supplementary_data_list:
        input_data_id = supplementary_data["input_data_id"]
        supplementary_data_id = supplementary_data["supplementary_data_id"]
        input_data_dict[input_data_id].append(supplementary_data_id)
    return input_data_dict


class DeleteSupplementaryDataPerSupplementaryDataMain(CommandLineWithConfirm):
    """ID一覧で指定した補助情報を個別に確認して削除します。"""

    def __init__(self, service: annofabapi.Resource, *, all_yes: bool = False) -> None:
        self.service = service
        CommandLineWithConfirm.__init__(self, all_yes)

    def delete_supplementary_data_list_for_input_data(self, project_id: str, input_data_id: str, supplementary_data_id_list: list[str]) -> int:
        """
        入力データ配下の補助情報を削除する。

        Args:
            project_id:
            input_data_id:
            supplementary_data_id_list:

        Returns:
            削除した補助情報の個数

        """

        def _get_supplementary_data_list(supplementary_data_id: str) -> dict[str, Any] | None:
            return first_true(supplementary_data_list, pred=lambda e: e["supplementary_data_id"] == supplementary_data_id)

        input_data = self.service.wrapper.get_input_data_or_none(project_id, input_data_id)
        if input_data is None:
            logger.warning(f"input_data_id='{input_data_id}' の入力データは存在しないのでスキップします。")
            return 0

        supplementary_data_list, _ = self.service.api.get_supplementary_data_list(project_id, input_data_id)

        deleted_count = 0
        for supplementary_data_id in supplementary_data_id_list:
            supplementary_data = _get_supplementary_data_list(supplementary_data_id)
            if supplementary_data is None:
                logger.warning(f"input_data_id='{input_data_id}' の入力データに、supplementary_data_id='{supplementary_data_id}' の補助情報は存在しないのでスキップします。")
                continue

            message_for_confirm = f"補助情報 supplementary_data_id='{supplementary_data_id}', supplementary_data_name='{supplementary_data['supplementary_data_name']}' を削除しますか？"
            if not self.confirm_processing(message_for_confirm):
                continue

            try:
                self.service.api.delete_supplementary_data(project_id, input_data_id=input_data_id, supplementary_data_id=supplementary_data_id)
                logger.debug(
                    f"補助情報 supplementary_data_id='{supplementary_data_id}', "
                    f"supplementary_data_name='{supplementary_data['supplementary_data_name']}' を削除しました。"
                    f"(入力データ input_data_id='{input_data_id}', "
                    f"input_data_name='{input_data['input_data_name']}' に紐付いている)"
                )
                deleted_count += 1
            except requests.HTTPError:
                logger.warning(
                    f"補助情報 supplementary_data_id='{supplementary_data_id}', supplementary_data_name='{supplementary_data['supplementary_data_name']}' の削除に失敗しました。",
                    exc_info=True,
                )
                continue
        return deleted_count

    def delete_supplementary_data_list(self, project_id: str, input_data_dict: InputDataSupplementaryDataDict) -> None:
        deleted_count = 0
        total_count = sum(len(e) for e in input_data_dict.values())
        processed_count = 0
        for input_data_id, supplementary_data_id_list in input_data_dict.items():
            try:
                deleted_count += self.delete_supplementary_data_list_for_input_data(project_id, input_data_id, supplementary_data_id_list)
            except Exception:  # pylint: disable=broad-except
                logger.warning(f"入力データ(input_data_id='{input_data_id}')配下の補助情報の削除に失敗しました。", exc_info=True)
            processed_count += len(supplementary_data_id_list)
            logger.info(f"{processed_count}/{total_count}件目までの補助情報を処理しました。")

        logger.info(f"{deleted_count} / {total_count} 件の補助情報を削除しました。")


class DeleteSupplementaryDataPerSupplementaryData(CommandLine):
    COMMON_MESSAGE = "annofabcli supplementary delete_per_supplementary_data: error:"
    """コマンドライン引数のエラーメッセージの接頭辞。"""

    def main(self) -> None:
        """CSVまたはJSONで指定した補助情報を削除します。

        Args:
            なし。

        Returns:
            None。
        """
        args = self.args
        if args.csv is not None:
            input_data_dict = get_input_data_supplementary_data_dict_from_csv(args.csv)
        else:
            supplementary_data_list = annofabcli.common.cli.get_json_from_args(args.json)
            if not isinstance(supplementary_data_list, list):
                print(f"{self.COMMON_MESSAGE} argument --json: JSON形式が不正です。オブジェクトの配列を指定してください。", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            input_data_dict = get_input_data_supplementary_data_dict_from_list(supplementary_data_list)
        super().require_project_access(args.project_id, [ProjectMemberRole.OWNER])
        main_obj = DeleteSupplementaryDataPerSupplementaryDataMain(self.service, all_yes=args.yes)
        main_obj.delete_supplementary_data_list(args.project_id, input_data_dict)


def main(args: argparse.Namespace) -> None:
    """認証して個別指定の補助情報削除を実行します。

    Args:
        args: コマンドライン引数。

    Returns:
        None。
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteSupplementaryDataPerSupplementaryData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    """個別指定の補助情報削除の引数を定義します。

    Args:
        parser: 引数の追加先。

    Returns:
        None。
    """
    ArgumentParser(parser).add_project_id()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--csv", type=Path, help="削除する補助情報のCSV。ヘッダ行と input_data_id、supplementary_data_id 列が必要です。")
    group.add_argument("--json", type=str, help="削除する補助情報のJSON配列。各要素に input_data_id と supplementary_data_id を指定します。 ``file://`` を先頭に付けるとJSONファイルを指定できます。")
    parser.set_defaults(subcommand_func=main)


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """個別指定の補助情報削除コマンドを登録します。

    Args:
        subparsers: コマンドの登録先。

    Returns:
        コマンドのパーサー。
    """
    help_message = "ID一覧で指定した補助情報を削除します。"
    parser = annofabcli.common.cli.create_parser(subparsers, "delete_per_supplementary_data", help_message, description=help_message, epilog="オーナロールを持つユーザで実行してください。")
    parse_args(parser)
    return parser
