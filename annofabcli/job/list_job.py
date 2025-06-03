import argparse
import copy
import logging
from typing import Any, Optional

from annofabapi.models import ProjectJobInfo, ProjectJobType

import annofabcli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class ListJob(CommandLine):
    """
    ジョブ一覧を表示する。
    """

    def get_job_list(self, project_id: str, job_type: ProjectJobType, job_query: Optional[dict[str, Any]] = None) -> list[ProjectJobInfo]:
        """
        ジョブ一覧を取得する。
        """

        if job_query is not None:
            query_params = copy.deepcopy(job_query)
        else:
            query_params = {}

        query_params["type"] = job_type.value

        logger.debug(f"query_params: {query_params}")
        job_list = self.service.wrapper.get_all_project_job(project_id, query_params=query_params)
        return job_list

    def print_job_list(self, project_id: str, job_type: ProjectJobType, job_query: Optional[dict[str, Any]] = None) -> None:
        """
        ジョブ一覧を出力する

        Args:
            project_id: 対象のproject_id
            job_type: ジョブタイプ
            job_query:

        """

        super().validate_project(project_id, project_member_roles=None)

        job_list = self.get_job_list(project_id, job_type=job_type, job_query=job_query)
        logger.info(f"ジョブ一覧の件数: {len(job_list)}")
        self.print_according_to_format(job_list)

    def main(self) -> None:
        args = self.args
        job_type = ProjectJobType(args.job_type)
        self.print_job_list(args.project_id, job_type=job_type, job_query=None)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListJob(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    job_choices = [e.value for e in ProjectJobType]
    argument_parser.add_project_id()

    parser.add_argument(
        "--job_type",
        type=str,
        choices=job_choices,
        required=True,
        help="ジョブタイプを指定します。指定できる値については https://annofab-cli.readthedocs.io/ja/latest/user_guide/command_line_options.html#job-type を参照してください。",
    )

    argument_parser.add_format(choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON], default=FormatArgument.CSV)
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list"
    subcommand_help = "ジョブ一覧を出力します。"
    description = "ジョブ一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
