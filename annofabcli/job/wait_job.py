import argparse
import logging
from typing import Optional

import annofabapi
from annofabapi.models import ProjectJobType

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    get_wait_options_from_args,
)
from annofabcli.common.dataclasses import WaitOptions

logger = logging.getLogger(__name__)


class WaitJobMain:
    def __init__(self, service: annofabapi.Resource):
        self.service = service
        self.facade = AnnofabApiFacade(service)

    def wait_job(
        self, project_id: str, job_type: ProjectJobType, wait_options: WaitOptions, job_id: Optional[str] = None
    ):
        MAX_WAIT_MINUTE = wait_options.max_tries * wait_options.interval / 60
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
            return


class WaitJob(AbstractCommandLineInterface):
    def main(self):
        args = self.args
        project_id = args.project_id
        job_type = ProjectJobType(args.job_type)

        DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)
        wait_options = get_wait_options_from_args(get_json_from_args(args.wait_options), DEFAULT_WAIT_OPTIONS)

        main_obj = WaitJobMain(self.service)
        main_obj.wait_job(project_id, job_type=job_type, job_id=args.job_id, wait_options=wait_options)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    WaitJob(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    job_choices = [e.value for e in ProjectJobType]
    parser.add_argument("--job_type", type=str, choices=job_choices, required=True, help="ジョブタイプを指定します。")

    parser.add_argument("--job_id", type=str, help="ジョブIDを指定します。未指定の場合は、最新のジョブが終了するまで待ちます。")

    parser.add_argument(
        "--wait_options",
        type=str,
        help="ジョブの終了を待つときのオプションをJSON形式で指定してください。"
        "`file://`を先頭に付けるとjsonファイルを指定できます。"
        'デフォルとは`{"interval":60, "max_tries":360}` です。'
        "`interval`:ジョブが完了したかを問い合わせる間隔[秒], "
        "`max_tires`:ジョブが完了したかの問い合わせを最大何回行うか。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "wait"
    subcommand_help = "ジョブの終了を待ちます。"
    description = "ジョブの終了を待ちます。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
