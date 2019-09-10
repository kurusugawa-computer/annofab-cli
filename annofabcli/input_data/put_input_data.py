import argparse
import logging
import uuid
from dataclasses import dataclass
from distutils.util import strtobool  # pylint: disable=import-error,no-name-in-module
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union  # pylint: disable=unused-import

import pandas
import requests
from annofabapi.models import ProjectMemberRole
from dataclasses_json import dataclass_json

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


@dataclass_json
@dataclass
class CsvInputData:
    """
    CSVに記載されている入力データ
    """
    input_data_name: str
    input_data_path: str
    input_data_id: str
    sign_required: Optional[bool]


class PutInputData(AbstractCommandLineInterface):
    """
    入力データをCSVで登録する。
    """
    def put_input_data(self, project_id: str, csv_input_data: CsvInputData,
                       last_updated_datetime: Optional[str] = None):
        request_body = {
            'input_data_name': csv_input_data.input_data_name,
            'input_data_path': csv_input_data.input_data_path,
            'sign_required': csv_input_data.sign_required,
        }
        if last_updated_datetime is not None:
            request_body.update({'last_updated_datetime': last_updated_datetime})

        self.service.api.put_input_data(project_id, csv_input_data.input_data_id, request_body=request_body)

    def confirm_put_input_data(self, csv_input_data: CsvInputData, alread_exists: bool = False) -> bool:

        message_for_confirm = (f"input_data_name='{csv_input_data.input_data_name}' の入力データを登録しますか？")
        if alread_exists:
            message_for_confirm += f"input_data_id={csv_input_data.input_data_id} を上書きします。"
        return self.confirm_processing(message_for_confirm)

    @annofabcli.utils.allow_404_error
    def get_input_data(self, project_id: str, input_data_id: str) -> Dict[str, Any]:
        input_data, _ = self.service.api.get_input_data(project_id, input_data_id)
        return input_data

    def put_input_data_list(self, project_id: str, input_data_list: List[CsvInputData], overwrite: bool = False):
        """
        入力データを一括で登録する。

        Args:
            project_id: 入力データの登録先プロジェクトのプロジェクトID
            input_data_list: 入力データList
            overwrite: Trueならば、input_data_idがすでに存在していたら上書きします。Falseならばスキップします。

        """

        super().validate_project(project_id, [ProjectMemberRole.OWNER])
        project_title = self.facade.get_project_title(project_id)
        logger.info(f"{project_title} に、{len(input_data_list)} 件の入力データを登録します。")

        count_put_input_data = 0

        for csv_input_data in input_data_list:

            last_updated_datetime = None
            input_data_id = csv_input_data.input_data_id
            input_data = self.get_input_data(project_id, input_data_id)
            if input_data is not None:
                if overwrite:
                    logger.debug(f"input_data_id={input_data_id} はすでに存在します。")
                    last_updated_datetime = input_data['updated_datetime']
                else:
                    logger.debug(f"input_data_id={input_data_id} がすでに存在するのでスキップします。")
                    continue

            if not self.confirm_put_input_data(csv_input_data, alread_exists=(last_updated_datetime is not None)):
                continue

            # 入力データを登録
            try:
                self.put_input_data(project_id, csv_input_data, last_updated_datetime)
                logger.debug(f"入力データを登録しました。"
                             f"input_data_id={csv_input_data.input_data_id}, "
                             f"input_data_name={csv_input_data.input_data_name}")
                count_put_input_data += 1

            except requests.exceptions.HTTPError as e:
                logger.warning(e)
                logger.warning(f"入力データの登録に失敗しました。"
                               f"input_data_id={csv_input_data.input_data_id}, "
                               f"input_data_name={csv_input_data.input_data_name}")

        logger.info(f"{project_title} に、{count_put_input_data} / {len(input_data_list)} 件の入力データを登録しました。")

    @staticmethod
    def get_input_data_list_from_csv(csv_path: Path) -> List[CsvInputData]:
        def create_input_data(e):
            input_data_id = e.input_data_id if not pandas.isna(e.input_data_id) else str(uuid.uuid4())
            sign_required = strtobool(str(e.sign_required)) if not pandas.isna(e.sign_required) else None
            return CsvInputData(input_data_name=e.input_data_name, input_data_path=e.input_data_path,
                                input_data_id=input_data_id, sign_required=sign_required)

        df = pandas.read_csv(str(csv_path), sep=',', header=None,
                             names=('input_data_name', 'input_data_path', 'input_data_id', 'sign_required'))
        input_data_list = [create_input_data(e) for e in df.itertuples()]
        return input_data_list

    def main(self):
        args = self.args
        input_data_list = self.get_input_data_list_from_csv(Path(args.csv))
        self.put_input_data_list(args.project_id, input_data_list=input_data_list, overwrite=args.overwrite)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    PutInputData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        '--csv', type=str, required=True,
        help=('入力データが記載されたCVファイルのパスを指定してください。'
              'CSVのフォーマットは、「1列目:input_data_name(required), 2列目:input_data_path(required), 3列目:input_data_id, '
              '4列目:sign_required(bool), ヘッダ行なし, カンマ区切り」です。'
              'input_data_idが空の場合はUUIDv4になります。'
              '各項目の詳細は `putInputData` API を参照してください。'))

    parser.add_argument('--overwrite', action='store_true',
                        help='指定した場合、input_data_idがすでに存在していたら上書きします。指定しなければ、スキップします。')

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "put"
    subcommand_help = "CSVに記載された入力データを登録します。"
    description = ("CSVに記載された入力データを登録します。")
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
