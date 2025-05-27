import argparse
import csv
import logging
import sys
from pathlib import Path
from typing import Optional

import annofabapi
import requests
from annofabapi.models import Project, ProjectMemberRole

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class ChangeProjectTitleMain:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)

    def change_title_for_project(self, project_id: str, new_title: str) -> bool:
        project: Project | None = self.service.wrapper.get_project_or_none(project_id)
        if project is None:
            logger.warning(f"project_id={project_id} のプロジェクトは存在しないので、スキップします。")
            return False

        if not self.facade.contains_any_project_member_role(project_id, [ProjectMemberRole.OWNER]):
            logger.warning(f"project_id={project_id}: オーナロールでないため、プロジェクトのタイトルを変更できません。project_title={project['title']}")
            return False

        logger.debug(f"{project['title']} のタイトルを {new_title} に変更します。project_id={project_id}")
        project["title"] = new_title
        project["status"] = project["project_status"]
        project["last_updated_datetime"] = project["updated_datetime"]
        self.service.api.put_project(project_id, request_body=project)
        return True

    def change_title_for_project_list(self, project_id_list: list[str], new_title: str) -> None:
        """
        複数のプロジェクトに対して、プロジェクトのタイトルを変更する。

        Args:
            project_id_list: 対象のプロジェクトIDリスト
            new_title: 変更後のタイトル

        Returns:

        """
        logger.info(f"{len(project_id_list)} 件のプロジェクトのタイトルを {new_title} に変更します。")
        success_count = 0
        for project_id in project_id_list:
            try:
                result = self.change_title_for_project(project_id, new_title=new_title)
                if result:
                    success_count += 1

            except requests.HTTPError as e:
                if e.response.status_code == requests.codes.conflict:
                    logger.warning(e)
                else:
                    raise

        logger.info(f"{success_count} 件のプロジェクトのタイトルを {new_title} に変更しました。")

    def change_title_from_csv(self, csv_path: Path) -> None:
        """
        CSVファイルを読み込み、複数のプロジェクトのタイトルを変更する。

        Args:
            csv_path: project_id, title カラムを持つCSVファイルのパス

        Returns:
            None
        """
        with csv_path.open(mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            if "project_id" not in reader.fieldnames or "new_title" not in reader.fieldnames:
                raise ValueError("CSVファイルに 'project_id' または 'new_title' カラムが存在しません。")

            project_id_list = []
            title_map = {}
            for row in reader:
                project_id = row["project_id"].strip()
                new_title = row["new_title"].strip()
                project_id_list.append(project_id)
                title_map[project_id] = new_title

            for project_id in project_id_list:
                new_title = title_map[project_id]
                self.change_title_for_project(project_id, new_title=new_title)


class ChangeProjectTitle(CommandLine):
    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        main_obj = ChangeProjectTitleMain(self.service)

        if args.csv_path:
            # CSVファイルからタイトルを変更
            csv_path = Path(args.csv_path)
            main_obj.change_title_from_csv(csv_path=csv_path)
        else:
            # プロジェクトIDとタイトルを直接指定
            main_obj.change_title_for_project(args.project_id, new_title=args.new_title)

    def validate(self, args: argparse.Namespace) -> None:
        if args.csv_path and (args.project_id or args.new_title):
            raise ValueError("--csv_path オプションを指定した場合、--project_id または --new_title を同時に指定することはできません。")

        if not args.csv_path and (not args.project_id or not args.new_title):
            raise ValueError("--csv_path を指定しない場合、--project_id と --new_title の両方を指定する必要があります。")


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeProjectTitle(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-p",
        "--project_id",
        type=str,
        help="対象プロジェクトのproject_idを指定します。",
    )

    parser.add_argument(
        "--new_title",
        type=str,
        help="変更後のプロジェクトタイトルを指定してください。",
    )

    parser.add_argument(
        "--csv_path",
        type=str,
        help="project_id, new_title カラムを持つCSVファイルのパスを指定してください。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "change_title"
    subcommand_help = "プロジェクトのタイトルを変更します。"
    description = "プロジェクトのタイトルを変更します。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
