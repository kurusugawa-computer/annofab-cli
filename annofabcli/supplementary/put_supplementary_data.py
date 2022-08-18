import argparse
import json
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
from annofabapi.models import ProjectMemberRole, SupplementaryData
from dataclasses_json import DataClassJsonMixin
from more_itertools import first_true

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    prompt_yesnoall,
)
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import get_file_scheme_path

logger = logging.getLogger(__name__)


@dataclass
class CsvSupplementaryData(DataClassJsonMixin):
    """
    CSVに記載されている補助情報
    """

    input_data_id: str
    supplementary_data_number: int
    supplementary_data_name: str
    supplementary_data_path: str
    supplementary_data_id: Optional[str] = None
    supplementary_data_type: Optional[str] = None


@dataclass
class SupplementaryDataForPut:
    """
    putする補助情報
    """

    input_data_id: str
    supplementary_data_id: str
    supplementary_data_name: str
    supplementary_data_path: str
    supplementary_data_type: Optional[str]
    supplementary_data_number: int
    last_updated_datetime: Optional[str]


class SubPutSupplementaryData:
    """
    1個の補助情報を登録するためのクラス。multiprocessing.Pool対応。

    Args:
        service:
        facade:
        all_yes:
    """

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, all_yes: bool = False):
        self.service = service
        self.facade = facade
        self.all_yes = all_yes
        self.supplementary_data_cache: Dict[str, List[SupplementaryData]] = {}

    def put_supplementary_data(self, project_id: str, supplementary_data: SupplementaryDataForPut):

        file_path = get_file_scheme_path(supplementary_data.supplementary_data_path)
        if file_path is not None:
            request_body = {
                "supplementary_data_name": supplementary_data.supplementary_data_name,
                "supplementary_data_number": supplementary_data.supplementary_data_number,
                "last_updated_datetime": supplementary_data.last_updated_datetime,
            }
            # 省略時は put_supplementary_data_from_file に推定させたいので、Noneも入れない
            if supplementary_data.supplementary_data_type is not None:
                request_body.update({"supplementary_data_type": supplementary_data.supplementary_data_type})

            logger.debug(
                f"'{file_path}'を補助情報として登録します。supplementary_data_name={supplementary_data.supplementary_data_name}"
            )
            self.service.wrapper.put_supplementary_data_from_file(
                project_id,
                input_data_id=supplementary_data.input_data_id,
                supplementary_data_id=supplementary_data.supplementary_data_id,
                file_path=file_path,
                request_body=request_body,
            )

        else:
            supplementary_data_type = supplementary_data.supplementary_data_type
            if supplementary_data_type is None:
                supplementary_data_type = (
                    "text" if supplementary_data.supplementary_data_path.endswith(".txt") else "image"
                )

            request_body = {
                "supplementary_data_name": supplementary_data.supplementary_data_name,
                "supplementary_data_number": supplementary_data.supplementary_data_number,
                "supplementary_data_path": supplementary_data.supplementary_data_path,
                "supplementary_data_type": supplementary_data_type,
                "last_updated_datetime": supplementary_data.last_updated_datetime,
            }

            self.service.api.put_supplementary_data(
                project_id,
                supplementary_data.input_data_id,
                supplementary_data.supplementary_data_id,
                request_body=request_body,
            )

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

    def confirm_put_supplementary_data(
        self, csv_supplementary_data: CsvSupplementaryData, already_exists: bool = False
    ) -> bool:
        message_for_confirm = (
            f"supplementary_data_name='{csv_supplementary_data.supplementary_data_name}' の補助情報を登録しますか？"
        )
        if already_exists:
            message_for_confirm += f"supplementary_data_id={csv_supplementary_data.supplementary_data_id} を上書きします。"
        return self.confirm_processing(message_for_confirm)

    def get_supplementary_data_list_cached(self, project_id: str, input_data_id: str) -> List[SupplementaryData]:
        key = f"{project_id},{input_data_id}"
        if key not in self.supplementary_data_cache:
            supplementary_data_list, _ = self.service.api.get_supplementary_data_list(project_id, input_data_id)
            self.supplementary_data_cache[key] = supplementary_data_list if supplementary_data_list is not None else []
        return self.supplementary_data_cache[key]

    def get_supplementary_data_by_id(
        self, project_id: str, input_data_id: str, supplementary_data_id: str
    ) -> Optional[SupplementaryData]:
        cached_list = self.get_supplementary_data_list_cached(project_id, input_data_id)
        return first_true(cached_list, pred=lambda e: e["supplementary_data_id"] == supplementary_data_id)

    def get_supplementary_data_by_number(
        self, project_id: str, input_data_id: str, supplementary_data_number: int
    ) -> Optional[SupplementaryData]:
        cached_list = self.get_supplementary_data_list_cached(project_id, input_data_id)
        return first_true(cached_list, pred=lambda e: e["supplementary_data_number"] == supplementary_data_number)

    def put_supplementary_data_main(
        self, project_id: str, csv_supplementary_data: CsvSupplementaryData, overwrite: bool = False
    ) -> bool:
        last_updated_datetime = None
        input_data_id = csv_supplementary_data.input_data_id
        supplementary_data_id = csv_supplementary_data.supplementary_data_id
        supplementary_data_path = csv_supplementary_data.supplementary_data_path

        # input_data_idの存在確認
        if self.service.wrapper.get_input_data_or_none(project_id, input_data_id) is None:
            logger.warning(f"input_data_id='{input_data_id}'である入力データは存在しないため、補助情報の登録をスキップします。")
            return False

        if supplementary_data_id is not None:
            old_supplementary_data_key = f"supplementary_data_id={supplementary_data_id}"
            old_supplementary_data = self.get_supplementary_data_by_id(project_id, input_data_id, supplementary_data_id)
        else:
            supplementary_data_number = csv_supplementary_data.supplementary_data_number
            old_supplementary_data_key = (
                f"input_data_id={input_data_id}, supplementary_data_number={supplementary_data_number}"
            )
            old_supplementary_data = self.get_supplementary_data_by_number(
                project_id, input_data_id, supplementary_data_number
            )
            supplementary_data_id = (
                old_supplementary_data["supplementary_data_id"]
                if old_supplementary_data is not None
                else str(uuid.uuid4())
            )

        if old_supplementary_data is not None:
            if overwrite:
                logger.debug(f"{old_supplementary_data_key} はすでに存在します。")
                last_updated_datetime = old_supplementary_data["updated_datetime"]
            else:
                logger.debug(f"{old_supplementary_data_key} がすでに存在するのでスキップします。")
                return False

        file_path = get_file_scheme_path(supplementary_data_path)
        logger.debug(f"csv_supplementary_data={csv_supplementary_data}")
        if file_path is not None:
            if not Path(file_path).exists():
                logger.warning(f"{supplementary_data_path} は存在しません。")
                return False

        if not self.confirm_put_supplementary_data(
            csv_supplementary_data, already_exists=(last_updated_datetime is not None)
        ):
            return False

        # 補助情報を登録
        supplementary_data_for_put = SupplementaryDataForPut(
            input_data_id=csv_supplementary_data.input_data_id,
            supplementary_data_id=supplementary_data_id,
            supplementary_data_name=csv_supplementary_data.supplementary_data_name,
            supplementary_data_path=csv_supplementary_data.supplementary_data_path,
            supplementary_data_type=csv_supplementary_data.supplementary_data_type,
            supplementary_data_number=csv_supplementary_data.supplementary_data_number,
            last_updated_datetime=last_updated_datetime,
        )
        try:
            self.put_supplementary_data(project_id, supplementary_data_for_put)
            logger.debug(
                f"補助情報を登録しました。"
                f"input_data_id={supplementary_data_for_put.input_data_id},"
                f"supplementary_data_id={supplementary_data_for_put.supplementary_data_id}, "
                f"supplementary_data_name={supplementary_data_for_put.supplementary_data_name}"
            )
            return True

        except requests.exceptions.HTTPError as e:
            logger.warning(e)
            logger.warning(
                f"補助情報の登録に失敗しました。"
                f"input_data_id={supplementary_data_for_put.input_data_id},"
                f"supplementary_data_id={supplementary_data_for_put.supplementary_data_id}, "
                f"supplementary_data_name={supplementary_data_for_put.supplementary_data_name}"
            )
            return False


class PutSupplementaryData(AbstractCommandLineInterface):
    """
    補助情報をCSVで登録する。
    """

    def put_supplementary_data_list(
        self,
        project_id: str,
        supplementary_data_list: List[CsvSupplementaryData],
        overwrite: bool = False,
        parallelism: Optional[int] = None,
    ) -> None:
        """
        補助情報を一括で登録する。

        Args:
            project_id: 補助情報の登録先プロジェクトのプロジェクトID
            supplementary_data_list: 補助情報List
            overwrite: Trueならば、supplementary_data_id（省略時はsupplementary_data_number）がすでに存在していたら上書きします。Falseならばスキップします。
            parallelism: 並列度

        """

        project_title = self.facade.get_project_title(project_id)
        logger.info(f"{project_title} に、{len(supplementary_data_list)} 件の補助情報を登録します。")

        count_put_supplementary_data = 0

        obj = SubPutSupplementaryData(service=self.service, facade=self.facade, all_yes=self.all_yes)
        if parallelism is not None:
            partial_func = partial(obj.put_supplementary_data_main, project_id, overwrite=overwrite)
            with Pool(parallelism) as pool:
                result_bool_list = pool.map(partial_func, supplementary_data_list)
                count_put_supplementary_data = len([e for e in result_bool_list if e])

        else:
            for csv_supplementary_data in supplementary_data_list:
                result = obj.put_supplementary_data_main(
                    project_id, csv_supplementary_data=csv_supplementary_data, overwrite=overwrite
                )
                if result:
                    count_put_supplementary_data += 1

        logger.info(f"{project_title} に、{count_put_supplementary_data} / {len(supplementary_data_list)} 件の補助情報を登録しました。")

    @staticmethod
    def get_supplementary_data_list_from_dict(
        supplementary_data_dict_list: List[Dict[str, Any]]
    ) -> List[CsvSupplementaryData]:
        return CsvSupplementaryData.schema().load(supplementary_data_dict_list, many=True, unknown="exclude")

    @staticmethod
    def get_supplementary_data_list_from_csv(csv_path: Path) -> List[CsvSupplementaryData]:
        def create_supplementary_data(e):
            supplementary_data_id = e.supplementary_data_id if not pandas.isna(e.supplementary_data_id) else None
            supplementary_data_type = e.supplementary_data_type if not pandas.isna(e.supplementary_data_type) else None
            return CsvSupplementaryData(
                input_data_id=e.input_data_id,
                supplementary_data_number=e.supplementary_data_number,
                supplementary_data_name=e.supplementary_data_name,
                supplementary_data_path=e.supplementary_data_path,
                supplementary_data_id=supplementary_data_id,
                supplementary_data_type=supplementary_data_type,
            )

        df = pandas.read_csv(
            str(csv_path),
            sep=",",
            header=None,
            names=(
                "input_data_id",
                "supplementary_data_number",
                "supplementary_data_name",
                "supplementary_data_path",
                "supplementary_data_id",
                "supplementary_data_type",
            ),
            # IDは必ず文字列として読み込むようにする
            dtype={"input_data_id": str, "supplementary_data_id": str, "supplementary_data_name": str},
        )
        supplementary_data_list = [create_supplementary_data(e) for e in df.itertuples()]
        return supplementary_data_list

    COMMON_MESSAGE = "annofabcli supplementary_data put: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.csv is not None:
            if not Path(args.csv).exists():
                print(f"{self.COMMON_MESSAGE} argument --csv: ファイルパスが存在しません。 '{args.csv}'", file=sys.stderr)
                return False

        if args.parallelism is not None and not args.yes:
            print(
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず ``--yes`` を指定してください。",
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
            supplementary_data_list = self.get_supplementary_data_list_from_csv(Path(args.csv))
        elif args.json is not None:
            supplementary_data_list = self.get_supplementary_data_list_from_dict(get_json_from_args(args.json))
        else:
            print(
                f"{self.COMMON_MESSAGE} argument --parallelism: '--csv'または'--json'のいずれかを指定してください。",
                file=sys.stderr,
            )
            return

        self.put_supplementary_data_list(
            project_id,
            supplementary_data_list=supplementary_data_list,
            overwrite=args.overwrite,
            parallelism=args.parallelism,
        )


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PutSupplementaryData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    file_group = parser.add_mutually_exclusive_group(required=True)
    file_group.add_argument(
        "--csv",
        type=str,
        help=(
            "補助情報が記載されたCVファイルのパスを指定してください。CSVのフォーマットは、以下の通りです。\n"
            "\n"
            " * ヘッダ行なし, カンマ区切り\n"
            " * 1列目: input_data_id (required)\n"
            " * 2列目: supplementary_data_number (required)\n"
            " * 3列目: supplementary_data_name (required)\n"
            " * 4列目: supplementary_data_path (required)\n"
            " * 5列目: supplementary_data_id\n"
            " * 6列目: supplementary_data_type\n"
            "\n"
            "各項目の詳細は https://annofab-cli.readthedocs.io/ja/latest/command_reference/supplementary/put.html を参照してください。"
        ),
    )

    JSON_SAMPLE = [
        {
            "input_data_id": "input1",
            "supplementary_data_number": 1,
            "supplementary_data_name": "foo",
            "supplementary_data_path": "file://foo.jpg",
        }
    ]
    file_group.add_argument(
        "--json",
        type=str,
        help=(
            "登録対象の補助情報データをJSON形式で指定してください。\n"
            "\n"
            f"(ex) ``{json.dumps(JSON_SAMPLE)}`` \n"
            "\n"
            "JSONの各キーは ``--csv`` に渡すCSVの各列に対応しています。"
            " ``file://`` を先頭に付けるとjsonファイルを指定できます。"
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="指定した場合、supplementary_data_id（省略時はsupplementary_data_number）がすでに存在していたら上書きします。指定しなければ、スキップします。",
    )

    parser.add_argument("--parallelism", type=int, help="並列度。指定しない場合は、逐次的に処理します。必ず ``--yes`` を指定してください。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "put"
    subcommand_help = "補助情報を登録します。"
    description = "補助情報を登録します。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
