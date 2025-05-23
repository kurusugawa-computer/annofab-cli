import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from functools import partial
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Optional

import annofabapi
import pandas
import requests
from annofabapi.models import ProjectMemberRole, SupplementaryData
from dataclasses_json import DataClassJsonMixin
from more_itertools import first_true

import annofabcli
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


def convert_supplementary_data_name_to_supplementary_data_id(supplementary_data_name: str) -> str:
    """
    補助情報データ名から、補助情報データIDを生成します。
    * IDに使えない文字以外は`__`に変換する。
    """
    return re.sub(r"[^a-zA-Z0-9_.-]", "__", supplementary_data_name)


@dataclass
class CliSupplementaryData(DataClassJsonMixin):
    """
    コマンドラインから指定された（`--csv`または`--json`）補助情報
    """

    input_data_id: str
    supplementary_data_name: str
    supplementary_data_path: str
    supplementary_data_id: Optional[str] = None
    supplementary_data_type: Optional[str] = None
    supplementary_data_number: Optional[int] = None


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
        all_yes:
    """

    def __init__(self, service: annofabapi.Resource, *, all_yes: bool = False) -> None:
        self.service = service
        self.all_yes = all_yes
        self.supplementary_data_cache: dict[tuple[str, str], list[SupplementaryData]] = {}

    def put_supplementary_data(self, project_id: str, supplementary_data: SupplementaryDataForPut) -> None:
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
                f"'{file_path}'を補助情報として登録します。 :: "
                f"input_data_id='{supplementary_data.input_data_id}', "
                f"supplementary_data_id='{supplementary_data.supplementary_data_id}', "
                f"supplementary_data_name='{supplementary_data.supplementary_data_name}'"
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
                supplementary_data_type = "text" if supplementary_data.supplementary_data_path.endswith(".txt") else "image"

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

    def confirm_put_supplementary_data(self, csv_supplementary_data: CliSupplementaryData, supplementary_data_id: str, *, already_exists: bool = False) -> bool:
        if already_exists:
            message_for_confirm = f"supplementary_data_name='{csv_supplementary_data.supplementary_data_name}', supplementary_data_id='{supplementary_data_id}'の補助情報を更新しますか？"
        else:
            message_for_confirm = f"supplementary_data_name='{csv_supplementary_data.supplementary_data_name}', supplementary_data_id='{supplementary_data_id}'の補助情報を登録しますか？"

        return self.confirm_processing(message_for_confirm)

    def put_supplementary_data_main(self, project_id: str, csv_data: CliSupplementaryData, *, overwrite: bool = False) -> bool:
        last_updated_datetime = None
        input_data_id = csv_data.input_data_id
        supplementary_data_id = (
            csv_data.supplementary_data_id if csv_data.supplementary_data_id is not None else convert_supplementary_data_name_to_supplementary_data_id(csv_data.supplementary_data_name)
        )

        supplementary_data_list = self.service.wrapper.get_supplementary_data_list_or_none(project_id, input_data_id)
        if supplementary_data_list is None:
            # 入力データが存在しない場合は、`supplementary_data_list`はNoneになる
            logger.warning(f"input_data_id='{input_data_id}'である入力データは存在しないため、補助情報の登録をスキップします。")
            return False

        old_supplementary_data = first_true(supplementary_data_list, pred=lambda e: e["supplementary_data_id"] == supplementary_data_id)

        # 補助情報numberが未指定の場合は、既存の補助情報numberの最大値+1にする
        max_supplementary_data_number = max((e["supplementary_data_number"] for e in supplementary_data_list), default=0)
        if csv_data.supplementary_data_number is not None:
            supplementary_data_number = csv_data.supplementary_data_number
        elif old_supplementary_data is not None:
            supplementary_data_number = old_supplementary_data["supplementary_data_number"]
        else:
            supplementary_data_number = max_supplementary_data_number + 1

        if old_supplementary_data is not None:
            if overwrite:
                logger.debug(
                    f"supplementary_data_id='{supplementary_data_id}'である補助情報がすでに存在します。 :: "
                    f"input_data_id='{input_data_id}', supplementary_data_name='{csv_data.supplementary_data_name}'"
                )
                last_updated_datetime = old_supplementary_data["updated_datetime"]
            else:
                logger.debug(
                    f"supplementary_data_id='{supplementary_data_id}'である補助情報がすでに存在するので、補助情報の登録をスキップします。 :: "
                    f"input_data_id='{input_data_id}', supplementary_data_name='{csv_data.supplementary_data_name}'"
                )
                return False

        file_path = get_file_scheme_path(csv_data.supplementary_data_path)
        if file_path is not None:  # noqa: SIM102
            if not Path(file_path).exists():
                logger.warning(f"'{csv_data.supplementary_data_path}' は存在しません。補助情報の登録をスキップします。")
                return False

        if not self.confirm_put_supplementary_data(csv_data, supplementary_data_id, already_exists=last_updated_datetime is not None):
            return False

        # 補助情報を登録
        supplementary_data_for_put = SupplementaryDataForPut(
            input_data_id=csv_data.input_data_id,
            supplementary_data_id=supplementary_data_id,
            supplementary_data_name=csv_data.supplementary_data_name,
            supplementary_data_path=csv_data.supplementary_data_path,
            supplementary_data_type=csv_data.supplementary_data_type,
            supplementary_data_number=supplementary_data_number,
            last_updated_datetime=last_updated_datetime,
        )
        try:
            self.put_supplementary_data(project_id, supplementary_data_for_put)
            logger.debug(
                f"補助情報を登録しました。 :: "
                f"input_data_id='{supplementary_data_for_put.input_data_id}', "
                f"supplementary_data_id='{supplementary_data_for_put.supplementary_data_id}', "
                f"supplementary_data_name='{supplementary_data_for_put.supplementary_data_name}'"
            )
            return True  # noqa: TRY300

        except requests.exceptions.HTTPError:
            logger.warning(
                f"補助情報の登録に失敗しました。 ::"
                f"input_data_id='{supplementary_data_for_put.input_data_id}',"
                f"supplementary_data_id='{supplementary_data_for_put.supplementary_data_id}', "
                f"supplementary_data_name='{supplementary_data_for_put.supplementary_data_name}'",
                exc_info=True,
            )
            return False


class PutSupplementaryData(CommandLine):
    """
    補助情報をCSVで登録する。
    """

    def put_supplementary_data_list(
        self,
        project_id: str,
        supplementary_data_list: list[CliSupplementaryData],
        *,
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

        obj = SubPutSupplementaryData(service=self.service, all_yes=self.all_yes)
        if parallelism is not None:
            partial_func = partial(obj.put_supplementary_data_main, project_id, overwrite=overwrite)
            with Pool(parallelism) as pool:
                result_bool_list = pool.map(partial_func, supplementary_data_list)
                count_put_supplementary_data = len([e for e in result_bool_list if e])

        else:
            for csv_supplementary_data in supplementary_data_list:
                result = obj.put_supplementary_data_main(project_id, csv_data=csv_supplementary_data, overwrite=overwrite)
                if result:
                    count_put_supplementary_data += 1

        logger.info(f"{project_title} に、{count_put_supplementary_data} / {len(supplementary_data_list)} 件の補助情報を登録しました。")

    @staticmethod
    def get_supplementary_data_list_from_dict(supplementary_data_dict_list: list[dict[str, Any]]) -> list[CliSupplementaryData]:
        return [CliSupplementaryData.from_dict(e) for e in supplementary_data_dict_list]

    @staticmethod
    def get_supplementary_data_list_from_csv(csv_path: Path) -> list[CliSupplementaryData]:
        df = pandas.read_csv(
            str(csv_path),
            dtype={
                "input_data_id": "string",
                "supplementary_data_id": "string",
                "supplementary_data_name": "string",
                "supplementary_data_path": "string",
                "supplementary_data_type": "string",
                "supplementary_data_number": "Int64",
            },
        )
        supplementary_data_list = [CliSupplementaryData.from_dict(e) for e in df.to_dict("records")]
        return supplementary_data_list

    COMMON_MESSAGE = "annofabcli supplementary_data put: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.csv is not None:  # noqa: SIM102
            if not Path(args.csv).exists():
                print(f"{self.COMMON_MESSAGE} argument --csv: ファイルパスが存在しません。 '{args.csv}'", file=sys.stderr)  # noqa: T201
                return False

        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず ``--yes`` を指定してください。",
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
            supplementary_data_list = self.get_supplementary_data_list_from_csv(Path(args.csv))
        elif args.json is not None:
            supplementary_data_list = self.get_supplementary_data_list_from_dict(get_json_from_args(args.json))
        else:
            print(  # noqa: T201
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


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PutSupplementaryData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    file_group = parser.add_mutually_exclusive_group(required=True)
    file_group.add_argument(
        "--csv",
        type=str,
        help=(
            "補助情報が記載されたCSVファイルのパスを指定してください。CSVのフォーマットは、以下の通りです。\n"
            "\n"
            " * ヘッダ行あり, カンマ区切り\n"
            " * input_data_id (required)\n"
            " * supplementary_data_name (required)\n"
            " * supplementary_data_path (required)\n"
            " * supplementary_data_id\n"
            " * supplementary_data_type\n"
            " * supplementary_data_number\n"
            "\n"
            "各項目の詳細は https://annofab-cli.readthedocs.io/ja/latest/command_reference/supplementary/put.html を参照してください。"
        ),
    )

    JSON_SAMPLE = [  # noqa: N806
        {
            "input_data_id": "input1",
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
        help="指定した場合、supplementary_data_idがすでに存在していたら上書きします。指定しなければ、スキップします。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="並列度。指定しない場合は、逐次的に処理します。必ず ``--yes`` を指定してください。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "put"
    subcommand_help = "補助情報を登録します。"
    description = "補助情報を登録します。"
    epilog = "オーナーロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
