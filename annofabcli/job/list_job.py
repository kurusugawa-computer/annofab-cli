import argparse
import copy
import logging
from typing import Any, Dict, List, Optional

from annofabapi.models import JobInfo, JobType

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument

logger = logging.getLogger(__name__)


class ListJob(AbstractCommandLineInterface):
    """
    ジョブ一覧を表示する。
    """

    def get_job_list(
        self, project_id: str, job_type: JobType, job_query: Optional[Dict[str, Any]] = None
    ) -> List[JobInfo]:
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

    def print_job_list(self, project_id: str, job_type: JobType, job_query: Optional[Dict[str, Any]] = None):
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

    def main(self):
        args = self.args
        # job_query = annofabcli.common.cli.get_json_from_args(args.job_query)
        job_type = JobType(args.job_type)
        self.print_job_list(args.project_id, job_type=job_type, job_query=None)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListJob(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    job_choices = [e.value for e in JobType]
    argument_parser.add_project_id()

    parser.add_argument("--job_type", type=str, choices=job_choices, required=True, help="ジョブタイプを指定します。")

    # クエリがうまく動かないので、コメントアウトする
    # parser.add_argument(
    #     '--job_query', type=str, help='ジョブの検索クエリをJSON形式で指定します。指定しない場合は、最新のジョブを1個取得します。 '
    #     '`file://`を先頭に付けると、JSON形式のファイルを指定できます。'
    #     '`limit` キーを指定できます。')

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON], default=FormatArgument.CSV
    )
    argument_parser.add_output()
    argument_parser.add_csv_format()

    argument_parser.add_query()
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list"
    subcommand_help = "ジョブ一覧を出力します。"
    description = "ジョブ一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
