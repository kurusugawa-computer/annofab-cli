"""
プロジェクトのユーザを表示する。
"""
import argparse
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Union  # pylint: disable=unused-import

import requests

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class ListUser(AbstractCommandLineInterface):
    """
    ユーザを表示する
    """
    def list_role_with_organization(self, organization_name: str):

        # 進行中で自分自身が所属しているプロジェクトの一覧を取得する
        # my_account_id = self.facade.get_my_account_id()
        try:
            for user in self.service.wrapper.get_all_organization_members(organization_name):
                print(f"{user['user_id']}\t{user['username']}")

            logger.info(f"{organization_name}のユーザ表示成功。")

        except requests.exceptions.HTTPError as e:
            logger.warning(e)
            logger.warning(f"エラーのため、{organization_name} から表示できなかった。")

    def list_role_with_project_id(self, project_id_list: List[str]):
        for project_id in project_id_list:
            try:
                if not self.facade.my_role_is_owner(project_id):
                    logger.warning(f"オーナではないため、プロジェクトメンバを表示できません。" f"project_id = {project_id}")
                    continue

                project_title = self.service.api.get_project(project_id)[0]["title"]
                for user in self.service.wrapper.get_all_project_members(project_id):
                    print(f"{user['project_id']}\t{user['user_id']}\t{user['username']}")

                logger.info(f"{project_title}から表示成功. project_id={project_id}")

            except requests.exceptions.HTTPError as e:
                logger.warning(e)
                logger.warning(f"エラーのため、project_id = {project_id} のプロジェクトから表示できなかった。")

    def main(self, args):
        super().process_common_args(args, __file__, logger)

        if args.organization is not None:
            self.list_role_with_organization(args.organization)

        elif args.project_id is not None:
            project_id_list = annofabcli.common.cli.get_list_from_args(args.project_id)
            self.list_role_with_project_id(project_id_list)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    ListUser(service, facade).main(args)


def parse_args(parser: argparse.ArgumentParser):
    list_group = parser.add_mutually_exclusive_group(required=True)
    list_group.add_argument('-p', '--project_id', type=str, nargs='+',
                            help='ユーザを表示するプロジェクトのproject_idを指定してください。`file://`を先頭に付けると、一覧が記載されたファイルを指定できます。')

    list_group.add_argument('--organization', type=str, help='組織配下のすべてのプロジェクトのユーザを表示したい場合は、組織名を指定してください。')

    parser.set_defaults(subcommand_func=main)


def add_parser_deprecated(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_users"
    subcommand_help = "複数のプロジェクトのユーザを表示する。"
    description = ("複数のプロジェクトのユーザを表示する。")
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list"
    subcommand_help = "複数のプロジェクトのユーザを表示する。"
    description = ("複数のプロジェクトのユーザを表示する。")
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
