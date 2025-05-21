import argparse
import logging
from typing import Any, Optional

import annofabapi
import requests
from annofabapi.models import Project, ProjectMemberRole, OrganizationMemberRole, ProjectJobType
from more_itertools import first_true

import annofabcli
from annofabcli.common.cli import CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
    get_json_from_args,
)

logger = logging.getLogger(__name__)


class ChangeProjectOrganizationMain(CommandLineWithConfirm):
    def __init__(self, service: annofabapi.Resource,*,all_yes: bool = False,) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)
        super().__init__(all_yes)
        

    def change_organization_for_project(self, project_id: str, organization_name: str) -> bool:
        project = self.service.wrapper.get_project_or_none(project_id)
        project_name = project['title']
        if project is None:
            logger.warning(f"project_id='{project_id}'のプロジェクトは存在しないので、スキップします。")
            return False


        if not self.confirm_processing(f"project_id='{project_id}'のプロジェクトの組織を'{organization_name}'に変更しますか？ :: project_name='{project_name}'"):
            return False
        
        logger.info(f"{project['title']} の組織を {organization_name} に変更します。project_id={project_id}")
        request_body = copy.deepcopy(project)
        request_body["organization_name"] = organization_name
        request_body["last_updated_datetime"] = project["updated_datetime"]

        content, _ = self.service.api.put_project(project_id, request_body=request_body)
        job = content["job"]
        logger.info(f"project_id='{project_id}'のプロジェクトの所属先組織を'{organization_name}'に変更します。 :: job_id='{job['job_id']}'")

    def change_organization_for_project_list(self, project_id_list: list[str], organization_name: str):
        if not self.facade.contains_any_organization_member_role(project_id, [OrganizationMemberRole.OWNER, OrganizationMemberRole.ADMINISTRATOR]):
            logger.warning(f"変更先組織'{organization_name}'に対して管理者ロールまたはオーナロールでないため、プロジェクトの所属する組織を変更できません。")
            return

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
        
    def wait_until_jobs_finished(self, jobs: list[dict[str, Any]] ) -> None:
        for job in jobs:
            self.service.wrapper.wait_until_job_finished(project_id=job["project_id"], job_id=job["job_id"], job_type=ProjectJobType(job["job_type"]))


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
        "--organization",
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
    subcommand_help = "プロジェクトの所属する組織を変更します。"
    epilog = "プロジェクトのオーナロール、変更先組織の管理者またはオーナーロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
