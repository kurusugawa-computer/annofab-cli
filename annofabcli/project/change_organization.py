import argparse
import logging
from typing import Any, Optional

import annofabapi
import requests
from annofabapi.models import Project, ProjectMemberRole
from more_itertools import first_true

import annofabcli
from annofabcli.common.cli import CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class ChangeProjectOrganizationMain:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)

    def change_organization_for_project(self, project_id: str, organization_name: str) -> bool:
        project = self.service.wrapper.get_project_or_none(project_id)
        if project is None:
            logger.warning(f"project_id={project_id} のプロジェクトは存在しないので、スキップします。")
            return False

        if not self.facade.contains_any_project_member_role(project_id, [ProjectMemberRole.OWNER]):
            logger.warning(f"project_id={project_id}: オーナロールでないため、組織を変更できません。project_title={project['title']}")
            return False

        logger.info(f"{project['title']} の組織を {organization_name} に変更します。project_id={project_id}")
        project["organization_name"] = organization_name
        try:
            self.service.api.put_project(project_id, request_body=project)
            logger.info(f"project_id={project_id} の組織を {organization_name} に変更しました。")
            return True
        except requests.HTTPError as e:
            logger.warning(f"project_id={project_id} の組織変更に失敗しました: {e}")
            return False

    def change_organization_for_project_list(self, project_id_list: list[str], organization_name: str):
        logger.info(f"{len(project_id_list)} 件のプロジェクトの組織を {organization_name} に変更します。")
        success_count = 0
        for project_id in project_id_list:
            try:
                result = self.change_organization_for_project(project_id, organization_name)
                if result:
                    success_count += 1
            except requests.HTTPError as e:
                logger.warning(f"project_id={project_id} の組織変更でHTTPエラー: {e}")
        logger.info(f"{success_count} 件のプロジェクトの組織を {organization_name} に変更しました。")


class ChangeProjectOrganization(CommandLine):
    def main(self) -> None:
        args = self.args
        project_id_list = annofabcli.common.cli.get_list_from_args(args.project_id)
        main_obj = ChangeProjectOrganizationMain(self.service)
        main_obj.change_organization_for_project_list(project_id_list=project_id_list, organization_name=args.organization_name)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeProjectOrganization(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-p",
        "--project_id",
        type=str,
        required=True,
        nargs="+",
        help="対象プロジェクトのproject_idを指定します。 ``file://`` を先頭に付けると、project_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "--organization_name",
        type=str,
        required=True,
        help="変更後の組織名を指定してください。",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="強制的に組織を変更します（将来拡張用）。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "change_organization"
    subcommand_help = "プロジェクトの所属組織を変更します。"
    description = "プロジェクトの所属組織を変更します。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
