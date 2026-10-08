import argparse
import logging

import annofabapi
from annofabapi.models import ProjectJobType

import annofabcli.common.cli
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.download import DEFAULT_WAIT_OPTIONS
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class WaitJobMain:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)

    def wait_job(self, project_id: str, job_type: ProjectJobType, job_id: str | None = None) -> None:
        """共通の待機設定でジョブの終了を待つ。

        Args:
            project_id: 対象のプロジェクトID。
            job_type: ジョブの種類。
            job_id: 対象のジョブID。未指定の場合は最新のジョブを対象にする。

        Returns:
            None
        """
        wait_options = DEFAULT_WAIT_OPTIONS
        MAX_WAIT_MINUTE = wait_options.max_tries * wait_options.interval / 60  # noqa: N806
        logger.info(f"job_type='{job_type.value}', job_id='{job_id}' :: ジョブが完了するまで、最大{MAX_WAIT_MINUTE}分間待ちます。")
        result = self.service.wrapper.wait_until_job_finished(
            project_id,
            job_type=job_type,
            job_id=job_id,
            job_access_interval=wait_options.interval,
            max_job_access=wait_options.max_tries,
        )
        if result is None:
            logger.warning(f"job_type='{job_type.value}', job_id='{job_id}' :: ジョブは存在しませんでした。")


class WaitJob(CommandLine):
    def main(self) -> None:
        args = self.args
        project_id = args.project_id
        job_type = ProjectJobType(args.job_type)

        main_obj = WaitJobMain(self.service)
        main_obj.wait_job(project_id, job_type=job_type, job_id=args.job_id)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    WaitJob(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    job_choices = [e.value for e in ProjectJobType]
    parser.add_argument("--job_type", type=str, choices=job_choices, required=True, help="ジョブタイプを指定します。")

    parser.add_argument("--job_id", type=str, help="ジョブIDを指定します。未指定の場合は、最新のジョブが終了するまで待ちます。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "wait"
    subcommand_help = "ジョブの終了を待ちます。"
    description = "ジョブの終了を待ちます。60秒間隔で完了を確認し、最大6時間待ちます。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
