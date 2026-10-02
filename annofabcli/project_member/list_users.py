import argparse
import logging
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor

import pandas
import requests
from annofabapi.models import ProjectMember

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import get_columns_with_priority

logger = logging.getLogger(__name__)


class ListProjectMembers(CommandLine):
    """
    ユーザを表示する
    """

    PRIOR_COLUMNS = [  # noqa: RUF012
        "project_id",
        "project_title",
        "account_id",
        "user_id",
        "username",
        "biography",
        "member_status",
        "member_role",
        "sampling_inspection_rate",
        "sampling_acceptance_rate",
    ]

    def get_all_project_members(self, project_id: str, include_inactive: bool = False) -> list[ProjectMember]:  # noqa: FBT001, FBT002
        query_params = {}
        if include_inactive:
            query_params.update({"include_inactive_member": ""})

        project_members = self.service.wrapper.get_all_project_members(project_id, query_params=query_params)
        return project_members

    def get_project_members_with_project_id(self, project_id_list: list[str], *, include_inactive: bool = False, parallelism: int | None = None) -> list[ProjectMember]:
        """指定されたプロジェクトのメンバを取得する。

        Args:
            project_id_list: 対象のプロジェクトID
            include_inactive: 脱退済みのメンバも取得するか
            parallelism: 並列度。Noneの場合は逐次処理する

        Returns:
            取得できたプロジェクトメンバ
        """

        def fetch(project_id: str) -> list[ProjectMember]:
            try:
                project, _ = self.service.api.get_project(project_id)
                project_members = self.get_all_project_members(project_id, include_inactive=include_inactive)
            except requests.exceptions.HTTPError:
                logger.warning(f"project_id='{project_id}' のプロジェクトメンバを取得できませんでした。", exc_info=True)
                return []

            project_title = project["title"]
            logger.info(f"{project_title} のプロジェクトメンバを {len(project_members)} 件取得しました。project_id='{project_id}'")
            for member in project_members:
                member["project_title"] = project_title
            return project_members

        if parallelism is None:
            member_lists: Iterable[list[ProjectMember]] = map(fetch, project_id_list)
            return [member for members in member_lists for member in members]

        with ThreadPoolExecutor(max_workers=parallelism) as executor:
            member_lists = executor.map(fetch, project_id_list)
            return [member for members in member_lists for member in members]

    def main(self) -> None:
        args = self.args

        if args.organization is not None:
            projects = self.service.wrapper.get_all_projects_of_organization(args.organization, query_params={"account_id": self.service.api.account_id})
            project_id_list = [project["project_id"] for project in projects]
        else:
            project_id_list = annofabcli.common.cli.get_list_from_args(args.project_id)
        project_members = self.get_project_members_with_project_id(
            project_id_list,
            include_inactive=args.include_inactive,
            parallelism=args.parallelism,
        )

        logger.info(f"プロジェクトメンバ一覧の件数: {len(project_members)}")
        if args.format == OutputFormat.CSV.value:
            df = pandas.DataFrame(project_members) if project_members else pandas.DataFrame(columns=self.PRIOR_COLUMNS)
            columns = get_columns_with_priority(df, prior_columns=self.PRIOR_COLUMNS)
            self.print_csv(df[columns])
        else:
            self.print_according_to_format(project_members)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListProjectMembers(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    list_group = parser.add_mutually_exclusive_group(required=True)
    list_group.add_argument(
        "-p",
        "--project_id",
        type=str,
        nargs="+",
        help="ユーザを表示するプロジェクトのproject_idを指定してください。 ``file://`` を先頭に付けると、一覧が記載されたファイルを指定できます。",
    )
    list_group.add_argument("-org", "--organization", type=str, help="自分が所属する組織配下のすべてのプロジェクトを対象にします。")

    parser.add_argument("--include_inactive", action="store_true", help="脱退しているメンバも出力します。")
    parser.add_argument("--parallelism", type=int, choices=annofabcli.common.cli.PARALLELISM_CHOICES, help="プロジェクトを取得する並列度を指定します。")

    argument_parser.add_format(
        choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON, OutputFormat.USER_ID_LIST],
        default=OutputFormat.CSV,
    )
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list"
    subcommand_help = "複数のプロジェクトのプロジェクトメンバを出力します。"
    description = "複数のプロジェクトのプロジェクトメンバを出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
