import argparse
import logging

import annofabapi
from annofabapi.models import JobStatus, ProjectJobType

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

    def is_job_progress(self, project_id: str, job_type: ProjectJobType) -> bool:
        job_list = self.service.api.get_project_job(project_id, query_params={"type": job_type.value})[0]["list"]
        if len(job_list) > 0:
            if job_list[0]["job_status"] == JobStatus.PROGRESS.value:
                return True

        return False

    def wait_job(self, project_id: str, job_type: ProjectJobType, wait_options: WaitOptions):
        if not self.is_job_progress(project_id, job_type):
            logger.info(f"job_type='{job_type.value}'の実行中のジョブはないので、終了します。")
            return

        MAX_WAIT_MINUTUE = wait_options.max_tries * wait_options.interval / 60
        logger.info(f"ダウンロード対象の最新化処理が完了するまで、最大{MAX_WAIT_MINUTUE}分間待ちます。")
        result = self.service.wrapper.wait_for_completion(
            project_id,
            job_type=job_type,
            job_access_interval=wait_options.interval,
            max_job_access=wait_options.max_tries,
        )
        if result:
            logger.info(f"job_type='{job_type.value}'のジョブが終了しました。")
        else:
            logger.info(f"job_type='{job_type.value}'のジョブが失敗したか、または {MAX_WAIT_MINUTUE} 分待っても処理が終了しませんでした。")


class WaitJob(AbstractCommandLineInterface):
    def main(self):
        args = self.args
        project_id = args.project_id
        job_type = ProjectJobType(args.job_type)

        DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)
        wait_options = get_wait_options_from_args(get_json_from_args(args.wait_options), DEFAULT_WAIT_OPTIONS)

        main_obj = WaitJobMain(self.service)
        main_obj.wait_job(project_id, job_type=job_type, wait_options=wait_options)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    WaitJob(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    job_choices = [e.value for e in ProjectJobType]
    parser.add_argument("--job_type", type=str, choices=job_choices, required=True, help="ジョブタイプを指定します。")

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


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "wait"
    subcommand_help = "ジョブの終了を待ちます。"
    description = "ジョブの終了を待ちます。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
