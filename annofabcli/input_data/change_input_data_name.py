from __future__ import annotations

import argparse
import logging
import multiprocessing
import sys
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Optional

import annofabapi
import pandas
from dataclasses_json import DataClassJsonMixin

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
    get_json_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


@dataclass
class ChangedInputData(DataClassJsonMixin):
    """
    変更される入力データ
    """

    input_data_id: str
    """変更対象の入力データを表すID"""
    input_data_name: str
    """変更後の入力データ名"""


class ChangeInputDataNameMain(CommandLineWithConfirm):
    def __init__(self, service: annofabapi.Resource, *, all_yes: bool = False) -> None:
        self.service = service
        CommandLineWithConfirm.__init__(self, all_yes)

    def change_input_data_name(self, project_id: str, input_data_id: str, new_input_data_name: str) -> bool:
        """
        1個の入力データの名前を変更します。
        """
        old_input_data = self.service.wrapper.get_input_data_or_none(project_id, input_data_id)
        if old_input_data is None:
            logger.warning(f"input_data_id='{input_data_id}'である入力データは存在しません。")
            return False

        if not self.confirm_processing(f"input_data_id='{input_data_id}' :: input_data_name='{old_input_data['input_data_name']}'を'{new_input_data_name}'に変更しますか？"):
            return False

        request_body = old_input_data
        request_body["last_updated_datetime"] = old_input_data["updated_datetime"]
        request_body["input_data_name"] = new_input_data_name

        self.service.api.put_input_data(project_id, input_data_id, request_body=request_body)
        return True

    def change_input_data_name_list_sequentially(
        self,
        project_id: str,
        changed_input_data_list: list[ChangedInputData],
    ) -> None:
        """複数の入力データの名前を逐次的に変更します。"""
        success_count = 0

        logger.info(f"{len(changed_input_data_list)} 件の入力データの名前を変更します。")

        for input_data_index, changed_input_data in enumerate(changed_input_data_list):
            if (input_data_index + 1) % 100 == 0:
                logger.info(f"{input_data_index + 1}件目の入力データの名前を変更します。")

            try:
                result = self.change_input_data_name(
                    project_id,
                    changed_input_data.input_data_id,
                    new_input_data_name=changed_input_data.input_data_name,
                )
                if result:
                    success_count += 1
            except Exception:
                logger.warning(f"input_data_id='{changed_input_data.input_data_id}'の入力データの名前を変更するのに失敗しました。", exc_info=True)
                continue

        logger.info(f"{success_count} / {len(changed_input_data_list)} 件の入力データの名前を変更しました。")

    def _change_input_data_name_wrapper(self, changed_input_data: ChangedInputData, project_id: str) -> bool:
        try:
            return self.change_input_data_name(
                project_id,
                input_data_id=changed_input_data.input_data_id,
                new_input_data_name=changed_input_data.input_data_name,
            )
        except Exception:
            logger.warning(f"input_data_id='{changed_input_data.input_data_id}'の入力データの名前を変更するのに失敗しました。", exc_info=True)
            return False

    def change_input_data_name_list_in_parallel(
        self,
        project_id: str,
        changed_input_data_list: list[ChangedInputData],
        parallelism: int,
    ) -> None:
        """複数の入力データの名前を並列的に変更します。"""

        success_count = 0

        logger.info(f"{len(changed_input_data_list)} 件の入力データの名前を変更します。{parallelism}個のプロセスを使用して並列でに実行します。")

        partial_func = partial(self._change_input_data_name_wrapper, project_id=project_id)
        with multiprocessing.Pool(parallelism) as pool:
            result_bool_list = pool.map(partial_func, changed_input_data_list)
            success_count = len([e for e in result_bool_list if e])

        logger.info(f"{success_count} / {len(changed_input_data_list)} 件の入力データの名前を変更しました。")


def create_changed_input_data_list_from_dict(input_data_dict_list: list[dict[str, str]]) -> list[ChangedInputData]:
    return [ChangedInputData.from_dict(e) for e in input_data_dict_list]


def create_changed_input_data_list_from_csv(csv_file: Path) -> list[ChangedInputData]:
    """入力データの情報が記載されているCSVを読み込み、ChangedInputDataのlistを返します。
    CSVには以下の列が存在します。
    * input_data_id
    * input_data_name

    Args:
        csv_file (Path): CSVファイルのパス

    Returns:
        変更対象の入力データのlist
    """
    df_input_data = pandas.read_csv(
        csv_file,
        # 文字列として読み込むようにする
        dtype={"input_data_id": "string", "input_data_name": "string"},
    )

    input_data_dict_list = df_input_data.to_dict("records")
    return [ChangedInputData.from_dict(e) for e in input_data_dict_list]


class ChangeInputDataName(CommandLine):
    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli input_data change_name: error:"  # noqa: N806

        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず ``--yes`` を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        main_obj = ChangeInputDataNameMain(self.service, all_yes=self.all_yes)

        if args.csv is not None:
            changed_input_data_list = create_changed_input_data_list_from_csv(args.csv)

        elif args.json is not None:
            input_data_dict_list = get_json_from_args(args.json)
            if not isinstance(input_data_dict_list, list):
                print("annofabcli input_data change_name: error: JSON形式が不正です。オブジェクトの配列を指定してください。", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            changed_input_data_list = create_changed_input_data_list_from_dict(input_data_dict_list)
        else:
            raise RuntimeError("'--csv'または'--json'のいずれかを指定してください。")

        project_id: str = args.project_id
        if args.parallelism is not None:
            main_obj.change_input_data_name_list_in_parallel(project_id, changed_input_data_list=changed_input_data_list, parallelism=args.parallelism)
        else:
            main_obj.change_input_data_name_list_sequentially(project_id, changed_input_data_list=changed_input_data_list)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeInputDataName(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    file_group = parser.add_mutually_exclusive_group(required=True)
    file_group.add_argument(
        "--csv",
        type=Path,
        help=(
            "変更対象の入力データが記載されたCSVファイルのパスを指定してください。\n"
            "CSVのフォーマットは以下の通りです。"
            "\n"
            " * ヘッダ行あり, カンマ区切り\n"
            " * input_data_id (required)\n"
            " * input_data_name (required)\n"
        ),
    )

    JSON_SAMPLE = '[{"input_data_id":"id", "input_data_name":"new_name"}]'  # noqa: N806
    file_group.add_argument(
        "--json",
        type=str,
        help=(
            "変更対象の入力データと変更後の名前をJSON形式で指定してください。\n"
            "JSONの各キーは ``--csv`` に渡すCSVの各列に対応しています。\n"
            "``file://`` を先頭に付けるとjsonファイルを指定できます。\n"
            f"(ex) ``{JSON_SAMPLE}``"
        ),
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "change_name"
    subcommand_help = "入力データ名を変更します。"
    epilog = "オーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
