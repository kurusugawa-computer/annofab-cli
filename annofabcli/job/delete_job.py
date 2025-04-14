import argparse
import logging
from typing import Optional

import annofabapi
from annofabapi.models import ProjectJobType, ProjectMemberRole

import annofabcli
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class DeleteJobMain:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)

    def delete_job_list(self, project_id: str, job_type: ProjectJobType, job_id_list: list[str]):  # noqa: ANN201
        job_list = self.service.wrapper.get_all_project_job(project_id, query_params={"type": job_type.value})
        exists_job_id_set = {e["job_id"] for e in job_list}

        count = 0
        for job_id in job_id_list:
            if job_id not in exists_job_id_set:
                logger.debug(f"job_id='{job_id}' のジョブは存在しなかったのでスキップします。")
                continue
            try:
                self.service.api.delete_project_job(project_id, job_type.value, job_id)
                logger.debug(f"job_type={job_type.value}, job_id='{job_id}' のジョブを削除しました。")
                count += 1
            except Exception:  # pylint: disable=broad-except
                logger.warning(f"job_type={job_type.value}, job_id='{job_id}' のジョブの削除に失敗しました。", exc_info=True)
        logger.info(f"{count} / {len(job_id_list)} 件のジョブを削除しました。")


class DeleteJob(CommandLine):
    def main(self) -> None:
        args = self.args
        project_id = args.project_id
        super().validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER])

        job_type = ProjectJobType(args.job_type)
        job_id_list = get_list_from_args(args.job_id)

        main_obj = DeleteJobMain(self.service)
        main_obj.delete_job_list(args.project_id, job_type=job_type, job_id_list=job_id_list)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteJob(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    job_choices = [e.value for e in ProjectJobType]
    argument_parser.add_project_id()

    parser.add_argument("--job_type", type=str, choices=job_choices, required=True, help="ジョブタイプを指定します。")
    parser.add_argument(
        "--job_id",
        type=str,
        nargs="+",
        required=True,
        help="削除するジョブのjob_idを指定します。" + " ``file://`` を先頭に付けると、job_idの一覧が記載されたファイルを指定できます。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "delete"
    subcommand_help = "ジョブを削除する。"
    description = "ジョブを削除する。"
    epilog = "オーナロールで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
