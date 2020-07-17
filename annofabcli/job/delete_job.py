import argparse
import logging
from typing import List

import annofabapi
from annofabapi.models import JobType, ProjectMemberRole

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)

logger = logging.getLogger(__name__)


class DeleteJobMain:
    def __init__(self, service: annofabapi.Resource):
        self.service = service
        self.facade = AnnofabApiFacade(service)

    def delete_job_list(self, project_id: str, job_type: JobType, job_id_list: List[str]):
        for job_id in job_id_list:
            logger.debug(f"job_id={job_id} のジョブを削除します。")
            try:
                self.service.api.delete_project_job(project_id, job_type.value, job_id)
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(e)


class DeleteJob(AbstractCommandLineInterface):
    def main(self):
        args = self.args
        project_id = args.project_id
        super().validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER])

        job_type = JobType(args.job_type)
        job_id_list = get_list_from_args(args.job_id)

        main_obj = DeleteJobMain(self.service)
        main_obj.delete_job_list(args.project_id, job_type=job_type, job_id_list=job_id_list)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteJob(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    job_choices = [e.value for e in JobType]
    argument_parser.add_project_id()

    parser.add_argument("--job_type", type=str, choices=job_choices, required=True, help="ジョブタイプを指定します。")
    parser.add_argument(
        "--job_id",
        type=str,
        nargs="+",
        required=True,
        help="削除するジョブのjob_idを指定します。" + "`file://`を先頭に付けると、job_idの一覧が記載されたファイルを指定できます。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "delete"
    subcommand_help = "ジョブを削除する。"
    description = "ジョブを削除する。"
    epilog = "オーナロールで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
