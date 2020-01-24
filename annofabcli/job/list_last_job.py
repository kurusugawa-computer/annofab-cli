import argparse
import logging
import sys
from typing import Any, Dict, List, Optional

from annofabapi.models import JobInfo, JobType, Project

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument

logger = logging.getLogger(__name__)


class ListLastJob(AbstractCommandLineInterface):
    """
    ジョブ一覧を表示する。
    """

    def get_last_job(self, project_id: str, job_type: JobType) -> Optional[JobInfo]:
        """
        最新のジョブを取得する。ジョブが存在しない場合はNoneを返す。

        """
        query_params = {"type": job_type.value}
        content, _ = self.service.api.get_project_job(project_id, query_params)
        job_list = content["list"]
        if len(job_list) == 0:
            logger.debug(f"project_id={project_id}にjob_type={job_type.value}のジョブは存在しませんでした。")
            return None
        else:
            return job_list[-1]

    def get_project_info(self, project_id: str, project: Project, add_details: bool = False) -> Dict[str, Any]:
        """
        出力対象であるプロジェクトに関する情報を取得する。

        Args:
            project_id:
            project: プロジェクト情報
            add_details:

        Returns:
            プロジェクト情報

        """

        project_info = {"project_id": project["project_id"], "project_title": project["title"]}

        if add_details:
            project_info["last_tasks_updated_datetime"] = project["summary"]["last_tasks_updated_datetime"]

            annotation_specs_history = self.service.api.get_annotation_specs_histories(project_id)[0]
            project_info["last_annotation_specs_updated_datetime"] = annotation_specs_history[-1]["updated_datetime"]

        return project_info

    @annofabcli.utils.allow_404_error
    def get_project(self, project_id: str) -> Project:
        project, _ = self.service.api.get_project(project_id)
        return project

    def get_last_job_list(
        self, project_id_list: List[str], job_type: JobType, add_details: bool = False
    ) -> List[JobInfo]:
        job_list = []
        for project_id in project_id_list:
            project = self.get_project(project_id)

            if project is None:
                logger.warning(f"project_id='{project_id}' のプロジェクトは存在しませんでした。")
                continue

            project_info = self.get_project_info(project_id=project_id, add_details=add_details, project=project)
            job = self.get_last_job(project_id, job_type)
            if job is not None:
                job_list.append({**project_info, **job})
            else:
                job_list.append(project_info)

        return job_list

    def print_job_list(self, project_id_list: List[str], job_type: JobType, add_details: bool = False) -> None:
        """
        ジョブ一覧を出力する

        Args:
            project_id: 対象のproject_id
            job_type: ジョブタイプ
        """

        job_list = self.get_last_job_list(project_id_list, job_type=job_type, add_details=add_details)
        logger.info(f"{len(job_list)} 個のプロジェクトの, job_type={job_type.value} の最新ジョブを出力します。")
        self.print_according_to_format(job_list)

    def get_project_id_list(self, organization_name: str) -> List[str]:
        """
        進行中で自分自身が所属する project_id を取得する

        Args:
            organization_name:

        Returns:

        """
        my_account, _ = self.service.api.get_my_account()
        query_params = {"status": "active", "account_id": my_account["account_id"]}
        project_list = self.service.wrapper.get_all_projects_of_organization(
            organization_name, query_params=query_params
        )
        return [e["project_id"] for e in project_list]

    def main(self):
        args = self.args
        job_type = JobType(args.job_type)

        if args.organization is not None:
            project_id_list = self.get_project_id_list(args.organization)

        elif args.project_id is not None:
            project_id_list = annofabcli.common.cli.get_list_from_args(args.project_id)

        else:
            print("引数に`--project_id` または `--organization` を指定してください。", file=sys.stderr)
            return

        self.print_job_list(project_id_list, job_type=job_type, add_details=args.add_details)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListLastJob(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    job_choices = [e.value for e in JobType]
    parser.add_argument("--job_type", type=str, choices=job_choices, required=True, help="ジョブタイプを指定します。")

    list_group = parser.add_mutually_exclusive_group(required=True)
    list_group.add_argument(
        "-p",
        "--project_id",
        type=str,
        nargs="+",
        help="対象のプロジェクトのproject_idを指定してください。`file://`を先頭に付けると、一覧が記載されたファイルを指定できます。",
    )

    list_group.add_argument("-org", "--organization", type=str, help="組織配下のすべてのプロジェクトのジョブを出力したい場合は、組織名を指定してください。")

    parser.add_argument(
        "--add_details",
        action="store_true",
        help="プロジェクトに関する詳細情報を表示します" "（`task_last_updated_datetime, annotation_specs_last_updated_datetime`）",
    )

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON], default=FormatArgument.CSV
    )
    argument_parser.add_output()
    argument_parser.add_csv_format()

    argument_parser.add_query()
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_last"
    subcommand_help = "複数のプロジェクトに対して、最新のジョブを出力します。"
    description = "複数のプロジェクトに対して、最新のジョブを出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
