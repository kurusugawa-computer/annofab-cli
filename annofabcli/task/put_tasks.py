import argparse
import copy
import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas
from annofabapi.models import ProjectJobType, ProjectMemberRole

import annofabcli
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

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)

TaskInputRelation = Dict[str, List[str]]
"""task_idとinput_data_idの構造を表現する型"""


class PutTask(AbstractCommandLineInterface):
    """
    CSVからタスクを登録する。
    """

    DEFAULT_BY_COUNT = {"allow_duplicate_input_data": False, "input_data_order": "name_asc"}

    TASK_THRESHOLD_FOR_JSON = 10
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

    def put_task_from_csv_file(self, project_id: str, csv_file: Path) -> None:
        """
        CSVファイルからタスクを登録する。

        Args:
            project_id:
            csv_file: タスク登録に関する情報が記載されたCSV
        """
        project_title = self.facade.get_project_title(project_id)
        logger.info(f"{project_title} に対して、{str(csv_file)} からタスクを登録します。")
        self.service.wrapper.initiate_tasks_generation_by_csv(project_id, csvfile_path=str(csv_file))

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

    @staticmethod
    def create_task_relation_dataframe(task_relation_dict: TaskInputRelation) -> pandas.DataFrame:
        tmp_list = []
        for task_id, input_data_id_list in task_relation_dict.items():
            for input_data_id in input_data_id_list:
                tmp_list.append({"task_id": task_id, "input_data_id": input_data_id})
        df = pandas.DataFrame(tmp_list)
        df["input_data_name"] = ""
        return df[["task_id", "input_data_name", "input_data_id"]]

    def main(self):
        args = self.args
        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        if args.csv is not None:
            csv_file = Path(args.csv)
            self.put_task_from_csv_file(project_id, csv_file)
        elif args.json is not None:
            # CSVファイルに変換する
            task_relation_dict = get_json_from_args(args.json)
            if len(task_relation_dict) > self.TASK_THRESHOLD_FOR_JSON:
                df = self.create_task_relation_dataframe(task_relation_dict)
                with tempfile.NamedTemporaryFile() as f:
                    df.to_csv(f, index=False, header=None)
                    self.put_task_from_csv_file(project_id, f.name)
            else:
                # 登録件数が少ない場合は、put_taskの方が早いのでこちらで登録する。
                task_count = 0
                for task_id, input_data_id_list in task_relation_dict.items():
                    task = self.service.wrapper.get_task_or_none(project_id, task_id)
                    if task is None:
                        logger.debug(f"タスク'{task_id}'を登録します。")
                        self.service.api.put_task(
                            project_id, task_id, request_body={"input_data_id_list": input_data_id_list}
                        )
                        task_count += 1
                    else:
                        logger.warning(f"タスク'{task_id}'はすでに存在するため、登録をスキップします。")
                        self.service.api.put_task(
                            project_id, task_id, request_body={"input_data_id_list": input_data_id_list}
                        )

                logger.info(f"{task_count} 件のタスクを登録しました。")
                return

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
        type=str,
        help=(
            "タスクに割り当てる入力データが記載されたCSVファイルのパスを指定してください。"
            "CSVのフォーマットは、「1列目:task_id,2列目:Any(無視される), 3列目:input_data_id」です。"
            "タスク作成画面でアップロードするCSVと同じフォーマットです。"
        ),
    )

    JSON_SAMPLE = '{"task1":["input1","input2"]}'
    file_group.add_argument(
        "--json",
        type=str,
        help=(
            "タスクに割り当てる入力データをJSON形式で指定してください。"
            "keyがtask_id, valueがinput_data_idのlistです。"
            f"(ex) {JSON_SAMPLE} "
            "``file://`` を先頭に付けるとjsonファイルを指定できます。"
        ),
    )

    file_group.add_argument(
        "--by_count",
        type=str,
        help=f"1つのタスクに割り当てる入力データの個数などの情報を、JSON形式で指定してください。"
        "JSONフォーマットは https://annofab.com/docs/api/#operation/initiateTasksGeneration"
        " APIのリクエストボディ 'task_generate_rule'と同じです。"
        f"デフォルトは'{json.dumps(PutTask.DEFAULT_BY_COUNT)}'です。"
        "'file://'を先頭に付けるとjsonファイルを指定できます。",
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
