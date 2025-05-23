import argparse
import logging
import sys
from typing import Any, Optional

import annofabapi
import pandas
from annofabapi.models import OrganizationMember, Project
from more_itertools import first_true

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import get_columns_with_priority

logger = logging.getLogger(__name__)


def create_minimal_dataframe(project_list: list[Project]):  # noqa: ANN201
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


class ListProjectMain:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)

    @staticmethod
    def get_account_id_from_user_id(organization_member_list: list[OrganizationMember], user_id: str) -> Optional[str]:
        member = first_true(organization_member_list, pred=lambda e: e["user_id"] == user_id)
        if member is not None:
            return member["account_id"]
        else:
            return None

    def get_project_list_from_project_id(self, project_id_list: list[str]) -> list[Project]:
        """
        project_idからプロジェクト一覧を取得する。
        """
        project_list = []
        for index, project_id in enumerate(project_id_list):
            project = self.service.wrapper.get_project_or_none(project_id)
            if project is None:
                logger.warning(f"project_id='{project_id}'のプロジェクトにアクセスできませんでした。")
                continue

            organization, _ = self.service.api.get_organization_of_project(project_id)
            project["organization_name"] = organization["organization_name"]
            project_list.append(project)

            if (index + 1) % 100 == 0:
                logger.debug(f"{index + 1} 件のプロジェクト情報を取得しました。")

        return project_list

    def _modify_project_query(self, organization_name: str, project_query: dict[str, Any]) -> dict[str, Any]:
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

        def remove_key(arg_key: str):  # noqa: ANN202
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

    def get_project_list_from_organization(self, organization_name: str, project_query: Optional[dict[str, Any]] = None) -> list[Project]:
        """
        組織名からプロジェクト一覧を取得する。
        """

        if project_query is not None:
            project_query = self._modify_project_query(organization_name, project_query)

        logger.debug(f"project_query: {project_query}")
        project_list = self.service.wrapper.get_all_projects_of_organization(organization_name, query_params=project_query)

        for project in project_list:
            project["organization_name"] = organization_name

        return project_list


class ListProject(CommandLine):
    """
    プロジェクト一覧を表示する。
    """

    PRIOR_COLUMNS = [  # noqa: RUF012
        "organization_id",
        "organization_name",
        "project_id",
        "title",
        "overview",
        "project_status",
        "input_data_type",
        "created_datetime",
        "updated_datetime",
        "summary",
        "configuration",
    ]

    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        if args.project_id is not None:
            if args.project_query is not None:
                logger.warning("`--project_id`と`--project_query`は同時に指定できません。")
            if args.include_not_joined_project:
                logger.warning("`--project_id`と`--include_not_joined_project`は同時に指定できません。")

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_query = {}

        organization_name = args.organization
        main_obj = ListProjectMain(self.service)
        if organization_name is not None:
            if not args.include_not_joined_project:
                # 所属しているプロジェクトのみ出力
                project_query.update({"user_id": self.service.api.login_user_id})

            if args.project_query is not None:
                project_query.update(annofabcli.common.cli.get_json_from_args(args.project_query))
            project_list = main_obj.get_project_list_from_organization(organization_name, project_query)
        else:
            assert args.project_id is not None
            project_id_list = annofabcli.common.cli.get_list_from_args(args.project_id)
            project_list = main_obj.get_project_list_from_project_id(project_id_list)

        logger.info(f"プロジェクト一覧の件数: {len(project_list)}")

        if args.format == FormatArgument.MINIMAL_CSV.value:
            df = create_minimal_dataframe(project_list)
            self.print_csv(df)
        elif args.format == FormatArgument.CSV.value:
            df = pandas.DataFrame(project_list)
            columns = get_columns_with_priority(df, prior_columns=self.PRIOR_COLUMNS)
            self.print_csv(df[columns])
        else:
            self.print_according_to_format(project_list)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListProject(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    query_group = parser.add_mutually_exclusive_group(required=True)

    query_group.add_argument(
        "-p",
        "--project_id",
        type=str,
        nargs="+",
        help="対象プロジェクトのproject_idを指定します。 ``file://`` を先頭に付けると、project_idの一覧が記載されたファイルを指定できます。",
    )

    query_group.add_argument("-org", "--organization", type=str, help="対象の組織名を指定してください。")

    parser.add_argument(
        "-pq",
        "--project_query",
        type=str,
        help="プロジェクトの検索クエリをJSON形式で指定します。'--organization'を指定したときのみ有効なオプションです。"
        "指定しない場合は、組織配下のすべてのプロジェクトを取得します。"
        " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        "クエリのフォーマットは、[getProjectsOfOrganization API]"
        "(https://annofab.com/docs/api/#operation/getProjectsOfOrganization)のクエリパラメータと同じです。"
        "さらに追加で、``user_id`` , ``except_user_id`` キーも指定できます。"
        "ただし ``page`` , ``limit`` キーは指定できません。",
    )

    parser.add_argument(
        "--include_not_joined_project",
        action="store_true",
        help="'--organization'を指定したときのみ有効なオプションです。指定した場合は、所属していないプロジェクトも出力します。"
        "指定しない場合は、自分が所属しているプロジェクトのみ出力します"
        '（ ``--project_query \'{"user_id":"my_user_id"}\'`` が指定されている状態と同じ）',
    )

    argument_parser.add_format(
        choices=[
            FormatArgument.CSV,
            FormatArgument.MINIMAL_CSV,
            FormatArgument.JSON,
            FormatArgument.PRETTY_JSON,
            FormatArgument.PROJECT_ID_LIST,
        ],
        default=FormatArgument.CSV,
    )
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list"
    subcommand_help = "プロジェクト一覧を出力します。"
    description = "プロジェクト一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
