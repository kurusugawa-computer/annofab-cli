from __future__ import annotations

import argparse
import logging
from enum import Enum
from typing import Optional

import annofabapi
from annofabapi.models import JobStatus, ProjectJobType, ProjectMemberRole

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.dataclasses import WaitOptions

logger = logging.getLogger(__name__)


class InputDataOrder(Enum):
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    RANDOM = "random"


class PuttingTaskByCountMain:
    def __init__(
        self,
        service: annofabapi.Resource,
        project_id: str,
    ):
        self.service = service
        self.project_id = project_id

    def generate_task(
        self,
        task_id_prefix: str,
        input_data_count: int,
        *,
        input_data_order: InputDataOrder,
        allow_duplicate_input_data: bool,
        should_wait: bool = False,
    ) -> None:
        """
        タスク生成のジョブを登録します。
        """
        project, _ = self.service.api.get_project(self.project_id)

        request_body = {
            "task_generate_rule": {
                "task_id_prefix": task_id_prefix,
                "allow_duplicate_input_data": allow_duplicate_input_data,
                "input_data_count": input_data_count,
                "input_data_order": input_data_order.value,
                "_type": "ByCount",
            },
            "project_last_updated_datetime": project["updated_datetime"],
        }
        content, _ = self.service.api.initiate_tasks_generation(self.project_id, request_body=request_body)
        job = content["job"]
        logger.info(
            f"AnnoFab上でタスク作成処理が開始されました。 :: task_id_prefix='{task_id_prefix}', input_data_count='input_data_count'"
        )
        if should_wait:
            self.wait_for_completion(job["job_id"])
        else:
            logger.info(
                f"以下のコマンドを実行すれば、タスク登録ジョブが終了するまで待ちます。 :: `annofabcli job wait --project_id {self.project_id} --job_type {job['job_type']} --job_id {job['job_id']}`"  # noqa: E501
            )

    def wait_for_completion(self, job_id: str) -> None:
        """
        タスク登録ジョブが終了するまで待ちます。
        """
        wait_options = WaitOptions(interval=30, max_tries=720)
        max_wait_minute = wait_options.max_tries * wait_options.interval / 60
        logger.info(f"job_id='{job_id}' :: 最大{max_wait_minute}分間、タスク登録のジョブが終了するまで待ちます。")

        result = self.service.wrapper.wait_until_job_finished(
            self.project_id,
            job_type=ProjectJobType.GEN_TASKS,
            job_id=job_id,
            job_access_interval=wait_options.interval,
            max_job_access=wait_options.max_tries,
        )
        if result is None:
            logger.error(f"job_id='{job_id}' :: タスク登録のジョブが存在しません。")
            return
        if result == JobStatus.SUCCEEDED:
            logger.info(f"job_id='{job_id}' :: タスク登録のジョブが成功しました。")
        elif result == JobStatus.FAILED:
            logger.error(f"job_id='{job_id}' :: タスク登録のジョブが失敗しました。")
        elif result == JobStatus.PROGRESS:
            logger.warning(f"job_id='{job_id}' :: {max_wait_minute}分間待ちましたが、タスク登録のジョブが終了しませんでした。")


class PutTaskByCount(AbstractCommandLineInterface):
    def main(self):
        args = self.args
        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        main_obj = PuttingTaskByCountMain(
            self.service,
            project_id=args.project_id,
        )

        main_obj.generate_task(
            args.task_id_prefix,
            args.input_data_count,
            input_data_order=InputDataOrder(args.input_data_order),
            allow_duplicate_input_data=args.allow_duplicate_input_data,
            should_wait=args.wait,
        )


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PutTaskByCount(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument("--task_id_prefix", type=str, required=True, help="生成するタスクIDのプレフィックス")

    parser.add_argument("--input_data_count", type=int, required=True, help="タスクに割り当てる入力データの個数。動画プロジェクトの場合は1を指定してください。")

    parser.add_argument(
        "--allow_duplicate_input_data", action="store_true", help="指定すると、既にタスクに使われている入力データを使ってタスクを作成します。"
    )

    parser.add_argument(
        "--input_data_order",
        type=str,
        choices=[e.value for e in InputDataOrder],
        default=InputDataOrder.NAME_ASC.value,
        help="タスクに割り当てる入力データの順序",
    )

    parser.add_argument("--wait", action="store_true", help="タスク登録ジョブが終了するまで待ちます。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "put_by_count"
    subcommand_help = "タスクに割り当てる入力データの個数を指定して、タスクを作成します。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
