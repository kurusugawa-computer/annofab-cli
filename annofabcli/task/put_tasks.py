from __future__ import annotations

import argparse
import logging
import multiprocessing
import tempfile
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import annofabapi
import pandas
from annofabapi.models import JobStatus, ProjectJobType, ProjectMemberRole

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_json_from_args,
)
from annofabcli.common.dataclasses import WaitOptions

logger = logging.getLogger(__name__)


TASK_THRESHOLD_FOR_JSON = 230
"""
タスク作成処理のwebapiに put_taskを使うか initiate_generation_task を使うかのしきい値。
作成するタスク数が指定した値以下の場合は、put_task webapiを使います。
しきい値は、実際にwebapiの処理時間を計測して決めました。詳細は以下を参照してください。
https://github.com/kurusugawa-computer/annofab-cli/pull/738#issuecomment-1077013844
"""

TaskInputRelation = Dict[str, List[str]]
"""task_idとinput_data_idの構造を表現する型"""


class ApiWithCreatingTask(Enum):
    """タスク作成に使われるWebAPI"""

    PUT_TASK = "put_task"
    INITIATE_TASKS_GENERATION = "initiate_tasks_generation"


def get_task_relation_dict(csv_file: Path) -> TaskInputRelation:
    """CSVから、keyがtask_id, valueがinput_data_idのlistのdictを生成します。"""
    df = pandas.read_csv(str(csv_file), header=None, usecols=(0, 1), names=("task_id", "input_data_id"))
    result: TaskInputRelation = defaultdict(list)
    for task_id, input_data_id in zip(df["task_id"], df["input_data_id"]):
        result[task_id].append(input_data_id)
    return result


def create_task_relation_csv(task_relation_dict: TaskInputRelation, csv_file: Path):
    """task_idとinput_data_idの関係を持つdictから、``initiate_tasks_generation`` APIに渡すCSVを生成します。


    Args:
        task_relation_dict: keyがtask_id, valueがinput_data_idのlistのdict
        csv_file: 出力先

    """
    tmp_list = []
    for task_id, input_data_id_list in task_relation_dict.items():
        for input_data_id in input_data_id_list:
            tmp_list.append({"task_id": task_id, "input_data_id": input_data_id})
    df = pandas.DataFrame(tmp_list)

    # webapiの都合上、2列目は空文字でないといけない
    df["empty"] = ""
    df = df[["task_id", "empty", "input_data_id"]]

    csv_file.parent.mkdir(exist_ok=True, parents=True)
    df.to_csv(str(csv_file), index=False, header=None)


class PuttingTaskMain:
    def __init__(
        self,
        service: annofabapi.Resource,
        project_id: str,
        *,
        parallelism: Optional[int],
        should_wait: bool = False,
    ):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.project_id = project_id
        self.parallelism = parallelism
        self.should_wait = should_wait

    def put_task(self, task_id: str, input_data_id_list: list[str]) -> bool:
        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is not None:
            logger.warning(f"タスク'{task_id}'はすでに存在するため、登録をスキップします。")
            return False

        # タスクを上書きしない理由：タスクを上書きすると、タスクに紐づくアノテーションまで消えてしまう恐れがあるため
        self.service.api.put_task(self.project_id, task_id, request_body={"input_data_id_list": input_data_id_list})
        logger.debug(f"タスク'{task_id}'を登録しました。")
        return True

    def put_task_wrapper(self, tpl: tuple[str, list[str]]) -> bool:
        task_id, input_data_id_list = tpl
        try:
            return self.put_task(task_id, input_data_id_list)
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"タスク'{task_id}'の登録に失敗しました。", exc_info=True)
            return False

    def put_task_list(self, task_relation_dict: TaskInputRelation):
        logger.debug(f"'put_task' WebAPIを用いてタスクを生成します。")
        success_count = 0
        if self.parallelism is None:
            for task_id, input_data_id_list in task_relation_dict.items():
                try:
                    result = self.put_task(task_id, input_data_id_list)
                    if result:
                        success_count += 1
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"タスク'{task_id}'の登録に失敗しました。", exc_info=True)

        else:
            with multiprocessing.Pool(self.parallelism) as p:
                results = p.map(self.put_task_wrapper, task_relation_dict.items())
                success_count = len([e for e in results if e])

        logger.info(f"{success_count} / {len(task_relation_dict)} 件のタスクを登録しました。")

    def put_task_from_csv_file(self, csv_file: Path) -> None:
        """
        CSVファイルからタスクを登録する。

        Args:
            project_id:
            csv_file: タスク登録に関する情報が記載されたCSV
        """
        logger.debug(f"'initiate_tasks_generation' WebAPIを用いてタスクを生成します。")
        content = self.service.wrapper.initiate_tasks_generation_by_csv(self.project_id, csvfile_path=str(csv_file))
        job = content["job"]
        logger.info(
            f"AnnoFab上でタスク作成処理が開始されました。 :: csv_file='{csv_file}', job_type='{job['job_type']}', job_id='{job['job_id']}'"  # noqa: E501
        )
        if self.should_wait:
            self.wait_for_completion(job["job_id"])
        else:
            logger.info(
                f"以下のコマンドを実行すれば、タスク登録ジョブが終了するまで待ちます。 :: `annofabcli job wait --project_id {self.project_id} --job_type {job['job_type']} --job_id {job['job_id']}`"  # noqa: E501
            )

    def generate_task(
        self,
        api: Optional[ApiWithCreatingTask],
        task_relation_dict: TaskInputRelation,
    ) -> None:
        """
        put_task または initiate_tasks_generation WebAPIを使って、タスクを生成します。

        Args:
            task_relation_dict: task_idとinput_data_id_listのdict
            csv_file: task_relation_dictに対応するCSVファイルです。Noneの場合は生成します。
            parallelism: `put_task` APIでタスクを生成する際に、指定した値だけ並列で処理します。
        """
        logger.info(f"{len(task_relation_dict)}件のタスクを生成します。")
        if api is None:
            if len(task_relation_dict) > TASK_THRESHOLD_FOR_JSON:
                with tempfile.NamedTemporaryFile() as f:
                    create_task_relation_csv(task_relation_dict, Path(f.name))
                    self.put_task_from_csv_file(Path(f.name))
            else:
                self.put_task_list(task_relation_dict)

        if api == ApiWithCreatingTask.PUT_TASK:
            self.put_task_list(task_relation_dict)

        elif api == ApiWithCreatingTask.INITIATE_TASKS_GENERATION:
            with tempfile.NamedTemporaryFile() as f:
                create_task_relation_csv(task_relation_dict, Path(f.name))
                self.put_task_from_csv_file(Path(f.name))

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


class PutTask(AbstractCommandLineInterface):
    def main(self):
        args = self.args
        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        api_with_creating_task = ApiWithCreatingTask(args.api) if args.api is not None else None
        main_obj = PuttingTaskMain(
            self.service,
            project_id=args.project_id,
            parallelism=args.parallelism,
            should_wait=args.wait,
        )

        if args.csv is not None:
            csv_file = args.csv
            task_relation_dict = get_task_relation_dict(csv_file)
            main_obj.generate_task(api_with_creating_task, task_relation_dict)

        elif args.json is not None:
            # CSVファイルに変換する
            task_relation_dict = get_json_from_args(args.json)
            main_obj.generate_task(api_with_creating_task, task_relation_dict)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PutTask(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    file_group = parser.add_mutually_exclusive_group(required=True)
    file_group.add_argument(
        "--csv",
        type=Path,
        help=(
            "タスクに割り当てる入力データが記載されたCSVファイルのパスを指定してください。"
            "CSVのフォーマットは、以下の通りです。"
            "タスク作成画面でアップロードするCSVと同じフォーマットです。\n"
            "\n"
            " * ヘッダ行なし, カンマ区切り\n"
            " * 1列目: task_id\n"
            " * 2列目: input_data_id\n"
        ),
    )

    JSON_SAMPLE = '{"task1":["input1","input2"]}'
    file_group.add_argument(
        "--json",
        type=str,
        help=(
            "タスクに割り当てる入力データをJSON形式で指定してください。"
            "keyがtask_id, valueがinput_data_idのlistです。\n"
            f"(ex) ``{JSON_SAMPLE}`` \n"
            "``file://`` を先頭に付けるとjsonファイルを指定できます。"
        ),
    )

    parser.add_argument(
        "--api",
        type=str,
        choices=[e.value for e in ApiWithCreatingTask],
        help=f"タスク作成に使うWebAPIを指定できます。 ``--csv`` or ``--json`` を指定したときのみ有効なオプションです。\n"
        "未指定の場合は、作成するタスク数に応じて、適切なWebAPIを選択します。\n",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        help="並列度。指定しない場合は、逐次的に処理します。``put_task`` WebAPIを使うときのみ有効なオプションです。",
    )

    parser.add_argument(
        "--wait", action="store_true", help="タスク登録ジョブが終了するまで待ちます。``initiate_tasks_generation`` WebAPIを使うときのみ有効なオプションです。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "put"
    subcommand_help = "タスクを作成します。"
    description = "タスクを作成します。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
