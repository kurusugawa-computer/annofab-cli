import argparse
import logging
from typing import Any, Dict, List, Optional

import annofabapi
import pandas
import requests
from annofabapi.models import OrganizationMember, Project, ProjectMemberRole, ProjectStatus
from more_itertools import first_true

import annofabcli
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


def create_minimal_dataframe(project_list: List[Project]):
    """必要最小限の列であるDataFrameを作成する"""
    df = pandas.DataFrame(project_list)
    df["last_tasks_updated_datetime"] = [e["summary"]["last_tasks_updated_datetime"] for e in project_list]
    return df[
        [
            "project_id",
            "title",
            "organization_name",
            "project_status",
            "input_data_type",
            "last_tasks_updated_datetime",
            "created_datetime",
        ]
    ]


class ChanegProjectStatusMain:
    def __init__(self, service: annofabapi.Resource):
        self.service = service
        self.facade = AnnofabApiFacade(service)

    @staticmethod
    def get_account_id_from_user_id(organization_member_list: List[OrganizationMember], user_id: str) -> Optional[str]:
        member = first_true(organization_member_list, pred=lambda e: e["user_id"] == user_id)
        if member is not None:
            return member["account_id"]
        else:
            return None

    def get_project_list_from_project_id(self, project_id_list: List[str]) -> List[Project]:
        """
        project_idからプロジェクト一覧を取得する。
        """
        project_list = []
        for project_id in project_id_list:
            project = self.service.wrapper.get_project_or_none(project_id)
            if project is None:
                logger.warning(f"project_id='{project_id}'のプロジェクトにアクセスできませんでした。")
                continue
            organization, _ = self.service.api.get_organization_of_project(project_id)
            project["organization_name"] = organization["organization_name"]
            project_list.append(project)

        return project_list

    def _modify_project_query(self, organization_name: str, project_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        プロジェクト索クエリを修正する。
        ``user_id`` から ``account_id`` に変換する。
        ``except_user_id`` から ``except_account_id`` に変換する。
        ``page`` , ``limit``を削除」する

        Args:

            project_query: タスク検索クエリ（IN/OUT）

        Returns:
            修正したタスク検索クエリ

        """

        def remove_key(arg_key: str):
            if arg_key in project_query:
                logger.info(f"project_query から、`{arg_key}`　キーを削除しました。")
                project_query.pop(arg_key)

        remove_key("page")
        remove_key("limit")

        organization_member_list = self.service.wrapper.get_all_organization_members(organization_name)

        if "user_id" in project_query:
            user_id = project_query["user_id"]
            account_id = self.get_account_id_from_user_id(organization_member_list, user_id)
            if account_id is not None:
                project_query["account_id"] = account_id
            else:
                logger.warning(f"project_query に含まれている user_id: {user_id} のユーザが見つかりませんでした。")

        if "except_user_id" in project_query:
            except_user_id = project_query["except_user_id"]
            except_account_id = self.get_account_id_from_user_id(organization_member_list, except_user_id)
            if except_account_id is not None:
                project_query["except_account_id"] = except_account_id
            else:
                logger.warning(f"project_query に含まれている except_user_id: {except_user_id} のユーザが見つかりませんでした。")

        return project_query

    def change_status_for_project(self, project_id: str, status: ProjectStatus, force_suspend: bool = False) -> bool:
        project = self.service.wrapper.get_project_or_none(project_id)
        if project is None:
            logger.warning(f"project_id={project_id} のプロジェクトは存在しないので、スキップします。")
            return False

        if not self.facade.contains_any_project_member_role(project_id, [ProjectMemberRole.OWNER]):
            logger.warning(f"project_id={project_id}: オーナロールでないため、アノテーションzipを更新できません。project_title={project['title']}")
            return False

        logger.debug(f"{project['title']} のステータスを{status.value} に変更します。project_id={project_id}")
        project["status"] = status.value
        project["last_updated_datetime"] = project["updated_datetime"]
        project["force_suspend"] = force_suspend
        self.service.api.put_project(project_id, request_body=project)
        return True

    def change_status_for_project_list(
        self, project_id_list: List[str], status: ProjectStatus, force_suspend: bool = False
    ):
        """
        複数のプロジェクトに対して、プロジェクトのステータスを変更する。

        Args:
            project_id_list:
            status: 変更後のステータス
            force_suspend: Trueなら作業中タスクがある状態でも停止中にする。

        Returns:

        """
        logger.info(f"{len(project_id_list)} 件のプロジェクトのステータスを {status.value} に変更します。")
        success_count = 0
        for project_id in project_id_list:
            try:
                result = self.change_status_for_project(project_id, status=status, force_suspend=force_suspend)
                if result:
                    success_count += 1

            except requests.HTTPError as e:
                if e.response.status_code == requests.codes.conflict:
                    # 現在のプロジェクトの状態では、ステータスを変更できない場合に発生するエラー
                    logger.warning(e)
                else:
                    raise e

        logger.info(f"{success_count} 件のプロジェクトのステータスを {status.value} に変更しました。")


class ChangeProjectStatus(AbstractCommandLineInterface):
    def main(self):
        args = self.args
        project_id_list = annofabcli.common.cli.get_list_from_args(args.project_id)
        main_obj = ChanegProjectStatusMain(self.service)
        main_obj.change_status_for_project_list(
            project_id_list=project_id_list, status=ProjectStatus(args.status), force_suspend=args.force
        )


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeProjectStatus(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):

    parser.add_argument(
        "-p",
        "--project_id",
        type=str,
        required=True,
        nargs="+",
        help="対象プロジェクトのproject_idを指定します。 ``file://`` を先頭に付けると、project_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "--status",
        type=str,
        choices=[ProjectStatus.ACTIVE.value, ProjectStatus.SUSPENDED.value],
        required=True,
        help="変更後のステータスを指定してください。",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=f"`--status {ProjectStatus.SUSPENDED.value}`を指定している状態で、 ``--force`` を指定した場合、作業中タスクが残っていても停止状態に変更します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "change_status"
    subcommand_help = "プロジェクトのステータスを変更します。"
    description = "プロジェクトのステータスを変更します。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
