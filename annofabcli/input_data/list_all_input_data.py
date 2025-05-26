from __future__ import annotations

import argparse
import datetime
import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Optional

import annofabapi
import pandas
from annofabapi.dataclass.input import InputData
from annofabapi.models import ProjectMemberRole

import annofabcli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login, print_according_to_format, print_csv
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade, InputDataQuery, match_input_data_with_query
from annofabcli.input_data.list_input_data import AddingDetailsToInputData
from annofabcli.input_data.utils import remove_unnecessary_keys_from_input_data

logger = logging.getLogger(__name__)

DatetimeRange = tuple[Optional[datetime.datetime], Optional[datetime.datetime]]


class ListInputDataWithJsonMain:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service

    @staticmethod
    def filter_input_data_list(
        input_data: dict[str, Any],
        input_data_id_set: Optional[set[str]] = None,
        input_data_query: Optional[InputDataQuery] = None,
    ) -> bool:
        result = True

        dc_input_data = InputData.from_dict(input_data)
        result = result and match_input_data_with_query(dc_input_data, input_data_query)
        if input_data_id_set is not None:
            result = result and (dc_input_data.input_data_id in input_data_id_set)
        return result

    @staticmethod
    def remove_unnecessary_keys_from_input_data2(input_data_list: list[dict[str, Any]]) -> None:
        """
        入力データから不要なキーを取り除きます。

        Args:
            input_data_list: (IN/OUT) 入力データのlist
        """
        unnecessary_keys = [
            "url",  # システム内部用のプロパティ
            "original_input_data_path",  # システム内部用のプロパティ
            "etag",  # annofab-cliで見ることはない
        ]
        for input_data in input_data_list:
            for key in unnecessary_keys:
                input_data.pop(key, None)

    def get_input_data_list(
        self,
        project_id: str,
        input_data_json: Optional[Path],
        *,
        input_data_id_list: Optional[list[str]] = None,
        input_data_query: Optional[InputDataQuery] = None,
        contain_parent_task_id_list: bool = False,
        contain_supplementary_data_count: bool = False,
        is_latest: bool = False,
    ) -> list[dict[str, Any]]:
        if input_data_json is None:
            downloading_obj = DownloadingFile(self.service)
            # `NamedTemporaryFile`を使わない理由: Windowsで`PermissionError`が発生するため
            # https://qiita.com/yuji38kwmt/items/c6f50e1fc03dafdcdda0 参考
            with tempfile.TemporaryDirectory() as str_temp_dir:
                json_path = Path(str_temp_dir) / f"{project_id}__input_data.json"
                downloading_obj.download_input_data_json(
                    project_id,
                    str(json_path),
                    is_latest=is_latest,
                )
                with json_path.open(encoding="utf-8") as f:
                    input_data_list = json.load(f)
        else:
            json_path = input_data_json
            with json_path.open(encoding="utf-8") as f:
                input_data_list = json.load(f)

        input_data_id_set = set(input_data_id_list) if input_data_id_list is not None else None
        filtered_input_data_list = [e for e in input_data_list if self.filter_input_data_list(e, input_data_query=input_data_query, input_data_id_set=input_data_id_set)]

        adding_obj = AddingDetailsToInputData(self.service, project_id)
        if contain_parent_task_id_list:
            adding_obj.add_parent_task_id_list_to_input_data_list(input_data_list)

        if contain_supplementary_data_count:
            adding_obj.add_supplementary_data_count_to_input_data_list(input_data_list)

        # 入力データの不要なキーを削除する
        for input_data in input_data_list:
            remove_unnecessary_keys_from_input_data(input_data)
        return filtered_input_data_list


class ListAllInputData(CommandLine):
    def main(self) -> None:
        args = self.args

        input_data_id_list = annofabcli.common.cli.get_list_from_args(args.input_data_id) if args.input_data_id is not None else None
        input_data_query = InputDataQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.input_data_query)) if args.input_data_query is not None else None

        project_id = args.project_id
        super().validate_project(project_id, project_member_roles=[ProjectMemberRole.TRAINING_DATA_USER, ProjectMemberRole.OWNER])

        main_obj = ListInputDataWithJsonMain(self.service)
        input_data_list = main_obj.get_input_data_list(
            project_id=project_id,
            input_data_json=args.input_data_json,
            input_data_id_list=input_data_id_list,
            input_data_query=input_data_query,
            is_latest=args.latest,
            contain_parent_task_id_list=args.with_parent_task_id_list,
            contain_supplementary_data_count=args.with_supplementary_data_count,
        )

        logger.debug(f"入力データ一覧の件数: {len(input_data_list)}")

        if len(input_data_list) > 0:
            output_format = FormatArgument(args.format)
            if output_format == FormatArgument.CSV:
                # pandas.DataFrameでなくpandas.json_normalizeを使う理由:
                # ネストしたオブジェクトを`system_metadata.input_duration`のような列名でアクセスできるようにするため
                df = pandas.json_normalize(input_data_list)
                print_csv(df, output=args.output)
            else:
                print_according_to_format(input_data_list, format=output_format, output=args.output)

        else:
            logger.info("入力データ一覧の件数が0件のため、出力しません。")


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAllInputData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    INPUT_DATA_QUERY_SAMPLE = {"input_data_name": "sample"}  # noqa: N806
    parser.add_argument(
        "-iq",
        "--input_data_query",
        type=str,
        help="入力データの検索クエリをJSON形式で指定します。\n"
        "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。\n"
        f"(ex) ``{json.dumps(INPUT_DATA_QUERY_SAMPLE)}``\n\n"
        "以下のキーを指定できます。\n\n"
        " * ``input_data_id`` \n"
        " * ``input_data_name`` \n"
        " * ``input_data_path``",
    )

    parser.add_argument(
        "-i",
        "--input_data_id",
        type=str,
        nargs="+",
        help="対象のinput_data_idを指定します。\n``file://`` を先頭に付けると、input_data_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "--input_data_json",
        type=Path,
        help="入力データ情報が記載されたJSONファイルのパスを指定すると、JSONに記載された情報を元に入力データ一覧を出力します。\n"
        "JSONファイルは ``$ annofabcli input_data download`` コマンドで取得できます。",
    )

    parser.add_argument(
        "--latest",
        action="store_true",
        help="最新の入力データの情報を出力します。"
        "このオプションを指定すると数分待ちます。Annofabからダウンロードする「入力データ全件ファイル」に、最新の情報を反映させるのに時間がかかるためです。\n"
        "指定しない場合は、コマンドを実行した日の02:00(JST)頃の入力データの一覧が出力されます。",
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
    subcommand_name = "list_all"
    subcommand_help = "すべての入力データの一覧を出力します。"
    description = "すべての入力データの一覧を出力します。\n出力される入力データは、コマンドを実行した日の02:00(JST)頃の状態です。最新の情報を出力したい場合は、 ``--latest`` を指定してください。"
    epilog = "アノテーションユーザまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
