import argparse
import logging
import urllib.parse
from pathlib import Path
from typing import Any

import annofabapi
import pandas
from annofabapi.models import InputData

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import get_columns_with_priority, print_csv, print_id_list, print_json
from annofabcli.input_data.utils import remove_unnecessary_keys_from_input_data

logger = logging.getLogger(__name__)


def print_input_data_list(
    input_data_list: list[dict[str, Any]],
    output_format: OutputFormat,
    output_file: Path | None,
) -> None:
    """
    入力データ一覧を指定されたフォーマットで出力する。

    Args:
        input_data_list: 入力データ一覧
        output_format: 出力フォーマット
        output_file: 出力先
    """
    input_data_prior_columns = [
        "project_id",
        "input_data_id",
        "input_data_name",
        "input_data_path",
        "url",
        "etag",
        "updated_datetime",
        "sign_required",
    ]

    if output_format == OutputFormat.CSV:
        if len(input_data_list) > 0:
            # pandas.DataFrameでなくpandas.json_normalizeを使う理由:
            # ネストしたオブジェクトを`system_metadata.input_duration`のような列名でアクセスできるようにするため
            df = pandas.json_normalize(input_data_list)

            # system_metadata.*列とmetadata.*列を検出して優先列リストに追加
            # 順序: input_data_prior_columns → system_metadata.* → metadata.*
            system_metadata_columns = sorted([col for col in df.columns if col.startswith("system_metadata.")])
            metadata_columns = sorted([col for col in df.columns if col.startswith("metadata.")])
            prior_columns_with_metadata = input_data_prior_columns + system_metadata_columns + metadata_columns
            columns = get_columns_with_priority(df, prior_columns=prior_columns_with_metadata)
            print_csv(df[columns], output=output_file)
        else:
            df = pandas.DataFrame(columns=input_data_prior_columns)
            print_csv(df, output=output_file)

    elif output_format == OutputFormat.PRETTY_JSON:
        print_json(input_data_list, is_pretty=True, output=output_file)

    elif output_format == OutputFormat.JSON:
        print_json(input_data_list, is_pretty=False, output=output_file)

    elif output_format == OutputFormat.INPUT_DATA_ID_LIST:
        input_data_id_list = [e["input_data_id"] for e in input_data_list]
        print_id_list(input_data_id_list, output=output_file)
    else:
        raise ValueError(f"{output_format}は対応していないフォーマットです。")


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
        input_data_id_list: list[str] | None = None,
        input_data_query: dict[str, Any] | None = None,
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

        output_format = OutputFormat(args.format)
        print_input_data_list(input_data_list, output_format=output_format, output_file=args.output)


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
            OutputFormat.CSV,
            OutputFormat.JSON,
            OutputFormat.PRETTY_JSON,
            OutputFormat.INPUT_DATA_ID_LIST,
        ],
        default=OutputFormat.CSV,
    )
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list"
    subcommand_help = "入力データ一覧を出力します。"
    description = "入力データ一覧を出力します。Annofabの制約上、10,000件までしか出力されません。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
