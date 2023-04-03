from __future__ import annotations
from pathlib import Path
import argparse
import logging
import multiprocessing
import sys
from functools import partial
from typing import Any, Dict, List, Optional, Tuple

import annofabapi
from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    AbstractCommandLineWithConfirmInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_json_from_args
)
from annofabcli.common.facade import AnnofabApiFacade

import argparse
import logging
import sys
import uuid
from dataclasses import dataclass
from functools import partial
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Dict, List, Optional

import annofabapi
import pandas
import requests
from annofabapi.exceptions import CheckSumError
from annofabapi.models import ProjectMemberRole
from dataclasses_json import DataClassJsonMixin

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    prompt_yesnoall,
)
from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import get_file_scheme_path

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




class ChangeInputDataNameMain(AbstractCommandLineWithConfirmInterface):
    def __init__(self, service: annofabapi.Resource, *, all_yes: bool = False) -> None:
        self.service = service
        AbstractCommandLineWithConfirmInterface.__init__(self, all_yes)

    def change_input_data_name(self, project_id:str, input_data_id: str, new_input_data_name:str) -> bool:

        """
        1個の入力データの名前を変更します。
        """
        old_input_data = self.service.wrapper.get_input_data(project_id, input_data_id)
        if old_input_data is None:
            logger.warning(f"input_data_id='{input_data_id}'である入力データは存在しません。")
            return False

        if not self.confirm_processing(f"input_data_id='{input_data_id}' :: "
            f"input_data_name='{old_input_data['input_data_name']}'を'{new_input_data_name}'に変更しますか？"):
            return False

        request_body = old_input_data
        request_body["last_updated_datetime"] = old_input_data["updated_datetime"]
        request_body["input_data_name"] = new_input_data_name

        self.service.api.put_input_data(self.project_id, input_data_id, request_body=request_body)
        return True



    def change_input_data_name_list_sequentially(
        self,
        project_id: str,
        changed_input_data_list: list[ChangedInputData],
    ) -> None:
        """複数の入力データの名前を逐次的に変更します。
        """
        success_count = 0

        logger.info(f"{len(changed_input_data_list)} 件の入力データの名前を変更します。")

        for input_data_index, changed_input_data in enumerate(changed_input_data_list):
            if (input_data_index+1) % 100 == 0:
                logger.info(f"{input_data_index+1}件目の入力データの名前を変更します。")

            try:
                result = self.change_input_data_name(
                    project_id,
                    changed_input_data.input_data_id,
                    new_input_data_name=changed_input_data.new_input_data_name
                )
                if result:
                    success_count += 1
            except Exception:
                logger.warning(f"input_data_id='{changed_input_data.input_data_id}'の入力データの名前を変更するのに失敗しました。", exc_info=True)
                continue


        logger.info(f"{success_count} / {len(changed_input_data_list)} 件の入力データの名前を変更しました。")

    def change_input_data_name_list_in_parallel(
        self,
        project_id: str,
        changed_input_data_list: list[ChangedInputData],
        parallelism: int,
    ) -> None:
        """複数の入力データの名前を並列的に変更します。
        """

        def wrapper(
            changed_input_data: ChangedInputData, project_id: str
        ) -> bool:
            try:
                return self.change_input_data_name(
                    project_id,
                    input_data_id=changed_input_data.input_data_id,
                    new_input_data_name=changed_input_data.new_input_data_name
                )
            except Exception:
                logger.warning(f"input_data_id='{changed_input_data.input_data_id}'の入力データの名前を変更するのに失敗しました。", exc_info=True)
                return False

        success_count = 0

        logger.info(f"{len(changed_input_data_list)} 件の入力データの名前を変更します。{parallelism}個のプロセスを使用して並列でに実行します。")

        partial_func = partial(
            wrapper,
            project_id=project_id,
        )

        with multiprocessing.Pool(parallelism) as pool:
            result_bool_list = pool.map(partial_func, enumerate(changed_input_data_list))
            success_count = len([e for e in result_bool_list if e])

        logger.info(f"{success_count} / {len(changed_input_data_list)} 件の入力データの名前を変更しました。")
        





class ChangeInputDataName(AbstractCommandLineInterface):
    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli input_data change_name: error:"

        if args.parallelism is not None and not args.yes:
            print(
                f"{COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず ``--yes`` を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        if args.csv is not None:
            df = read_input_data_csv(args.csv)
            is_duplicated = is_duplicated_input_data(df)
            if not args.allow_duplicated_input_data and is_duplicated:
                print(
                    f"{self.COMMON_MESSAGE} argument --csv: '{args.csv}' に記載されている'input_data_name'または'input_data_path'が重複しているため、入力データを登録しません。"  # noqa: E501
                    f"重複している状態で入力データを登録する際は、'--allow_duplicated_input_data'を指定してください。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

            input_data_list = self.get_input_data_list_from_df(df)
            self.put_input_data_list(
                project_id, input_data_list=input_data_list, overwrite=args.overwrite, parallelism=args.parallelism
            )

        elif args.json is not None:
            input_data_dict_list: list[dict[str,str]] = get_json_from_args(args.json)
            input_data_list = self.get_input_data_list_from_dict(
                input_data_dict_list, allow_duplicated_input_data=args.allow_duplicated_input_data
            )
            self.put_input_data_list(
                project_id, input_data_list=input_data_list, overwrite=args.overwrite, parallelism=args.parallelism
            )



        input_data_id_list = annofabcli.common.cli.get_list_from_args(args.input_data_id)
        metadata = annofabcli.common.cli.get_json_from_args(args.metadata)
        super().validate_project(args.project_id, [ProjectMemberRole.OWNER])
        main_obj = UpdateMetadataMain(self.service, all_yes=args.yes)
        main_obj.update_metadata_of_input_data(
            args.project_id,
            input_data_id_list,
            metadata,
            overwrite_metadata=args.overwrite,
            parallelism=args.parallelism,
        )


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
            "入力データが記載されたCSVファイルのパスを指定してください。\n"
            "CSVのフォーマットは以下の通りです。"
            "詳細は https://annofab-cli.readthedocs.io/ja/latest/command_reference/input_data/put.html を参照してください。\n"
            "\n"
            " * ヘッダ行なし, カンマ区切り\n"
            " * 1列目: input_data_name (required)\n"
            " * 2列目: input_data_path (required)\n"
            " * 3列目: input_data_id\n"
            " * 4列目: sign_required (bool)\n"
        ),
    )

    JSON_SAMPLE = (
        '[{"input_data_name":"", "input_data_path":"file://lenna.png", "input_data_id":"foo","sign_required":false}]'
    )
    file_group.add_argument(
        "--json",
        type=str,
        help=(
            "登録対象の入力データをJSON形式で指定してください。\n"
            "JSONの各キーは ``--csv`` に渡すCSVの各列に対応しています。\n"
            "``file://`` を先頭に付けるとjsonファイルを指定できます。\n"
            f"(ex) ``{JSON_SAMPLE}``"
        ),
    )



    parser.add_argument(
        "--parallelism", type=int, help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "change_name"
    subcommand_help = "入力データ名を変更します。"
    epilog = "オーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, epilog=epilog
    )
    parse_args(parser)
    return parser
