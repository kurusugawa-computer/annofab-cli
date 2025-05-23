import argparse
import logging
from typing import Any, Optional

import requests
from annofabapi.models import ProjectMemberRole

import annofabcli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class DeleteInputData(CommandLine):
    """
    入力データを削除する。
    """

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

    def confirm_delete_input_data(self, input_data_id: str, input_data_name: str, used_task_id_list: list[str]) -> bool:
        message_for_confirm = f"入力データ(input_data_id='{input_data_id}', input_data_name='{input_data_name}') を削除しますか？"
        if len(used_task_id_list) > 0:
            message_for_confirm += f"タスク{used_task_id_list}に使われています。"
        return self.confirm_processing(message_for_confirm)

    def confirm_delete_supplementary(self, input_data_id: str, input_data_name: str, supplementary_data_list: list[dict[str, Any]]) -> bool:
        message_for_confirm = f"入力データに紐づく補助情報 {len(supplementary_data_list)} 件を削除しますか？ (input_data_id='{input_data_id}', input_data_name='{input_data_name}') "
        return self.confirm_processing(message_for_confirm)

    def delete_input_data(self, project_id: str, input_data_id: str, input_data_index: int, delete_supplementary: bool, force: bool):  # noqa: ANN201, FBT001
        input_data = self.service.wrapper.get_input_data_or_none(project_id, input_data_id)
        if input_data is None:
            logger.info(f"input_data_id='{input_data_id}'である入力データは存在しません。")
            return False

        task_list = self.service.wrapper.get_all_tasks(project_id, query_params={"input_data_ids": input_data_id})
        input_data_name = input_data["input_data_name"]

        used_task_id_list = []
        if len(task_list) > 0:
            used_task_id_list = [e["task_id"] for e in task_list]
            if not force:
                logger.debug(
                    f"入力データ(input_data_id='{input_data_id}', "
                    f"input_data_name='{input_data_name}')はタスクに使われているため、スキップします。削除する場合は`--force`を付けてください。\n"
                    f"task_id_list='{used_task_id_list}'"
                )
                return False
            else:
                logger.debug(f"入力データ(input_data_id='{input_data_id}', input_data_name='{input_data_name}')はタスクに使われています。task_id_list='{used_task_id_list}'")

        if not self.confirm_delete_input_data(input_data_id, input_data_name, used_task_id_list=used_task_id_list):
            return False

        self.service.api.delete_input_data(project_id, input_data_id)
        logger.debug(f"{input_data_index + 1!s} 件目: 入力データ(input_data_id='{input_data_id}', input_data_name='{input_data_name}') を削除しました。")

        if delete_supplementary:
            supplementary_data_list, _ = self.service.api.get_supplementary_data_list(project_id, input_data_id)
            if len(supplementary_data_list) > 0 and self.confirm_delete_supplementary(input_data_id, input_data_name, supplementary_data_list=supplementary_data_list):
                deleted_supplementary_data = self.delete_supplementary_data_list_for_input_data(project_id, input_data_id, supplementary_data_list=supplementary_data_list)
                logger.debug(
                    f"{input_data_index + 1!s} 件目: 入力データ(input_data_id='{input_data_id}', "
                    f"input_data_name='{input_data_name}') に紐づく補助情報を"
                    f" {deleted_supplementary_data} / {len(supplementary_data_list)} 件削除しました。"
                )
        return True

    def delete_input_data_list(self, project_id: str, input_data_id_list: list[str], delete_supplementary: bool, force: bool):  # noqa: ANN201, FBT001
        """
        タスクに使われていない入力データを削除する。
        """

        super().validate_project(project_id, [ProjectMemberRole.OWNER])
        project_title = self.facade.get_project_title(project_id)
        logger.info(f"プロジェクト'{project_title}'から 、{len(input_data_id_list)} 件の入力データを削除します。")

        count_delete_input_data = 0
        for input_data_index, input_data_id in enumerate(input_data_id_list):
            try:
                result = self.delete_input_data(
                    project_id,
                    input_data_id,
                    input_data_index=input_data_index,
                    delete_supplementary=delete_supplementary,
                    force=force,
                )
                if result:
                    count_delete_input_data += 1

            except requests.exceptions.HTTPError:
                logger.warning(f"input_data_id='{input_data_id}'である入力データの削除に失敗しました。", exc_info=True)
                continue

        logger.info(f"プロジェクト'{project_title}'から 、{count_delete_input_data}/{len(input_data_id_list)} 件の入力データを削除しました。")

    def main(self) -> None:
        args = self.args
        input_data_id_list = annofabcli.common.cli.get_list_from_args(args.input_data_id)
        self.delete_input_data_list(
            args.project_id,
            input_data_id_list=input_data_id_list,
            delete_supplementary=args.delete_supplementary,
            force=args.force,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteInputData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    parser.add_argument(
        "-i",
        "--input_data_id",
        type=str,
        required=True,
        nargs="+",
        help="削除対象の入力データのinput_data_idを指定します。 ``file://`` を先頭に付けると、input_data_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument("--force", action="store_true", help="タスクに使われている入力データも削除します。")

    parser.add_argument("--delete_supplementary", action="store_true", help="入力データに紐づく補助情報も削除します。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "delete"
    subcommand_help = "入力データを削除します。"
    description = "入力データを削除します。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
