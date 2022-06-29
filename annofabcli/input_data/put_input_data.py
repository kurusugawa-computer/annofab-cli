import argparse
import logging
import sys
import uuid
import zipfile
from dataclasses import dataclass
from functools import partial
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Dict, List, Optional

import annofabapi
import pandas
import requests
from annofabapi.exceptions import CheckSumError
from annofabapi.models import ProjectJobType, ProjectMemberRole
from dataclasses_json import DataClassJsonMixin

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    get_wait_options_from_args,
    prompt_yesnoall,
)
from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import get_file_scheme_path

logger = logging.getLogger(__name__)

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)


@dataclass
class CsvInputData(DataClassJsonMixin):
    """
    CSVに記載されている入力データ
    """

    input_data_name: str
    input_data_path: str
    input_data_id: Optional[str] = None
    sign_required: Optional[bool] = None


@dataclass
class InputDataForPut(DataClassJsonMixin):
    """
    put用の入力データ
    """

    input_data_name: str
    input_data_path: str
    input_data_id: str
    sign_required: Optional[bool]


def read_input_data_csv(csv_file: Path) -> pandas.DataFrame:
    """入力データの情報が記載されているCSVを読み込み、pandas.DataFrameを返します。
    DataFrameには以下の列が存在します。
    * input_data_name
    * input_data_path
    * input_data_id
    * sign_required

    Args:
        csv_file (Path): CSVファイルのパス

    Returns:
        CSVの情報が格納されたpandas.DataFrame
    """
    df = pandas.read_csv(
        str(csv_file),
        sep=",",
        header=None,
        names=("input_data_name", "input_data_path", "input_data_id", "sign_required"),
        # IDと名前は必ず文字列として読み込むようにする
        dtype={"input_data_id": str, "input_data_name": str},
    )
    return df


def is_duplicated_input_data(df: pandas.DataFrame) -> bool:
    """DataFrame内のinput_data_name または input_data_pathが重複しているかどうかを返します。

    Args:
        df (pandas.DataFrame): 入力データが格納されているDataFrame

    Returns:
        bool: _description_
    """
    df_duplicated_input_data_name = df[df["input_data_name"].duplicated()]
    result = False
    if len(df_duplicated_input_data_name) > 0:
        logger.warning(f"'input_data_name'が重複しています。\n" f"{df_duplicated_input_data_name['input_data_name'].unique()}")
        result = True

    df_duplicated_input_data_path = df[df["input_data_path"].duplicated()]
    if len(df_duplicated_input_data_path) > 0:
        logger.warning(f"'input_data_path'が重複しています。\n" f"{df_duplicated_input_data_path['input_data_path'].unique()}")
        result = True

    return result


class SubPutInputData:
    """
    1個の入力データを登録するためのクラス。multiprocessing.Pool対応。

    Args:
        service:
        facade:
        all_yes:
    """

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, all_yes: bool = False):
        self.service = service
        self.facade = facade
        self.all_yes = all_yes

    def put_input_data(
        self, project_id: str, csv_input_data: InputDataForPut, last_updated_datetime: Optional[str] = None
    ):

        request_body: Dict[str, Any] = {"last_updated_datetime": last_updated_datetime}

        file_path = get_file_scheme_path(csv_input_data.input_data_path)
        if file_path is not None:
            request_body.update(
                {"input_data_name": csv_input_data.input_data_name, "sign_required": csv_input_data.sign_required}
            )
            logger.debug(f"'{file_path}'を入力データとして登録します。input_data_name={csv_input_data.input_data_name}")
            self.service.wrapper.put_input_data_from_file(
                project_id, input_data_id=csv_input_data.input_data_id, file_path=file_path, request_body=request_body
            )

        else:
            request_body.update(
                {
                    "input_data_name": csv_input_data.input_data_name,
                    "input_data_path": csv_input_data.input_data_path,
                    "sign_required": csv_input_data.sign_required,
                }
            )

            self.service.api.put_input_data(project_id, csv_input_data.input_data_id, request_body=request_body)

    def confirm_processing(self, confirm_message: str) -> bool:
        """
        `all_yes`属性を見て、処理するかどうかユーザに問い合わせる。
        "ALL"が入力されたら、`all_yes`属性をTrueにする

        Args:
            task_id: 処理するtask_id
            confirm_message: 確認メッセージ

        Returns:
            True: Yes, False: No

        """
        if self.all_yes:
            return True

        yes, all_yes = prompt_yesnoall(confirm_message)

        if all_yes:
            self.all_yes = True

        return yes

    def confirm_put_input_data(self, input_data: InputDataForPut, already_exists: bool = False) -> bool:
        message_for_confirm = (
            f"input_data_name='{input_data.input_data_name}', input_data_id='{input_data.input_data_id}' の入力データを登録しますか？"
        )
        if already_exists:
            message_for_confirm = f"input_data_name='{input_data.input_data_name}', input_data_id='{input_data.input_data_id}' の入力データを上書きして登録しますか？"  # noqa: E501
        else:
            message_for_confirm = f"input_data_name='{input_data.input_data_name}', input_data_id='{input_data.input_data_id}' の入力データを登録しますか？"  # noqa: E501

        return self.confirm_processing(message_for_confirm)

    def put_input_data_main(self, project_id: str, csv_input_data: CsvInputData, overwrite: bool = False) -> bool:

        input_data = InputDataForPut(
            input_data_name=csv_input_data.input_data_name,
            input_data_path=csv_input_data.input_data_path,
            input_data_id=csv_input_data.input_data_id
            if csv_input_data.input_data_id is not None
            else str(uuid.uuid4()),
            sign_required=csv_input_data.sign_required,
        )

        last_updated_datetime = None
        dict_input_data = self.service.wrapper.get_input_data_or_none(project_id, input_data.input_data_id)

        if dict_input_data is not None:
            if overwrite:
                logger.debug(f"input_data_id={input_data.input_data_id} はすでに存在します。")
                last_updated_datetime = dict_input_data["updated_datetime"]
            else:
                logger.debug(f"input_data_id={input_data.input_data_id} がすでに存在するのでスキップします。")
                return False

        file_path = get_file_scheme_path(input_data.input_data_path)
        if file_path is not None:
            if not Path(file_path).exists():
                logger.warning(f"{input_data.input_data_path} は存在しません。")
                return False

        if not self.confirm_put_input_data(input_data, already_exists=(last_updated_datetime is not None)):
            return False

        # 入力データを登録
        try:
            self.put_input_data(project_id, input_data, last_updated_datetime=last_updated_datetime)
            logger.debug(
                f"入力データを登録しました。 :: "
                f"input_data_id='{input_data.input_data_id}', "
                f"input_data_name='{input_data.input_data_name}'"
                f"input_data_name='{input_data.input_data_name}'"
            )
            return True

        except requests.exceptions.HTTPError as e:
            logger.warning(e)
            logger.warning(
                f"入力データの登録に失敗しました。"
                f"input_data_id={input_data.input_data_id}, "
                f"input_data_name={input_data.input_data_name}"
            )
            return False
        except CheckSumError as e:
            logger.warning(e)
            logger.warning(
                f"入力データを登録しましたが、データが破損している可能性があります。"
                f"input_data_id={input_data.input_data_id}, "
                f"input_data_name={input_data.input_data_name},"
                f"input_data_name={input_data.input_data_path},"
            )
            return False


class PutInputData(AbstractCommandLineInterface):
    """
    入力データをCSVで登録する。
    """

    COMMON_MESSAGE = "annofabcli input_data put: error:"

    def put_input_data_list(
        self,
        project_id: str,
        input_data_list: List[CsvInputData],
        overwrite: bool = False,
        parallelism: Optional[int] = None,
    ) -> None:
        """
        入力データを一括で登録する。

        Args:
            project_id: 入力データの登録先プロジェクトのプロジェクトID
            input_data_list: 入力データList
            overwrite: Trueならば、input_data_idがすでに存在していたら上書きします。Falseならばスキップします。
            parallelism: 並列度

        """

        project_title = self.facade.get_project_title(project_id)
        logger.info(f"{project_title} に、{len(input_data_list)} 件の入力データを登録します。")

        count_put_input_data = 0

        obj = SubPutInputData(service=self.service, facade=self.facade, all_yes=self.all_yes)
        if parallelism is not None:
            partial_func = partial(obj.put_input_data_main, project_id, overwrite=overwrite)
            with Pool(parallelism) as pool:
                result_bool_list = pool.map(partial_func, input_data_list)
                count_put_input_data = len([e for e in result_bool_list if e])

        else:
            for csv_input_data in input_data_list:
                result = obj.put_input_data_main(project_id, csv_input_data=csv_input_data, overwrite=overwrite)
                if result:
                    count_put_input_data += 1

        logger.info(f"{project_title} に、{count_put_input_data} / {len(input_data_list)} 件の入力データを登録しました。")

    @staticmethod
    def get_input_data_list_from_df(df: pandas.DataFrame) -> List[CsvInputData]:
        def create_input_data(e):
            input_data_id = e.input_data_id if not pandas.isna(e.input_data_id) else None
            sign_required: Optional[bool] = e.sign_required if pandas.notna(e.sign_required) else None
            return CsvInputData(
                input_data_name=e.input_data_name,
                input_data_path=e.input_data_path,
                input_data_id=input_data_id,
                sign_required=sign_required,
            )

        input_data_list = [create_input_data(e) for e in df.itertuples()]

        return input_data_list

    @staticmethod
    def get_input_data_list_from_dict(
        input_data_dict_list: List[Dict[str, Any]], allow_duplicated_input_data: bool
    ) -> List[CsvInputData]:
        # 重複チェック
        df = pandas.DataFrame(input_data_dict_list)
        df_duplicated_input_data_name = df[df["input_data_name"].duplicated()]
        if len(df_duplicated_input_data_name) > 0:
            logger.warning(
                f"`input_data_name`が重複しています。\n" f"{df_duplicated_input_data_name['input_data_name'].unique()}"
            )
            if not allow_duplicated_input_data:
                raise RuntimeError(f"`input_data_name`が重複しています。")

        df_duplicated_input_data_path = df[df["input_data_path"].duplicated()]
        if len(df_duplicated_input_data_path) > 0:
            logger.warning(
                f"`input_data_path`が重複しています。\n" f"{df_duplicated_input_data_path['input_data_path'].unique()}"
            )
            if not allow_duplicated_input_data:
                raise RuntimeError(f"`input_data_path`が重複しています。")

        return CsvInputData.schema().load(input_data_dict_list, many=True, unknown="exclude")

    def put_input_data_from_zip_file(
        self,
        project_id: str,
        zip_file: Path,
        wait_options: WaitOptions,
        input_data_name_for_zip: Optional[str] = None,
        wait: bool = False,
    ) -> None:
        """
        zipファイルを入力データとして登録する

        Args:
            project_id: 入力データの登録先プロジェクトのプロジェクトID
            zip_file: 入力データとして登録するzipファイルのパス
            input_data_name_for_zip: zipファイルのinput_data_name
            wait: 入力データの登録が完了するまで待つかどうか

        """

        project_title = self.facade.get_project_title(project_id)
        logger.info(f"{project_title} に、{str(zip_file)} を登録します。")

        request_body = {}
        if input_data_name_for_zip is not None:
            request_body["input_data_name"] = input_data_name_for_zip

        self.service.wrapper.put_input_data_from_file(
            project_id,
            input_data_id=str(uuid.uuid4()),
            file_path=str(zip_file),
            content_type="application/zip",
            request_body=request_body,
        )
        logger.info(f"入力データの登録中です（サーバ側の処理）。")

        if wait:
            MAX_WAIT_MINUTE = wait_options.max_tries * wait_options.interval / 60
            logger.info(f"最大{MAX_WAIT_MINUTE}分間、処理が終了するまで待ちます。")

            result = self.service.wrapper.wait_for_completion(
                project_id,
                job_type=ProjectJobType.GEN_INPUTS,
                job_access_interval=wait_options.interval,
                max_job_access=wait_options.max_tries,
            )
            if result:
                logger.info(f"入力データの登録が完了しました。")
            else:
                logger.warning(f"入力データの登録に失敗しました。または、{MAX_WAIT_MINUTE}分間待っても、入力データの登録が完了しませんでした。")

    def validate(self, args: argparse.Namespace) -> bool:
        if args.zip is not None:
            if not Path(args.zip).exists():
                print(f"{self.COMMON_MESSAGE} argument --zip: ファイルパスが存在しません。 '{args.zip}'", file=sys.stderr)
                return False

            if not zipfile.is_zipfile(args.zip):
                print(f"{self.COMMON_MESSAGE} argument --zip: zipファイルではありません。 '{args.zip}'", file=sys.stderr)
                return False

            if args.overwrite:
                logger.warning(f"'--zip'オプションを指定しているとき、'--overwrite'オプションは無視されます。")

            if args.parallelism is not None:
                logger.warning(f"'--zip'オプションを指定しているとき、'--parallelism'オプションは無視されます。")

        if args.csv is not None:
            if not Path(args.csv).exists():
                print(f"{self.COMMON_MESSAGE} argument --csv: ファイルパスが存在しません。 '{args.csv}'", file=sys.stderr)
                return False

        if args.csv is not None or args.json is not None:
            if args.wait:
                logger.warning(f"'--csv'/'--json'オプションを指定しているとき、'--wait'オプションは無視されます。")

            if args.input_data_name_for_zip:
                logger.warning(f"'--csv'/'--json'オプションを指定しているとき、'--input_data_name_for_zip'オプションは無視されます。")

            if args.parallelism is not None and not args.yes:
                print(
                    f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず '--yes' を指定してください。",
                    file=sys.stderr,
                )
                return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER])

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
            input_data_dict_list = get_json_from_args(args.json)
            input_data_list = self.get_input_data_list_from_dict(
                input_data_dict_list, allow_duplicated_input_data=args.allow_duplicated_input_data
            )
            self.put_input_data_list(
                project_id, input_data_list=input_data_list, overwrite=args.overwrite, parallelism=args.parallelism
            )

        elif args.zip is not None:
            wait_options = get_wait_options_from_args(get_json_from_args(args.wait_options), DEFAULT_WAIT_OPTIONS)
            self.put_input_data_from_zip_file(
                project_id,
                zip_file=args.zip,
                input_data_name_for_zip=args.input_data_name_for_zip,
                wait=args.wait,
                wait_options=wait_options,
            )

        else:
            print(f"引数が不正です。", file=sys.stderr)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PutInputData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
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

    file_group.add_argument("--zip", type=Path, help=("入力データとして登録するzipファイルのパスを指定してください。"))

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="指定した場合、input_data_idがすでに存在していたら上書きします。指定しなければ、スキップします。" " ``--csv`` , `--json`` を指定したときのみ有効なオプションです。",
    )

    parser.add_argument(
        "--input_data_name_for_zip",
        type=str,
        help="入力データとして登録するzipファイルのinput_data_nameを指定してください。省略した場合、 ``--zip`` のパスになります。"
        " ``--zip`` を指定したときのみ有効なオプションです。",
    )

    parser.add_argument(
        "--allow_duplicated_input_data",
        action="store_true",
        help=(
            "``--csv`` , ``--json`` に渡した入力データの重複（input_data_name, input_data_path）を許可します。\n"
            "``--csv`` , ``--json` `を指定したときのみ有効なオプションです。"
        ),
    )

    parser.add_argument("--wait", action="store_true", help=("入力データの登録が完了するまで待ちます。" " ``--zip`` を指定したときのみ有効なオプションです。"))

    parser.add_argument(
        "--wait_options",
        type=str,
        help="入力データの登録が完了するまで待つ際のオプションをJSON形式で指定してください。 ``--wait`` を指定したときのみ有効なオプションです。"
        " ``file://`` を先頭に付けるとjsonファイルを指定できます。"
        'デフォルとは ``{"interval":60, "max_tries":360}`` です。'
        "``interval`` :完了したかを問い合わせる間隔[秒], "
        "``max_tires`` :完了したかの問い合わせを最大何回行うか。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        help="並列度。指定しない場合は、逐次的に処理します。" "``--csv`` , ``--json`` を指定したときのみ有効なオプションです。また、必ず ``--yes`` を指定してください。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "put"
    subcommand_help = "入力データを登録します。"
    description = "CSVに記載された入力データ情報やzipファイルを、入力データとして登録します。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
