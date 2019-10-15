import argparse
import copy
import datetime
import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Union  # pylint: disable=unused-import

import annofabapi
from annofabapi.models import InputData, Task, TaskId
from annofabapi.utils import to_iso8601_extension
from dataclasses_json import dataclass_json

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)

DatetimeRange = Tuple[Optional[datetime.datetime], Optional[datetime.datetime]]


@dataclass_json
@dataclass(frozen=True)
class InputDataBatchQuery:
    """
    入力データをバッチ単位（段階的に）に取得する。
    """
    first: str
    last: str
    days: int


def str_to_datetime(d: str) -> datetime.datetime:
    """
    文字列 `YYYY-MM-DDD` をdatetime.datetimeに変換する。
    """
    return datetime.datetime.strptime(d, '%Y-%m-%d')


def create_datetime_range_list(first_datetime: datetime.datetime, last_datetime: datetime.datetime,
                               days: int) -> List[DatetimeRange]:
    datetime_list: List[DatetimeRange] = []
    datetime_list.append((None, first_datetime))

    from_datetime = first_datetime
    while True:
        to_datetime = from_datetime + datetime.timedelta(days=days)
        datetime_list.append((from_datetime, to_datetime))
        if to_datetime >= last_datetime:
            break

        from_datetime = to_datetime

    datetime_list.append((to_datetime, None))
    return datetime_list


class ListInputData(AbstractCommandLineInterface):
    """
    入力データの一覧を表示する
    """

    #: 入力データIDの平均長さ
    average_input_data_id_length: int = 36

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)
        self.average_input_data_id_length = args.averate_input_data_id_length

    @staticmethod
    def _find_task_id_list(task_list: List[Task], input_data_id: str) -> List[TaskId]:
        """
        タスク一覧から、該当のinput_data_idを持つtask_id_listを返す。
        """
        task_id_list = []
        for task in task_list:
            if input_data_id in task['input_data_id_list']:
                task_id_list.append(task['task_id'])
        return task_id_list

    def get_input_data(self, project_id: str, input_data_query: Optional[Dict[str, Any]] = None,
                       add_details: bool = False) -> List[InputData]:
        """
        入力データ一覧を取得する。
        """

        logger.debug(f"input_data_query: {input_data_query}")
        input_data_list = self.service.wrapper.get_all_input_data_list(project_id, query_params=input_data_query)
        # 詳細な情報を追加する
        if add_details and len(input_data_list) > 0:
            logger.debug(f"入力データ一覧の件数: {len(input_data_list)}")

            # AWS CloudFrontのURLの上限が8,192byte
            # https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cloudfront-limits.html
            MAX_URL_QUERY_LENGTH = 8000  # input_dat_ids部分のURLクエリの最大値
            average_input_data_id_length = self.average_input_data_id_length + 1  # カンマの分だけ長さを増やす
            chunk_size = MAX_URL_QUERY_LENGTH // average_input_data_id_length
            initial_index = 0
            while True:
                sub_input_data_list = input_data_list[initial_index:initial_index + chunk_size]
                sub_input_data_id_list = [e['input_data_id'] for e in sub_input_data_list]
                str_input_data_id_list = ",".join(sub_input_data_id_list)
                encoded_input_data_id_list = urllib.parse.quote(str_input_data_id_list)
                if len(encoded_input_data_id_list) > MAX_URL_QUERY_LENGTH:
                    differential_length = (len(encoded_input_data_id_list) - MAX_URL_QUERY_LENGTH)
                    decreasing_size = (differential_length // average_input_data_id_length) + 1
                    logger.debug(f"chunk_sizeを {chunk_size} から、{chunk_size - decreasing_size} に減らした. "
                                 f"len(encoded_input_data_id_list) = {len(encoded_input_data_id_list)}")
                    chunk_size = chunk_size - decreasing_size
                    if chunk_size <= 0:
                        chunk_size = 1

                    continue

                logger.debug(f"input_data_list[{initial_index}:{initial_index+chunk_size}] を使用しているタスクを取得する。")
                task_list = self.service.wrapper.get_all_tasks(project_id,
                                                               query_params={'input_data_ids': str_input_data_id_list})

                for input_data in sub_input_data_list:
                    # input_data_idで絞り込んでいるが、大文字小文字を区別しない。
                    # したがって、確認のため `_find_task_id_list`を実行する
                    task_id_list = self._find_task_id_list(task_list, input_data['input_data_id'])
                    self.visualize.add_properties_to_input_data(input_data, task_id_list)

                initial_index = initial_index + chunk_size
                if initial_index >= len(input_data_list):
                    break

        return input_data_list

    def get_input_data_with_batch(self, project_id: str, batch_query: InputDataBatchQuery,
                                  input_data_query: Optional[Dict[str, Any]] = None,
                                  add_details: bool = False) -> List[InputData]:
        """
        バッチ単位で入力データを取得する。

        Args:
            project_id:
            input_data_query:
            add_details:
            batch_query:

        Returns:

        """
        first_datetime = str_to_datetime(batch_query.first)
        last_datetime = str_to_datetime(batch_query.last)

        all_input_data_list = []

        datetime_range_list = create_datetime_range_list(first_datetime, last_datetime, batch_query.days)
        for from_datetime, to_datetime in datetime_range_list:
            idq = copy.deepcopy(input_data_query) if input_data_query is not None else {}

            if from_datetime is not None:
                idq["from"] = to_iso8601_extension(from_datetime)
            if to_datetime is not None:
                idq["to"] = to_iso8601_extension(to_datetime)

            logger.debug(f"入力データを取得します。query={idq}")
            input_data_list = self.get_input_data(project_id, idq, add_details)
            logger.debug(f"入力データを {len(input_data_list)} 件取得しました。")
            if len(input_data_list) == 10000:
                logger.warning("入力データ一覧は10,000件で打ち切られている可能性があります。")

            all_input_data_list.extend(input_data_list)

        return all_input_data_list

    def print_input_data(self, project_id: str, input_data_query: Optional[Dict[str, Any]] = None,
                         add_details: bool = False, batch_query: Optional[InputDataBatchQuery] = None):
        """
        入力データ一覧を出力する

        Args:
            project_id: 対象のproject_id
            input_data_query: 入力データの検索クエリ
            add_details: 詳細情報を表示する

        """

        super().validate_project(project_id, project_member_roles=None)

        if batch_query is None:
            input_data_list = self.get_input_data(project_id, input_data_query=input_data_query,
                                                  add_details=add_details)
            logger.info(f"入力データ一覧の件数: {len(input_data_list)}")
            if len(input_data_list) == 10000:
                logger.warning("入力データ一覧は10,000件で打ち切られている可能性があります。")

        else:
            input_data_list = self.get_input_data_with_batch(project_id, input_data_query=input_data_query,
                                                             add_details=add_details, batch_query=batch_query)
            logger.info(f"入力データ一覧の件数: {len(input_data_list)}")
            total_count = self.service.api.get_input_data_list(project_id,
                                                               query_params=input_data_query)[0]["total_count"]
            if len(input_data_list) != total_count:
                logger.warning(f"実際に取得した件数:{len(input_data_list)}が、取得可能な件数:{total_count} と異なっていました。")

        self.print_according_to_format(input_data_list)

    def main(self):
        args = self.args
        input_data_query = annofabcli.common.cli.get_json_from_args(args.input_data_query)
        dict_batch_query = annofabcli.common.cli.get_json_from_args(args.batch)
        batch_query = InputDataBatchQuery.from_dict(dict_batch_query) if dict_batch_query is not None else None
        self.print_input_data(args.project_id, input_data_query=input_data_query, add_details=args.add_details,
                              batch_query=batch_query)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    ListInputData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    # タスク検索クエリ
    parser.add_argument(
        '-iq', '--input_data_query', type=str, help='入力データの検索クエリをJSON形式で指定します。'
        '`file://`を先頭に付けると、JSON形式のファイルを指定できます。'
        'クエリのフォーマットは、[getInputDataList API](https://annofab.com/docs/api/#operation/getInputDataList)のクエリパラメータと同じです。'
        'ただし `page`, `limit`キーは指定できません。')

    parser.add_argument(
        '--batch', type=str, help='段階的に入力データを取得するための情報をJSON形式で指定します。 '
        '(ex) `{"first":"2019-01-01", "last":"2019-01-31", "days":7}` '
        'このオプションを駆使すれば、10,000件以上のデータを取得できます。')

    parser.add_argument('--add_details', action='store_true', help='入力データの詳細情報を表示します（`parent_task_id_list`）')

    parser.add_argument(
        '--averate_input_data_id_length', type=int, default=36, help=('入力データIDの平均長さを指定します。`add_details`がTrueのときのみ有効です。'
                                                                      'デフォルトはUUIDv4の長さです。'
                                                                      'この値を元にして、タスク一括取得APIの実行回数を決めます。'))

    argument_parser.add_format(
        choices=[
            FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON, FormatArgument.INPUT_DATA_ID_LIST
        ], default=FormatArgument.CSV)
    argument_parser.add_output()
    argument_parser.add_csv_format()

    argument_parser.add_query()
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list"
    subcommand_help = "入力データ一覧を出力します。"
    description = ("入力データ一覧を出力します。AnnoFabの制約上、10,000件までしか出力されません。")

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
