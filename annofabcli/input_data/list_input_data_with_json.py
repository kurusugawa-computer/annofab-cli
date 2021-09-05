import argparse
import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import annofabapi
from annofabapi.dataclass.input import InputData
from annofabapi.models import ProjectMemberRole

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import InputDataQuery, match_input_data_with_query

logger = logging.getLogger(__name__)

DatetimeRange = Tuple[Optional[datetime.datetime], Optional[datetime.datetime]]


class ListInputDataWithJsonMain:
    def __init__(self, service: annofabapi.Resource):
        self.service = service
        self.facade = AnnofabApiFacade(service)

    @staticmethod
    def filter_input_data_list(
        input_data: Dict[str, Any],
        input_data_id_set: Optional[Set[str]] = None,
        input_data_query: Optional[InputDataQuery] = None,
    ) -> bool:
        result = True

        dc_input_data = InputData.from_dict(input_data)
        result = result and match_input_data_with_query(dc_input_data, input_data_query)
        if input_data_id_set is not None:
            result = result and (dc_input_data.input_data_id in input_data_id_set)
        return result

    def get_input_data_list(
        self,
        project_id: str,
        input_data_json: Optional[Path],
        input_data_id_list: Optional[List[str]] = None,
        input_data_query: Optional[InputDataQuery] = None,
        is_latest: bool = False,
        wait_options: Optional[WaitOptions] = None,
    ) -> List[Dict[str, Any]]:
        if input_data_json is None:
            downloading_obj = DownloadingFile(self.service)
            cache_dir = annofabcli.utils.get_cache_dir()
            json_path = cache_dir / f"{project_id}-input_data.json"

            downloading_obj.download_input_data_json(
                project_id, str(json_path), is_latest=is_latest, wait_options=wait_options
            )
        else:
            json_path = input_data_json

        logger.debug(f"{json_path} を読み込み中")
        with json_path.open() as f:
            input_data_list = json.load(f)

        logger.debug(f"入力データを絞り込み中")
        input_data_id_set = set(input_data_id_list) if input_data_id_list is not None else None
        filtered_input_data_list = [
            e
            for e in input_data_list
            if self.filter_input_data_list(e, input_data_query=input_data_query, input_data_id_set=input_data_id_set)
        ]
        return filtered_input_data_list


class ListInputDataWithJson(AbstractCommandLineInterface):
    def main(self):
        args = self.args

        input_data_id_list = (
            annofabcli.common.cli.get_list_from_args(args.input_data_id) if args.input_data_id is not None else None
        )
        input_data_query = (
            InputDataQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.input_data_query))
            if args.input_data_query is not None
            else None
        )
        wait_options = (
            WaitOptions.from_dict(annofabcli.common.cli.get_json_from_args(args.wait_options))
            if args.wait_options is not None
            else None
        )

        project_id = args.project_id
        super().validate_project(
            project_id, project_member_roles=[ProjectMemberRole.TRAINING_DATA_USER, ProjectMemberRole.OWNER]
        )

        main_obj = ListInputDataWithJsonMain(self.service)
        input_data_list = main_obj.get_input_data_list(
            project_id=project_id,
            input_data_json=args.input_data_json,
            input_data_id_list=input_data_id_list,
            input_data_query=input_data_query,
            is_latest=args.latest,
            wait_options=wait_options,
        )

        logger.debug(f"入力データ一覧の件数: {len(input_data_list)}")

        if len(input_data_list) > 0:
            self.print_according_to_format(input_data_list)
        else:
            logger.info(f"入力データ一覧の件数が0件のため、出力しません。")


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListInputDataWithJson(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "-iq",
        "--input_data_query",
        type=str,
        help="入力データの検索クエリをJSON形式で指定します。"
        " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        "指定できるキーは、``input_data_id`` , ``input_data_name`` , ``input_data_path`` です。",
    )

    parser.add_argument(
        "-i",
        "--input_data_id",
        type=str,
        nargs="+",
        help="対象のinput_data_idを指定します。" " ``file://`` を先頭に付けると、input_data_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "--input_data_json",
        type=Path,
        help="入力データ情報が記載されたJSONファイルのパスを指定すると、JSONに記載された情報を元に入力データ一覧を出力します。"
        "指定しない場合、全件ファイルをダウンロードします。"
        "JSONファイルは ``$ annofabcli project download input_data`` コマンドで取得できます。",
    )

    parser.add_argument(
        "--latest", action="store_true", help="最新の入力データ一覧ファイルを参照します。このオプションを指定すると、入力データ一覧ファイルを更新するのに約5分以上待ちます。"
    )

    parser.add_argument(
        "--wait_options",
        type=str,
        help="入力データ一覧ファイルの更新が完了するまで待つ際のオプションを、JSON形式で指定してください。"
        " ``file://`` を先頭に付けるとjsonファイルを指定できます。"
        'デフォルトは ``{"interval":60, "max_tries":360}`` です。'
        " ``interval`` :完了したかを問い合わせる間隔[秒], "
        " ``max_tires`` :完了したかの問い合わせを最大何回行うか。",
    )

    argument_parser.add_format(
        choices=[
            FormatArgument.CSV,
            FormatArgument.JSON,
            FormatArgument.PRETTY_JSON,
            FormatArgument.INPUT_DATA_ID_LIST,
        ],
        default=FormatArgument.CSV,
    )
    argument_parser.add_output()
    argument_parser.add_csv_format()

    argument_parser.add_query()
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "list_with_json"
    subcommand_help = "入力データ全件ファイルから一覧を出力します。"
    description = "入力データ全件ファイルから一覧を出力します。"
    epilog = "アノテーションユーザまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
