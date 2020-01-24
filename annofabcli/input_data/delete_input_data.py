import argparse
import logging
from typing import Any, Dict, List

import requests
from annofabapi.models import ProjectMemberRole

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class DeleteInputData(AbstractCommandLineInterface):
    """
    タスクに使われていない入力データを削除する。
    """

    @annofabcli.utils.allow_404_error
    def get_input_data(self, project_id: str, input_data_id: str) -> Dict[str, Any]:
        input_data, _ = self.service.api.get_input_data(project_id, input_data_id)
        return input_data

    def confirm_delete_input_data(self, input_data_id: str, input_data_name: str) -> bool:
        message_for_confirm = (
            f"入力データ(input_data_id='{input_data_id}', " f"input_data_name='{input_data_name}') を削除しますか？"
        )
        return self.confirm_processing(message_for_confirm)

    def delete_input_data(self, project_id: str, input_data_id: str):
        input_data = self.get_input_data(project_id, input_data_id)
        if input_data is None:
            logger.info(f"input_data_id={input_data_id} は存在しません。")
            return False

        task_list = self.service.wrapper.get_all_tasks(project_id, query_params={"input_data_ids": input_data_id})
        input_data_name = input_data["input_data_name"]
        if len(task_list) > 0:
            task_id_list = [e["task_id"] for e in task_list]
            logger.info(
                f"入力データ(input_data_id='{input_data_id}', "
                f"input_data_name='{input_data_name}')はタスクに使われているので、削除しません。"
                f"task_id_list='{task_id_list}'"
            )
            return False

        if not self.confirm_delete_input_data(input_data_id, input_data_name):
            return False

        self.service.api.delete_input_data(project_id, input_data_id)
        logger.info(f"入力データ(input_data_id='{input_data_id}', " f"input_data_name='{input_data_name}') を削除しました。")
        return True

    def delete_input_data_list(self, project_id: str, input_data_id_list: List[str]):
        """
        タスクに使われていない入力データを削除する。
        """

        super().validate_project(project_id, [ProjectMemberRole.OWNER])
        project_title = self.facade.get_project_title(project_id)
        logger.info(f"プロジェクト'{project_title}'から 、{len(input_data_id_list)} 件の入力データを削除します。")

        count_delete_input_data = 0
        for input_data_id in input_data_id_list:
            try:
                result = self.delete_input_data(project_id, input_data_id)
                if result:
                    count_delete_input_data += 1

            except requests.exceptions.HTTPError as e:
                logger.warning(e)
                logger.warning(f"input_data_id='{input_data_id}'の削除に失敗しました。")
                continue

        logger.info(f"プロジェクト'{project_title}'から 、{count_delete_input_data} 件の入力データを削除しました。")

    def main(self):
        args = self.args
        input_data_id_list = annofabcli.common.cli.get_list_from_args(args.input_data_id)
        self.delete_input_data_list(args.project_id, input_data_id_list=input_data_id_list)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteInputData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    parser.add_argument(
        "-i",
        "--input_data_id",
        type=str,
        required=True,
        nargs="+",
        help="削除対象の入力データのinput_data_idを指定します。" "`file://`を先頭に付けると、input_data_idの一覧が記載されたファイルを指定できます。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "delete"
    subcommand_help = "入力データを削除します。"
    description = "入力データを削除します。ただし、タスクに使われている入力データは削除できません。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
