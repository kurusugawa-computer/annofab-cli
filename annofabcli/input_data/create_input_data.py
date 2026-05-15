import argparse
import logging
import re
import sys
from dataclasses import dataclass
from functools import partial
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import annofabapi
import pandas
import requests
from annofabapi.exceptions import CheckSumError
from annofabapi.models import ProjectMemberRole
from dataclasses_json import DataClassJsonMixin

import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    prompt_yesnoall,
)
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import get_file_scheme_path

logger = logging.getLogger(__name__)


@dataclass
class CsvInputData(DataClassJsonMixin):
    """
    CSVに記載されている入力データ
    """

    input_data_name: str
    input_data_path: str
    input_data_id: str | None = None


@dataclass
class InputDataForCreate(DataClassJsonMixin):
    """
    create用の入力データ
    """

    input_data_name: str
    input_data_path: str
    input_data_id: str


def convert_input_data_name_to_input_data_id(input_data_name: str) -> str:
    """
    入力データ名から、入力データIDを生成します。
    * IDに使えない文字以外は`__`に変換する。
    """
    return re.sub(r"[^a-zA-Z0-9_.-]", "__", input_data_name)


def read_input_data_csv(csv_file: Path) -> pandas.DataFrame:
    """入力データの情報が記載されているCSVを読み込み、pandas.DataFrameを返します。

    DataFrameには以下の列が存在します。
    * input_data_name
    * input_data_path
    * input_data_id

    Args:
        csv_file: CSVファイルのパス

    Returns:
        CSVの情報が格納されたpandas.DataFrame

    Raises:
        ValueError: 必須列が不足している場合
    """
    df = pandas.read_csv(str(csv_file), dtype=str)

    required_columns = {"input_data_name", "input_data_path"}
    if not required_columns.issubset(df.columns):
        raise ValueError("CSV形式が不正です。ヘッダ行に 'input_data_name' と 'input_data_path' を指定してください。")

    if "input_data_id" not in df.columns:
        df["input_data_id"] = None

    return df


def is_duplicated_input_data(df: pandas.DataFrame) -> bool:
    """DataFrame内のinput_data_name または input_data_pathが重複しているかどうかを返します。

    Args:
        df: 入力データが格納されているDataFrame

    Returns:
        重複している場合はTrue
    """
    df_duplicated_input_data_name = df[df["input_data_name"].duplicated()]
    result = False
    if len(df_duplicated_input_data_name) > 0:
        logger.warning(f"'input_data_name'が重複しています。\n{df_duplicated_input_data_name['input_data_name'].unique()}")
        result = True

    df_duplicated_input_data_path = df[df["input_data_path"].duplicated()]
    if len(df_duplicated_input_data_path) > 0:
        logger.warning(f"'input_data_path'が重複しています。\n{df_duplicated_input_data_path['input_data_path'].unique()}")
        result = True

    return result


class SubCreateInputData:
    """
    1個の入力データを作成するためのクラス。multiprocessing.Pool対応。

    Args:
        service:
        facade:
        all_yes:
    """

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, all_yes: bool = False) -> None:  # noqa: FBT001, FBT002
        self.service = service
        self.facade = facade
        self.all_yes = all_yes

    def create_input_data(self, project_id: str, input_data: InputDataForCreate, last_updated_datetime: str | None = None) -> None:
        request_body: dict[str, Any] = {"last_updated_datetime": last_updated_datetime}

        file_path = get_file_scheme_path(input_data.input_data_path)
        if file_path is not None:
            request_body.update({"input_data_name": input_data.input_data_name})
            logger.debug(f"'{file_path}'を入力データとして作成します。input_data_name='{input_data.input_data_name}'")
            self.service.wrapper.put_input_data_from_file(project_id, input_data_id=input_data.input_data_id, file_path=file_path, request_body=request_body)

        else:
            request_body.update(
                {
                    "input_data_name": input_data.input_data_name,
                    "input_data_path": input_data.input_data_path,
                }
            )

            self.service.api.put_input_data(project_id, input_data.input_data_id, request_body=request_body)

    def confirm_processing(self, confirm_message: str) -> bool:
        """
        `all_yes`属性を見て、処理するかどうかユーザに問い合わせる。
        "ALL"が入力されたら、`all_yes`属性をTrueにする

        Args:
            confirm_message: 確認メッセージ

        Returns:
            YesならTrue、NoならFalse
        """
        if self.all_yes:
            return True

        yes, all_yes = prompt_yesnoall(confirm_message)

        if all_yes:
            self.all_yes = True

        return yes

    def confirm_create_input_data(self, input_data: InputDataForCreate, already_exists: bool = False) -> bool:  # noqa: FBT001, FBT002
        if already_exists:
            message_for_confirm = f"input_data_name='{input_data.input_data_name}', input_data_id='{input_data.input_data_id}' の入力データを上書きして作成しますか？"
        else:
            message_for_confirm = f"input_data_name='{input_data.input_data_name}', input_data_id='{input_data.input_data_id}' の入力データを作成しますか？"

        return self.confirm_processing(message_for_confirm)

    def create_input_data_main_wrapper(self, tpl: tuple[int, CsvInputData], *, project_id: str, overwrite: bool) -> bool:
        input_data_index, csv_input_data = tpl
        return self.create_input_data_main(project_id, csv_input_data, input_data_index=input_data_index, overwrite=overwrite)

    def create_input_data_main(self, project_id: str, csv_input_data: CsvInputData, *, input_data_index: int, overwrite: bool = False) -> bool:
        input_data = InputDataForCreate(
            input_data_name=csv_input_data.input_data_name,
            input_data_path=csv_input_data.input_data_path,
            input_data_id=csv_input_data.input_data_id if csv_input_data.input_data_id is not None else convert_input_data_name_to_input_data_id(csv_input_data.input_data_name),
        )
        log_message_prefix = f"{input_data_index + 1}件目 :: "
        last_updated_datetime = None
        dict_input_data = self.service.wrapper.get_input_data_or_none(project_id, input_data.input_data_id)

        if dict_input_data is not None:
            if overwrite:
                logger.debug(f"{log_message_prefix}input_data_id='{input_data.input_data_id}'の入力データはすでに存在します。")
                last_updated_datetime = dict_input_data["updated_datetime"]
            else:
                logger.debug(
                    f"{log_message_prefix}input_data_id='{input_data.input_data_id}'の入力データがすでに存在するので入力データの作成をスキップします。"
                    "入力データを上書きして作成する場合は、引数に '--overwrite' を指定してください。"
                )
                return False

        file_path = get_file_scheme_path(input_data.input_data_path)
        if file_path is not None and not Path(file_path).exists():
            logger.warning(f"input_data_path='{input_data.input_data_path}'にファイルは存在しません。入力データの作成をスキップします。")
            return False

        if not self.confirm_create_input_data(input_data, already_exists=last_updated_datetime is not None):
            return False

        try:
            self.create_input_data(project_id, input_data, last_updated_datetime=last_updated_datetime)
            logger.debug(f"{log_message_prefix}入力データを作成しました。 :: input_data_id='{input_data.input_data_id}', input_data_name='{input_data.input_data_name}'")
            return True  # noqa: TRY300

        except requests.exceptions.HTTPError:
            logger.warning(
                f"{log_message_prefix}入力データの作成に失敗しました。 :: input_data_id='{input_data.input_data_id}', input_data_name='{input_data.input_data_name}'",
                exc_info=True,
            )
            return False
        except CheckSumError:
            logger.warning(
                f"{log_message_prefix}入力データを作成しましたが、データが破損している可能性があります。 :: input_data_id='{input_data.input_data_id}', input_data_name='{input_data.input_data_name}'",
                exc_info=True,
            )
            return False


class CreateInputData(CommandLine):
    """
    入力データを作成する。
    """

    COMMON_MESSAGE = "annofabcli input_data create: error:"

    def create_input_data_list(
        self,
        project_id: str,
        input_data_list: list[CsvInputData],
        overwrite: bool = False,  # noqa: FBT001, FBT002
        parallelism: int | None = None,
    ) -> None:
        """入力データを一括で作成する。"""

        project_title = self.facade.get_project_title(project_id)
        logger.info(f"プロジェクト'{project_title}'に、{len(input_data_list)} 件の入力データを作成します。")

        count_create_input_data = 0

        obj = SubCreateInputData(service=self.service, facade=self.facade, all_yes=self.all_yes)
        if parallelism is not None:
            partial_func = partial(obj.create_input_data_main_wrapper, project_id=project_id, overwrite=overwrite)
            with Pool(parallelism) as pool:
                result_bool_list = pool.map(partial_func, enumerate(input_data_list))
                count_create_input_data = len([e for e in result_bool_list if e])

        else:
            for input_data_index, csv_input_data in enumerate(input_data_list):
                result = obj.create_input_data_main(project_id, csv_input_data=csv_input_data, input_data_index=input_data_index, overwrite=overwrite)
                if result:
                    count_create_input_data += 1

        logger.info(f"プロジェクト'{project_title}'に、{count_create_input_data} / {len(input_data_list)} 件の入力データを作成しました。")

    @staticmethod
    def get_input_data_list_from_df(df: pandas.DataFrame) -> list[CsvInputData]:
        def create_input_data_from_row(e: Any) -> CsvInputData:  # noqa: ANN401
            input_data_id = e.input_data_id if not pandas.isna(e.input_data_id) else None
            return CsvInputData(
                input_data_name=e.input_data_name,
                input_data_path=e.input_data_path,
                input_data_id=input_data_id,
            )

        return [create_input_data_from_row(e) for e in df.itertuples()]

    @staticmethod
    def get_input_data_list_from_dict(input_data_dict_list: list[dict[str, Any]], allow_duplicated_input_data: bool) -> list[CsvInputData]:  # noqa: FBT001
        df = pandas.DataFrame(input_data_dict_list)
        df_duplicated_input_data_name = df[df["input_data_name"].duplicated()]
        if len(df_duplicated_input_data_name) > 0:
            logger.warning(f"`input_data_name`が重複しています。\n{df_duplicated_input_data_name['input_data_name'].unique()}")
            if not allow_duplicated_input_data:
                raise RuntimeError("`input_data_name`が重複しています。")

        df_duplicated_input_data_path = df[df["input_data_path"].duplicated()]
        if len(df_duplicated_input_data_path) > 0:
            logger.warning(f"`input_data_path`が重複しています。\n{df_duplicated_input_data_path['input_data_path'].unique()}")
            if not allow_duplicated_input_data:
                raise RuntimeError("`input_data_path`が重複しています。")

        return [CsvInputData.from_dict(e) for e in input_data_dict_list]

    def validate(self, args: argparse.Namespace) -> bool:
        if args.csv is not None and not Path(args.csv).exists():
            print(f"{self.COMMON_MESSAGE} argument --csv: ファイルパスが存在しません。 '{args.csv}'", file=sys.stderr)  # noqa: T201
            return False

        if (args.csv is not None or args.json is not None) and args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、'--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        if args.csv is not None:
            try:
                df = read_input_data_csv(args.csv)
            except ValueError as e:
                print(f"{self.COMMON_MESSAGE} argument --csv: {e}", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

            is_duplicated = is_duplicated_input_data(df)
            if not args.allow_duplicated_input_data and is_duplicated:
                print(  # noqa: T201
                    f"{self.COMMON_MESSAGE} argument --csv: '{args.csv}' に記載されている'input_data_name'または'input_data_path'が重複しているため、入力データを作成しません。"
                    f"重複している状態で入力データを作成する際は、'--allow_duplicated_input_data'を指定してください。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

            input_data_list = self.get_input_data_list_from_df(df)
            self.create_input_data_list(project_id, input_data_list=input_data_list, overwrite=args.overwrite, parallelism=args.parallelism)

        elif args.json is not None:
            input_data_dict_list = get_json_from_args(args.json)
            if not isinstance(input_data_dict_list, list):
                print(f"{self.COMMON_MESSAGE} argument --json: JSON形式が不正です。オブジェクトの配列を指定してください。", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

            input_data_list = self.get_input_data_list_from_dict(input_data_dict_list, allow_duplicated_input_data=args.allow_duplicated_input_data)
            self.create_input_data_list(project_id, input_data_list=input_data_list, overwrite=args.overwrite, parallelism=args.parallelism)

        else:
            print("引数が不正です。", file=sys.stderr)  # noqa: T201


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CreateInputData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    file_group = parser.add_mutually_exclusive_group(required=True)
    file_group.add_argument(
        "--csv",
        type=Path,
        help=(
            "入力データが記載されたCSVファイルのパスを指定してください。CSVのフォーマットは、以下の通りです。"
            "詳細は https://annofab-cli.readthedocs.io/ja/latest/command_reference/input_data/create.html を参照してください。\n\n"
            " * ヘッダ行あり, カンマ区切り\n"
            " * 必須列: input_data_name, input_data_path\n"
            " * 任意列: input_data_id\n"
        ),
    )

    json_sample = '[{"input_data_name":"data1", "input_data_path":"file://lenna.png"}]'
    file_group.add_argument(
        "--json",
        type=str,
        help=(
            "作成対象の入力データをJSON形式で指定してください。\n"
            "JSONの各キーは ``--csv`` に渡すCSVの各列に対応しています。\n"
            "``file://`` を先頭に付けるとjsonファイルを指定できます。\n"
            f"(ex) ``{json_sample}``"
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="指定した場合、input_data_idがすでに存在していたら上書きします。指定しなければ、スキップします。",
    )

    parser.add_argument(
        "--allow_duplicated_input_data",
        action="store_true",
        help="``--csv`` , ``--json`` に渡した入力データの重複（input_data_name, input_data_path）を許可します。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="並列度。指定しない場合は、逐次的に処理します。指定する場合は必ず ``--yes`` を指定してください。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "create"
    subcommand_help = "入力データを作成します。"
    description = "入力データを作成します。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
