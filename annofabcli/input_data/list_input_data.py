import argparse
import logging
import urllib.parse
from typing import Any, Optional

import annofabapi
import pandas
from annofabapi.models import InputData

import annofabcli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login, print_according_to_format, print_csv
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.input_data.utils import remove_unnecessary_keys_from_input_data

logger = logging.getLogger(__name__)


class AddingDetailsToInputData:
    """
    入力データに詳細情報を追加するためのクラス
    """

    def __init__(self, service: annofabapi.Resource, project_id: str) -> None:
        self.service = service
        self.project_id = project_id

    def add_parent_task_id_list_to_input_data_list(self, input_data_list: list[InputData], *, average_input_data_id_length: int = 36) -> list[InputData]:
        """
        `input_data_list`に"どのタスクに使われているか"という情報を付与します。

        Args:
            input_data_list: 入力データList(In/Out)
            average_input_data_id_length: 入力データIDの平均長さ。この値を元にして、`getTasks` APIの実行回数を決めます。
                `getTasks` APIはクエリパラメータに`input_data_ids`で複数の入力データIDを指定できます。
                クエリパラメータのサイズには上限があるため、たとえば10,000個の入力データIDを指定することはできません。
                したがって、入力データIDの平均サイズから、`getTasks` APIの実行回数を決めます。

        Returns:

        """
        if len(input_data_list) == 0:
            return input_data_list

        # AWS CloudFrontのURLの上限が8,192byte
        # https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cloudfront-limits.html
        MAX_URL_QUERY_LENGTH = 8000  # input_dat_ids部分のURLクエリの最大値  # noqa: N806
        average_input_data_id_length = average_input_data_id_length + 1  # カンマの分だけ長さを増やす
        chunk_size = MAX_URL_QUERY_LENGTH // average_input_data_id_length
        initial_index = 0
        while True:
            sub_input_data_list = input_data_list[initial_index : initial_index + chunk_size]
            sub_input_data_id_list = [e["input_data_id"] for e in sub_input_data_list]
            str_input_data_id_list = ",".join(sub_input_data_id_list)
            encoded_input_data_id_list = urllib.parse.quote(str_input_data_id_list)
            if len(encoded_input_data_id_list) > MAX_URL_QUERY_LENGTH:
                differential_length = len(encoded_input_data_id_list) - MAX_URL_QUERY_LENGTH
                decreasing_size = (differential_length // average_input_data_id_length) + 1
                logger.debug(f"chunk_sizeを {chunk_size} から、{chunk_size - decreasing_size} に減らした. len(encoded_input_data_id_list) = {len(encoded_input_data_id_list)}")
                chunk_size = chunk_size - decreasing_size
                if chunk_size <= 0:
                    chunk_size = 1

                continue

            logger.debug(f"入力データの{initial_index}件目から{initial_index + chunk_size - 1}件目を参照しているタスクのtask_idを取得します。")
            task_list = self.service.wrapper.get_all_tasks(self.project_id, query_params={"input_data_ids": str_input_data_id_list})

            for input_data in sub_input_data_list:
                task_id_list = [t["task_id"] for t in task_list if input_data["input_data_id"] in t["input_data_id_list"]]
                input_data["parent_task_id_list"] = task_id_list

            initial_index = initial_index + chunk_size
            if initial_index >= len(input_data_list):
                break

        return input_data_list

    def add_supplementary_data_count_to_input_data_list(self, input_data_list: list[InputData]) -> list[InputData]:
        """
        `input_data_list`に補助情報の個数（`supplementary_data_count`）を付与します。

        Args:
            input_data_list: 入力データList(In/Out)

        Returns:

        """
        if len(input_data_list) == 0:
            return input_data_list

        logger.info(f"入力データ {len(input_data_list)} 件に紐づく補助情報の個数を取得します。")
        for index, input_data in enumerate(input_data_list):
            supplementary_data_list, _ = self.service.api.get_supplementary_data_list(self.project_id, input_data["input_data_id"])
            input_data["supplementary_data_count"] = len(supplementary_data_list)
            if (index + 1) % 100 == 0:
                logger.debug(f"{index + 1} 件の入力データに紐づく補助情報の個数を取得しました。")

        return input_data_list


class ListInputDataMain:
    def __init__(self, service: annofabapi.Resource, project_id: str) -> None:
        self.service = service
        self.project_id = project_id

    def get_input_data_from_input_data_id(self, input_data_id_list: list[str]) -> list[InputData]:
        input_data_list = []
        logger.debug(f"{len(input_data_id_list)}件の入力データを取得します。")
        for index, input_data_id in enumerate(input_data_id_list):
            if (index + 1) % 100 == 0:
                logger.debug(f"{index + 1} 件目の入力データを取得します。")

            input_data = self.service.wrapper.get_input_data_or_none(self.project_id, input_data_id)
            if input_data is not None:
                input_data_list.append(input_data)
            else:
                logger.warning(f"入力データ '{input_data_id}' は見つかりませんでした。")

        return input_data_list

    def get_input_data_list(
        self,
        *,
        input_data_id_list: Optional[list[str]] = None,
        input_data_query: Optional[dict[str, Any]] = None,
        contain_parent_task_id_list: bool = False,
        contain_supplementary_data_count: bool = False,
    ) -> list[InputData]:
        """
        入力データ一覧を取得する。
        """
        if input_data_id_list is not None:
            input_data_list = self.get_input_data_from_input_data_id(input_data_id_list)
        else:
            logger.debug(f"input_data_query: {input_data_query}")
            input_data_list = self.service.wrapper.get_all_input_data_list(self.project_id, query_params=input_data_query)

        adding_obj = AddingDetailsToInputData(self.service, self.project_id)
        if contain_parent_task_id_list:
            adding_obj.add_parent_task_id_list_to_input_data_list(input_data_list)

        if contain_supplementary_data_count:
            adding_obj.add_supplementary_data_count_to_input_data_list(input_data_list)

        # 入力データの不要なキーを削除する
        for input_data in input_data_list:
            remove_unnecessary_keys_from_input_data(input_data)
        return input_data_list


class ListInputData(CommandLine):
    """
    入力データの一覧を表示する
    """

    def main(self) -> None:
        args = self.args
        input_data_id_list = annofabcli.common.cli.get_list_from_args(args.input_data_id) if args.input_data_id is not None else None

        input_data_query = annofabcli.common.cli.get_json_from_args(args.input_data_query)

        main_obj = ListInputDataMain(self.service, project_id=args.project_id)

        input_data_list = main_obj.get_input_data_list(
            input_data_id_list=input_data_id_list,
            input_data_query=input_data_query,
            contain_parent_task_id_list=args.with_parent_task_id_list,
            contain_supplementary_data_count=args.with_supplementary_data_count,
        )

        logger.info(f"入力データ一覧の件数: {len(input_data_list)}")
        if len(input_data_list) == 10_000:
            logger.warning("入力データ一覧は10,000件で打ち切られている可能性があります。")

        output_format = FormatArgument(args.format)
        if len(input_data_list) > 0:
            if output_format == FormatArgument.CSV:
                # pandas.DataFrameでなくpandas.json_normalizeを使う理由:
                # ネストしたオブジェクトを`system_metadata.input_duration`のような列名でアクセスできるようにするため
                df = pandas.json_normalize(input_data_list)
                print_csv(df, output=args.output)
            else:
                print_according_to_format(input_data_list, format=output_format, output=args.output)
        else:
            logger.info("入力データの件数が0件のため、出力しません。")


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListInputData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    query_group = parser.add_mutually_exclusive_group()

    query_group.add_argument(
        "-iq",
        "--input_data_query",
        type=str,
        help="入力データの検索クエリをJSON形式で指定します。"
        " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        "クエリのフォーマットは、`getInputDataList <https://annofab.com/docs/api/#operation/getInputDataList>`_ APIのクエリパラメータと同じです。"
        "ただし ``page`` , ``limit`` キーは指定できません。",
    )

    query_group.add_argument(
        "-i",
        "--input_data_id",
        type=str,
        nargs="+",
        help="対象のinput_data_idを指定します。 ``--input_data_query`` 引数とは同時に指定できません。 ``file://`` を先頭に付けると、input_data_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument("--with_parent_task_id_list", action="store_true", help="入力データを参照しているタスクのIDのlist( ``parent_task_id_list`` )も出力します。")

    parser.add_argument("--with_supplementary_data_count", action="store_true", help="入力データに紐づく補助情報の個数( ``supplementary_data_count`` )も出力します。")

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

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list"
    subcommand_help = "入力データ一覧を出力します。"
    description = "入力データ一覧を出力します。Annofabの制約上、10,000件までしか出力されません。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
