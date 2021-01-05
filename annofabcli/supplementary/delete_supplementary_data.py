import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import annofabapi
import pandas
import requests
from annofabapi.models import ProjectMemberRole
from more_itertools import first_true

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstracCommandCinfirmInterface,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
)

logger = logging.getLogger(__name__)


class DeleteSupplementaryDataMain(AbstracCommandCinfirmInterface):
    def __init__(self, service: annofabapi.Resource, all_yes: bool = False):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        AbstracCommandCinfirmInterface.__init__(self, all_yes)

    def delete_supplementary_data_list_for_input_data(
        self, project_id: str, input_data_id: str, supplementary_data_id_list: List[str]
    ) -> int:
        """
        入力データ配下の補助情報を削除する。

        Args:
            project_id:
            input_data_id:
            supplementary_data_id_list:

        Returns:
            削除した補助情報の個数

        """

        def _get_supplementary_data_list(supplementary_data_id: str) -> Optional[Dict[str, Any]]:
            return first_true(
                supplementary_data_list, pred=lambda e: e["supplementary_data_id"] == supplementary_data_id
            )

        input_data = self.service.wrapper.get_input_data_or_none(project_id, input_data_id)
        if input_data is None:
            logger.warning(f"input_data_id={input_data_id} の入力データは存在しないのでスキップします。")
            return 0

        supplementary_data_list, _ = self.service.api.get_supplementary_data_list(project_id, input_data_id)

        deleted_count = 0
        for supplementary_data_id in supplementary_data_id_list:
            supplementary_data = _get_supplementary_data_list(supplementary_data_id)
            if supplementary_data is None:
                logger.warning(
                    f"input_data_id={input_data_id} の入力データに、"
                    f"supplementary_data_id={supplementary_data_id} の補助情報は存在しないのでスキップします。"
                )
                continue

            message_for_confirm = (
                f"補助情報 supplementary_data_id={supplementary_data_id}, "
                f"supplementary_data_name={supplementary_data['supplementary_data_name']} を削除しますか？"
            )
            if not self.confirm_processing(message_for_confirm):
                continue

            try:
                self.service.api.delete_supplementary_data(
                    project_id, input_data_id=input_data_id, supplementary_data_id=supplementary_data_id
                )
                logger.debug(
                    f"補助情報 supplementary_data_id={supplementary_data_id}, "
                    f"supplementary_data_name={supplementary_data['supplementary_data_name']} を削除しました。"
                    f"(入力データ input_data_id={input_data_id}, "
                    f"input_data_name={input_data['input_data_name']} に紐付いている)"
                )
                deleted_count += 1
            except requests.HTTPError as e:
                logger.warning(e)
                logger.warning(
                    f"補助情報 supplementary_data_id={supplementary_data_id}, "
                    f"supplementary_data_name={supplementary_data['supplementary_data_name']} の削除に失敗しました。"
                )
                continue
        return deleted_count

    def delete_supplementary_data_list(self, project_id: str, csv_path: Path):
        df = pandas.read_csv(
            str(csv_path),
            sep=",",
            header=None,
            names=[
                "input_data_id",
                "supplementary_data_id",
            ],
        )
        input_data_dict = defaultdict(list)
        for input_data_id, supplementary_data_id in zip(df["input_data_id"], df["supplementary_data_id"]):
            input_data_dict[input_data_id].append(supplementary_data_id)

        deleted_count = 0
        for input_data_id, supplementary_data_id_list in input_data_dict.items():
            try:
                deleted_count += self.delete_supplementary_data_list_for_input_data(
                    project_id, input_data_id, supplementary_data_id_list
                )
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(e)
                logger.warning(f"入力データ(input_data_id={input_data_id})配下の補助情報の削除に失敗しました。")

        logger.info(f"{deleted_count} / {len(df)} 件の補助情報を削除しました。")


class DeleteSupplementaryData(AbstractCommandLineInterface):
    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli supplementary_data put: error:"
        if args.csv is not None:
            if not Path(args.csv).exists():
                print(f"{COMMON_MESSAGE} argument --csv: ファイルパスが存在しません。 '{args.csv}'", file=sys.stderr)
                return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            return

        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        main_obj = DeleteSupplementaryDataMain(self.service, all_yes=args.yes)

        main_obj.delete_supplementary_data_list(project_id, csv_path=args.csv)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteSupplementaryData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--csv",
        type=str,
        required=True,
        help=(
            "削除する補助情報が記載されたCVファイルのパスを指定してください。"
            "CSVのフォーマットは、「1列目:input_data_id(required), 2列目:supplementary_data_id(required) です。"
        ),
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "delete"
    subcommand_help = "補助情報を削除します。"
    description = "補助情報を削除します。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
