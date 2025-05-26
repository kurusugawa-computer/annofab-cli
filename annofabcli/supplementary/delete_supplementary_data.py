import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import annofabapi
import pandas
import requests
from annofabapi.models import ProjectMemberRole
from more_itertools import first_true

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)

InputDataSupplementaryDataDict = dict[str, list[str]]
"""
input_data_idとsupplementary_data_idの関係を表したdict.
key: input_data_id, value: supplementary_data_idのList
"""


def get_input_data_supplementary_data_dict_from_csv(csv_path: Path) -> InputDataSupplementaryDataDict:
    df: pandas.DataFrame = pandas.read_csv(
        csv_path,
        dtype={"input_data_id": "string", "supplementary_data_id": "string"},
    )
    input_data_dict: InputDataSupplementaryDataDict = defaultdict(list)
    for input_data_id, supplementary_data_id in zip(df["input_data_id"], df["supplementary_data_id"]):
        input_data_dict[input_data_id].append(supplementary_data_id)
    return input_data_dict


def get_input_data_supplementary_data_dict_from_list(supplementary_data_list: list[dict[str, Any]]) -> InputDataSupplementaryDataDict:
    input_data_dict = defaultdict(list)
    for supplementary_data in supplementary_data_list:
        input_data_id = supplementary_data["input_data_id"]
        supplementary_data_id = supplementary_data["supplementary_data_id"]
        input_data_dict[input_data_id].append(supplementary_data_id)
    return input_data_dict


class DeleteSupplementaryDataMain(CommandLineWithConfirm):
    def __init__(self, service: annofabapi.Resource, *, all_yes: bool = False) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)
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

        def _get_supplementary_data_list(supplementary_data_id: str) -> Optional[dict[str, Any]]:
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
        for input_data_id, supplementary_data_id_list in input_data_dict.items():
            try:
                deleted_count += self.delete_supplementary_data_list_for_input_data(project_id, input_data_id, supplementary_data_id_list)
            except Exception:  # pylint: disable=broad-except
                logger.warning(f"入力データ(input_data_id='{input_data_id}')配下の補助情報の削除に失敗しました。", exc_info=True)

        logger.info(f"{deleted_count} / {total_count} 件の補助情報を削除しました。")

    def delete_supplementary_data_list_for_input_data2(self, project_id: str, input_data_id: str, supplementary_data_list: list[dict[str, Any]]) -> int:
        """
        入力データ配下の補助情報を削除する。

        Args:
            project_id:
            input_data_id:
            supplementary_data_list:

        Returns:
            削除した補助情報の個数

        """
        deleted_count = 0
        for supplementary_data in supplementary_data_list:
            supplementary_data_id = supplementary_data["supplementary_data_id"]
            try:
                self.service.api.delete_supplementary_data(project_id, input_data_id=input_data_id, supplementary_data_id=supplementary_data_id)
                logger.debug(
                    f"補助情報を削除しました。input_data_id='{input_data_id}', supplementary_data_id='{supplementary_data_id}', supplementary_data_name={supplementary_data['supplementary_data_name']}"
                )
                deleted_count += 1
            except requests.HTTPError:
                logger.warning(
                    f"補助情報の削除に失敗しました。input_data_id='{input_data_id}', supplementary_data_id='{supplementary_data_id}', "
                    f"supplementary_data_name='{supplementary_data['supplementary_data_name']}'",
                    exc_info=True,
                )
                continue

        return deleted_count

    def delete_supplementary_data_list_by_input_data_id(self, project_id: str, input_data_id_list: list[str]) -> None:
        dict_deleted_count: dict[str, int] = {}
        for input_data_id in input_data_id_list:
            input_data = self.service.wrapper.get_input_data_or_none(project_id, input_data_id)
            if input_data is None:
                logger.warning(f"input_data_id='{input_data_id}' の入力データは存在しないので、補助情報の削除をスキップします。")
                continue
            input_data_name = input_data["input_data_name"]

            supplementary_data_list, _ = self.service.api.get_supplementary_data_list(project_id, input_data_id)
            if len(supplementary_data_list) == 0:
                logger.debug("入力データに紐づく補助情報は存在しないので、削除をスキップします。")
                continue

            message_for_confirm = f"入力データに紐づく補助情報 {len(supplementary_data_list)} 件を削除しますか？ (input_data_id='{input_data_id}', input_data_name='{input_data_name}') "
            if not self.confirm_processing(message_for_confirm):
                continue

            try:
                deleted_supplementary_data_count = self.delete_supplementary_data_list_for_input_data2(project_id, input_data_id, supplementary_data_list)
                dict_deleted_count[input_data_id] = deleted_supplementary_data_count
                logger.debug(
                    f"入力データに紐づく補助情報を {deleted_supplementary_data_count} / {len(supplementary_data_list)} 件削除しました。"
                    f"(input_data_id='{input_data_id}', "
                    f"input_data_name='{input_data_name}') "
                )

            except Exception:  # pylint: disable=broad-except
                logger.warning(f"入力データ(input_data_id='{input_data_id}')配下の補助情報の削除に失敗しました。", exc_info=True)

        logger.info(f"{len(dict_deleted_count)} / {len(input_data_id_list)} 件の入力データに紐づく補助情報を削除しました。")


class DeleteSupplementaryData(CommandLine):
    COMMON_MESSAGE = "annofabcli supplementary_data delete: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.csv is not None:  # noqa: SIM102
            if not Path(args.csv).exists():
                print(f"{self.COMMON_MESSAGE} argument --csv: ファイルパスが存在しません。 '{args.csv}'", file=sys.stderr)  # noqa: T201
                return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        main_obj = DeleteSupplementaryDataMain(self.service, all_yes=args.yes)

        if args.csv is not None:
            input_data_dict = get_input_data_supplementary_data_dict_from_csv(args.csv)
            main_obj.delete_supplementary_data_list(project_id, input_data_dict)

        elif args.json is not None:
            supplementary_data_list = annofabcli.common.cli.get_json_from_args(args.json)
            if not isinstance(supplementary_data_list, list):
                print(f"{self.COMMON_MESSAGE} argument --json: JSON形式が不正です。オブジェクトの配列を指定してください。", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

            input_data_dict = get_input_data_supplementary_data_dict_from_list(supplementary_data_list)
            main_obj.delete_supplementary_data_list(project_id, input_data_dict)

        elif args.input_data_id is not None:
            input_data_id_list = annofabcli.common.cli.get_list_from_args(args.input_data_id)
            main_obj.delete_supplementary_data_list_by_input_data_id(project_id, input_data_id_list=input_data_id_list)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteSupplementaryData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--csv",
        type=str,
        help=(
            "削除する補助情報が記載されたCSVファイルのパスを指定してください。\n"
            "CSVのフォーマットは以下の通りです。"
            "詳細は https://annofab-cli.readthedocs.io/ja/latest/command_reference/supplementary/delete.html を参照してください。\n"
            " * ヘッダ行あり, カンマ区切り\n"
            " * input_data_id (required)\n"
            " * supplementary_data_id (required)\n"
        ),
    )

    JSON_SAMPLE = '[{"input_data_id" : "input1", "supplementary_data_id" : "supplementary1"}]'  # noqa: N806
    group.add_argument(
        "--json",
        type=str,
        help=(
            "削除対象の補助情報データをJSON形式で指定してください。\n"
            "JSONの各キーは ``--csv`` に渡すCSVの各列に対応しています。\n"
            "``file://`` を先頭に付けるとjsonファイルを指定できます。\n"
            f"(ex) ``{JSON_SAMPLE}``"
        ),
    )

    group.add_argument(
        "-i",
        "--input_data_id",
        type=str,
        nargs="+",
        help=(
            "削除する補助情報に紐づく入力データのinput_data_idを指定してください。"
            "指定した入力データに紐づくすべての補助情報を削除します。"
            " ``file://`` を先頭に付けると、input_data_idの一覧が記載されたファイルを指定できます。"
        ),
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "delete"
    subcommand_help = "補助情報を削除します。"
    description = "補助情報を削除します。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
