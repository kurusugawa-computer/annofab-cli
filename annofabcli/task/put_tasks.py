from __future__ import annotations

import argparse
import copy
import json
import logging
import multiprocessing
import tempfile
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import annofabapi
import pandas
from annofabapi.models import ProjectJobType, ProjectMemberRole

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    AbstractCommandLineWithConfirmInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    get_wait_options_from_args,
)
from annofabcli.common.dataclasses import WaitOptions

logger = logging.getLogger(__name__)

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)

TASK_THRESHOLD_FOR_JSON = 230

TaskInputRelation = Dict[str, List[str]]
"""task_idとinput_data_idの構造を表現する型"""


class ApiWithCreatingTask(Enum):
    """タスク作成に使われるWebAPI"""

    PUT_TASK = "put_task"
    INITIATE_TASKS_GENERATION = "initiate_tasks_generation"


def get_task_relation_dict(csv_file: Path) -> TaskInputRelation:
    """CSVから、keyがtask_id, valueがinput_data_idのlistのdictを生成します。"""
    df = pandas.read_csv(str(csv_file), header=None, usecols=(0, 2), names=("task_id", "input_data_id"))
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
    df["input_data_name"] = ""
    df = df[["task_id", "input_data_name", "input_data_id"]]

    csv_file.parent.mkdir(exist_ok=True, parents=True)
    df.to_csv(str(csv_file), index=False, header=None)


class PuttingTaskMain(AbstractCommandLineWithConfirmInterface):
    def __init__(self, service: annofabapi.Resource, project_id: str, all_yes: bool = False):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.project_id = project_id

        AbstractCommandLineWithConfirmInterface.__init__(self, all_yes)

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

    def put_task_list(self, task_relation_dict: TaskInputRelation, parallelism: Optional[int]):
        success_count = 0
        if parallelism is None:
            for task_id, input_data_id_list in task_relation_dict.items():
                try:
                    result = self.put_task(task_id, input_data_id_list)
                    if result:
                        success_count += 1
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"タスク'{task_id}'の登録に失敗しました。", exc_info=True)

        else:
            with multiprocessing.Pool(parallelism) as p:
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
        self.service.wrapper.initiate_tasks_generation_by_csv(self.project_id, csvfile_path=str(csv_file))
        logger.info(f"AnnoFab上でタスク作成処理が開始されました。 :: csv_file='{csv_file}'")

    def generate_task(
        self,
        api: Optional[ApiWithCreatingTask],
        task_relation_dict: TaskInputRelation,
        csv_file: Optional[Path],
        parallelism: Optional[int],
    ) -> None:
        """
        put_task または initiate_tasks_generation WebAPIを使って、タスクを生成します。

        Args:
            task_relation_dict: task_idとinput_data_id_listのdict
            csv_file: task_relation_dictに対応するCSVファイルです。Noneの場合は生成します。
            parallelism: `put_task` APIでタスクを生成する際に、指定した値だけ並列で処理します。
        """
        if api is None:
            if len(task_relation_dict) > TASK_THRESHOLD_FOR_JSON:
                if csv_file is not None:
                    self.put_task_from_csv_file(csv_file)
                else:
                    with tempfile.NamedTemporaryFile() as f:
                        create_task_relation_csv(task_relation_dict, Path(f.name))
                        self.put_task_from_csv_file(Path(f.name))
            else:
                self.put_task_list(task_relation_dict, parallelism)

        if api == ApiWithCreatingTask.PUT_TASK:
            self.put_task_list(task_relation_dict, parallelism)

        elif api == ApiWithCreatingTask.INITIATE_TASKS_GENERATION:
            if csv_file is not None:
                self.put_task_from_csv_file(csv_file)
            else:
                with tempfile.NamedTemporaryFile() as f:
                    create_task_relation_csv(task_relation_dict, Path(f.name))
                    self.put_task_from_csv_file(Path(f.name))


class PutTask(AbstractCommandLineInterface):
    """
    CSVからタスクを登録する。
    """

    DEFAULT_BY_COUNT = {"allow_duplicate_input_data": False, "input_data_order": "name_asc"}

    """'--json'が指定されたとき、この値以下ならば`put_task`APIでタスクを登録する。
    この値を超えているならば、`initiate_tasks_generation`APIでタスクを登録する。"""

    def put_task_by_count(self, project_id: str, task_generate_rule: Dict[str, Any]):
        project_last_updated_datetime = self.service.api.get_project(project_id)[0]["updated_datetime"]
        task_generate_rule.update({"_type": "ByCount"})
        request_body = {
            "task_generate_rule": task_generate_rule,
            "project_last_updated_datetime": project_last_updated_datetime,
        }
        self.service.api.initiate_tasks_generation(project_id, request_body=request_body)

    def wait_for_completion(
        self,
        project_id: str,
        wait_options: WaitOptions,
        wait: bool = False,
    ) -> None:
        """
        CSVファイルからタスクを登録する。

        Args:
            project_id:
            wait_options: タスク登録の完了を待つ処理
            wait: タスク登録が完了するまで待つかどうか
        """
        logger.info(f"タスクの登録中です（サーバ側の処理）。")

        if wait:
            MAX_WAIT_MINUTE = wait_options.max_tries * wait_options.interval / 60
            logger.info(f"最大{MAX_WAIT_MINUTE}分間、タスク登録処理が終了するまで待ちます。")

            result = self.service.wrapper.wait_for_completion(
                project_id,
                job_type=ProjectJobType.GEN_TASKS,
                job_access_interval=wait_options.interval,
                max_job_access=wait_options.max_tries,
            )
            if result:
                logger.info(f"タスクの登録が完了しました。")
            else:
                logger.warning(f"タスクの登録に失敗しました。または、{MAX_WAIT_MINUTE}分間待っても、タスクの登録が完了しませんでした。")

    def main(self):
        args = self.args
        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        api_with_creating_task = ApiWithCreatingTask(args.api) if args.api is not None else None
        main_obj = PuttingTaskMain(self.service, project_id=args.project_id, all_yes=args.yes)

        if args.csv is not None:
            csv_file = args.csv
            task_relation_dict = get_task_relation_dict(csv_file)
            main_obj.generate_task(api_with_creating_task, task_relation_dict, csv_file, parallelism=args.parallelism)

        elif args.json is not None:
            # CSVファイルに変換する
            task_relation_dict = get_json_from_args(args.json)
            main_obj.generate_task(
                api_with_creating_task, task_relation_dict, csv_file=None, parallelism=args.parallelism
            )

        elif args.by_count is not None:
            by_count = copy.deepcopy(PutTask.DEFAULT_BY_COUNT)
            by_count.update(get_json_from_args(args.by_count))
            self.put_task_by_count(project_id, by_count)
        else:
            raise RuntimeError("--csv or --by_count が指定されていません。")

        wait_options = get_wait_options_from_args(get_json_from_args(args.wait_options), DEFAULT_WAIT_OPTIONS)
        self.wait_for_completion(
            project_id,
            wait=args.wait,
            wait_options=wait_options,
        )


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
            "タスク作成画面でアップロードするCSVと同じフォーマットです。"
            "\n"
            " * ヘッダ行なし, カンマ区切り\n"
            " * 1列目: task_id\n"
            " * 2列目: Any(無視される)\n"
            " * 3列目: input_data_id\n"
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

    file_group.add_argument(
        "--by_count",
        type=str,
        help=f"1つのタスクに割り当てる入力データの個数などの情報を、JSON形式で指定してください。\n"
        "JSONフォーマットは https://annofab.com/docs/api/#operation/initiateTasksGeneration"
        " APIのリクエストボディ ``task_generate_rule`` と同じです。"
        f"デフォルトは ``{json.dumps(PutTask.DEFAULT_BY_COUNT)}`` です。\n"
        "``file://`` を先頭に付けるとjsonファイルを指定できます。",
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
        help="並列度。指定しない場合は、逐次的に処理します。``put_task`` WebAPIを使うときのみ有効なオプおションです。",
    )

    parser.add_argument("--wait", action="store_true", help=("タスク登録が完了するまで待ちます。"))

    parser.add_argument(
        "--wait_options",
        type=str,
        help="タスクの登録が完了するまで待つ際のオプションを、JSON形式で指定してください。"
        " ``file://`` を先頭に付けるとjsonファイルを指定できます。"
        'デフォルは ``{"interval":60, "max_tries":360}`` です。'
        "``interval`` :完了したかを問い合わせる間隔[秒], "
        "``max_tires`` :完了したかの問い合わせを最大何回行うか。",
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
