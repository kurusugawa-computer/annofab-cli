from __future__ import annotations

import argparse
import logging
import multiprocessing
import sys
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Optional
from enum import Enum

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


class UpdateResult(Enum):
    """更新結果の種類"""
    SUCCESS = "success"
    INPUT_ERROR = "input_error"  # 入力情報エラー（存在しないinput_data_id等）
    EXCEPTION_ERROR = "exception_error"  # 例外エラー


@dataclass
class UpdatedInputData(DataClassJsonMixin):
    """
    更新される入力データ
    """

    input_data_id: str
    """更新対象の入力データを表すID"""
    input_data_name: Optional[str] = None
    """変更後の入力データ名（指定した場合のみ更新）"""
    input_data_path: Optional[str] = None
    """変更後の入力データパス（指定した場合のみ更新）"""


class UpdateInputDataMain(CommandLineWithConfirm):
    def __init__(self, service: annofabapi.Resource, *, all_yes: bool = False) -> None:
        self.service = service
        CommandLineWithConfirm.__init__(self, all_yes)

    def update_input_data(
        self,
        project_id: str,
        input_data_id: str,
        new_input_data_name: Optional[str] = None,
        new_input_data_path: Optional[str] = None,
    ) -> UpdateResult:
        """
        1個の入力データを更新します。
        """
        old_input_data = self.service.wrapper.get_input_data_or_none(project_id, input_data_id)
        if old_input_data is None:
            logger.warning(f"input_data_id='{input_data_id}'である入力データは存在しません。")
            return UpdateResult.INPUT_ERROR

        # 更新する内容の確認メッセージを作成
        changes = []
        if new_input_data_name is not None:
            changes.append(f"input_data_name='{old_input_data['input_data_name']}'を'{new_input_data_name}'に変更")
        if new_input_data_path is not None:
            changes.append(f"input_data_path='{old_input_data['input_data_path']}'を'{new_input_data_path}'に変更")

        if len(changes) == 0:
            logger.warning(f"input_data_id='{input_data_id}': 更新する内容が指定されていません。")
            return UpdateResult.INPUT_ERROR

        change_message = "、".join(changes)
        if not self.confirm_processing(f"input_data_id='{input_data_id}' :: {change_message}しますか？"):
            return UpdateResult.INPUT_ERROR

        request_body = old_input_data
        request_body["last_updated_datetime"] = old_input_data["updated_datetime"]

        if new_input_data_name is not None:
            request_body["input_data_name"] = new_input_data_name
        if new_input_data_path is not None:
            request_body["input_data_path"] = new_input_data_path

        self.service.api.put_input_data(project_id, input_data_id, request_body=request_body)
        return UpdateResult.SUCCESS

    def update_input_data_list_sequentially(
        self,
        project_id: str,
        updated_input_data_list: list[UpdatedInputData],
    ) -> None:
        """複数の入力データを逐次的に更新します。"""
        success_count = 0
        input_error_count = 0  # 入力情報エラー（存在しないinput_data_id等）
        exception_count = 0    # 例外エラー

        logger.info(f"{len(updated_input_data_list)} 件の入力データを更新します。")

        for input_data_index, updated_input_data in enumerate(updated_input_data_list):
            if (input_data_index + 1) % 1000 == 0:
                logger.info(f"{input_data_index + 1}件目の入力データを更新します。")

            try:
                result = self.update_input_data(
                    project_id,
                    updated_input_data.input_data_id,
                    new_input_data_name=updated_input_data.input_data_name,
                    new_input_data_path=updated_input_data.input_data_path,
                )
                if result == UpdateResult.SUCCESS:
                    success_count += 1
                else:
                    input_error_count += 1
            except Exception:
                logger.warning(f"input_data_id='{updated_input_data.input_data_id}'の入力データを更新するのに失敗しました。", exc_info=True)
                exception_count += 1
                continue

        total_failure_count = input_error_count + exception_count
        logger.info(f"{success_count} / {len(updated_input_data_list)} 件の入力データを更新しました。（成功: {success_count}件, 失敗: {total_failure_count}件 [入力エラー: {input_error_count}件, 例外エラー: {exception_count}件]）")

    def _update_input_data_wrapper(self, updated_input_data: UpdatedInputData, project_id: str) -> UpdateResult:
        try:
            return self.update_input_data(
                project_id,
                input_data_id=updated_input_data.input_data_id,
                new_input_data_name=updated_input_data.input_data_name,
                new_input_data_path=updated_input_data.input_data_path,
            )
        except Exception:
            logger.warning(f"input_data_id='{updated_input_data.input_data_id}'の入力データを更新するのに失敗しました。", exc_info=True)
            return UpdateResult.EXCEPTION_ERROR

    def update_input_data_list_in_parallel(
        self,
        project_id: str,
        updated_input_data_list: list[UpdatedInputData],
        parallelism: int,
    ) -> None:
        """複数の入力データを並列的に更新します。"""

        logger.info(f"{len(updated_input_data_list)} 件の入力データを更新します。{parallelism}個のプロセスを使用して並列でに実行します。")

        partial_func = partial(self._update_input_data_wrapper, project_id=project_id)
        with multiprocessing.Pool(parallelism) as pool:
            result_list = pool.map(partial_func, updated_input_data_list)
            success_count = len([e for e in result_list if e == UpdateResult.SUCCESS])
            input_error_count = len([e for e in result_list if e == UpdateResult.INPUT_ERROR])
            exception_count = len([e for e in result_list if e == UpdateResult.EXCEPTION_ERROR])

        total_failure_count = input_error_count + exception_count
        logger.info(f"{success_count} / {len(updated_input_data_list)} 件の入力データを更新しました。（成功: {success_count}件, 失敗: {total_failure_count}件 [入力エラー: {input_error_count}件, 例外エラー: {exception_count}件]）")


def create_updated_input_data_list_from_dict(input_data_dict_list: list[dict[str, str]]) -> list[UpdatedInputData]:
    return [UpdatedInputData.from_dict(e) for e in input_data_dict_list]


def create_updated_input_data_list_from_csv(csv_file: Path) -> list[UpdatedInputData]:
    """入力データの情報が記載されているCSVを読み込み、UpdatedInputDataのlistを返します。
    CSVには以下の列が存在します。
    * input_data_id (必須)
    * input_data_name (任意)
    * input_data_path (任意)

    Args:
        csv_file (Path): CSVファイルのパス

    Returns:
        更新対象の入力データのlist
    """
    df_input_data = pandas.read_csv(
        csv_file,
        # 文字列として読み込むようにする
        dtype={"input_data_id": "string", "input_data_name": "string", "input_data_path": "string"},
    )

    input_data_dict_list = df_input_data.to_dict("records")
    return [UpdatedInputData.from_dict(e) for e in input_data_dict_list]


class UpdateInputData(CommandLine):
    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli input_data update: error:"  # noqa: N806

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

        main_obj = UpdateInputDataMain(self.service, all_yes=self.all_yes)

        if args.csv is not None:
            updated_input_data_list = create_updated_input_data_list_from_csv(args.csv)

        elif args.json is not None:
            input_data_dict_list = get_json_from_args(args.json)
            if not isinstance(input_data_dict_list, list):
                print("annofabcli input_data update: error: JSON形式が不正です。オブジェクトの配列を指定してください。", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            updated_input_data_list = create_updated_input_data_list_from_dict(input_data_dict_list)
        else:
            raise RuntimeError("'--csv'または'--json'のいずれかを指定してください。")

        project_id: str = args.project_id
        if args.parallelism is not None:
            main_obj.update_input_data_list_in_parallel(project_id, updated_input_data_list=updated_input_data_list, parallelism=args.parallelism)
        else:
            main_obj.update_input_data_list_sequentially(project_id, updated_input_data_list=updated_input_data_list)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateInputData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    file_group = parser.add_mutually_exclusive_group(required=True)
    file_group.add_argument(
        "--csv",
        type=Path,
        help=(
            "更新対象の入力データと更新後の値が記載されたCSVファイルのパスを指定します。\n"
            "CSVのフォーマットは以下の通りです。"
            "\n"
            " * ヘッダ行あり, カンマ区切り\n"
            " * input_data_id (required)\n"
            " * input_data_name (optional)\n"
            " * input_data_path (optional)\n"
            "更新しないプロパティは、セルの値を空欄にしてください。\n"
        ),
    )

    JSON_SAMPLE = '[{"input_data_id":"id1","input_data_name":"new_name1"},{"input_data_id":"id2","input_data_path":"new_path2"}]'  # noqa: N806
    file_group.add_argument(
        "--json",
        type=str,
        help=(
            "更新対象の入力データと更新後の値をJSON形式で指定します。\n"
            "JSONの各キーは ``--csv`` に渡すCSVの各列に対応しています。\n"
            "``file://`` を先頭に付けるとjsonファイルを指定できます。\n"
            f"(ex) ``{JSON_SAMPLE}`` \n"
            "更新しないプロパティは、キーを記載しないか値をnullにしてください。\n"
        ),
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）。指定しない場合は、逐次的に処理します。指定する場合は ``--yes`` も一緒に指定する必要があります。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "update"
    subcommand_help = "入力データの名前やパスを更新します。"
    epilog = "オーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
