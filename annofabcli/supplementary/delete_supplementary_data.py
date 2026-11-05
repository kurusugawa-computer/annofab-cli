import argparse
import logging
from typing import Any

import annofabapi
import requests
from annofabapi.models import ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.annofab.supplementary_data import get_supplementary_data_dict_in_bulk
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class DeleteSupplementaryDataMain(CommandLineWithConfirm):
    def __init__(self, service: annofabapi.Resource, *, all_yes: bool = False) -> None:
        self.service = service
        CommandLineWithConfirm.__init__(self, all_yes)

    def delete_supplementary_data_list_for_input_data(self, project_id: str, input_data_id: str, supplementary_data_list: list[dict[str, Any]]) -> int:
        """
        入力データ配下の補助情報を削除する。

        Args:
            project_id:
            input_data_id:
            supplementary_data_list:

        Returns:
            削除した補助情報の個数

        """
        deleted_count = 0
        for supplementary_data in supplementary_data_list:
            supplementary_data_id = supplementary_data["supplementary_data_id"]
            try:
                self.service.api.delete_supplementary_data(project_id, input_data_id=input_data_id, supplementary_data_id=supplementary_data_id)
                logger.debug(
                    f"補助情報を削除しました。input_data_id='{input_data_id}', supplementary_data_id='{supplementary_data_id}', "
                    f"supplementary_data_name='{supplementary_data['supplementary_data_name']}'"
                )
                deleted_count += 1
            except requests.HTTPError:
                logger.warning(
                    f"補助情報の削除に失敗しました。input_data_id='{input_data_id}', supplementary_data_id='{supplementary_data_id}', "
                    f"supplementary_data_name='{supplementary_data['supplementary_data_name']}'",
                    exc_info=True,
                )
                continue

        return deleted_count

    def delete_supplementary_data_list(self, project_id: str, input_data_id_list: list[str]) -> None:
        dict_deleted_count: dict[str, int] = {}
        supplementary_data_dict = get_supplementary_data_dict_in_bulk(self.service, project_id, input_data_id_list)
        for input_data_id in input_data_id_list:
            input_data = self.service.wrapper.get_input_data_or_none(project_id, input_data_id)
            if input_data is None:
                logger.warning(f"input_data_id='{input_data_id}' の入力データは存在しないので、補助情報の削除をスキップします。")
                continue
            input_data_name = input_data["input_data_name"]

            supplementary_data_list = supplementary_data_dict[input_data_id]
            if len(supplementary_data_list) == 0:
                logger.debug("入力データに紐づく補助情報は存在しないので、削除をスキップします。")
                continue

            message_for_confirm = f"入力データに紐づく補助情報 {len(supplementary_data_list)} 件を削除しますか？ (input_data_id='{input_data_id}', input_data_name='{input_data_name}') "
            if not self.confirm_processing(message_for_confirm):
                continue

            try:
                deleted_supplementary_data_count = self.delete_supplementary_data_list_for_input_data(project_id, input_data_id, supplementary_data_list)
                dict_deleted_count[input_data_id] = deleted_supplementary_data_count
                logger.debug(
                    f"入力データに紐づく補助情報を {deleted_supplementary_data_count} / {len(supplementary_data_list)} 件削除しました。"
                    f"(input_data_id='{input_data_id}', "
                    f"input_data_name='{input_data_name}') "
                )

            except Exception:  # pylint: disable=broad-except
                logger.warning(f"入力データ(input_data_id='{input_data_id}')配下の補助情報の削除に失敗しました。", exc_info=True)

        logger.info(f"{len(dict_deleted_count)} / {len(input_data_id_list)} 件の入力データに紐づく補助情報を削除しました。")


class DeleteSupplementaryData(CommandLine):
    """入力データに紐づく全補助情報を削除します。"""

    def main(self) -> None:
        """入力データごとに確認して補助情報を削除します。

        Args:
            なし。

        Returns:
            None。
        """
        args = self.args
        super().require_project_access(args.project_id, [ProjectMemberRole.OWNER])
        input_data_id_list = annofabcli.common.cli.get_list_from_args(args.input_data_id)
        main_obj = DeleteSupplementaryDataMain(self.service, all_yes=args.yes)
        main_obj.delete_supplementary_data_list(args.project_id, input_data_id_list)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteSupplementaryData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "-i",
        "--input_data_id",
        type=str,
        required=True,
        nargs="+",
        help=(
            "削除する補助情報に紐づく入力データのinput_data_idを指定してください。"
            "指定した入力データに紐づくすべての補助情報を削除します。"
            " ``file://`` を先頭に付けると、input_data_idの一覧が記載されたファイルを指定できます。"
            " ファイルを読み込む場合は、ファイル指定を1個だけ渡してください。"
            "直接指定する値や別のファイル指定とは併用できません。"
        ),
    )

    parser.set_defaults(subcommand_func=main)


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "delete"
    subcommand_help = "指定した入力データに紐づくすべての補助情報を削除します。"
    description = "指定した入力データに紐づくすべての補助情報を削除します。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.create_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
