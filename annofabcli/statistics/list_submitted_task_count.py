import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import pandas
from annofabapi.models import TaskHistory
from annofabapi.parser import (
    SimpleAnnotationParser,
    SimpleAnnotationParserByTask,
    lazy_parse_simple_annotation_dir,
    lazy_parse_simple_annotation_dir_by_task,
    lazy_parse_simple_annotation_zip,
    lazy_parse_simple_annotation_zip_by_task,
)

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
from annofabcli.common.download import DownloadingFile

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)

logger = logging.getLogger(__name__)


def from_datetime_to_date(datetime: str) -> str:
    return datetime[0:10]


class ListSubmittedTaskCount(AbstractCommandLineInterface):
    CSV_FORMAT = {"encoding": "utf_8_sig", "index": False}

    def get_task_history_dict(
        self, project_id: str, task_history_json_path: Optional[Path]
    ) -> Dict[str, List[TaskHistory]]:
        if task_history_json_path is not None:
            json_path = task_history_json_path
        else:
            cache_dir = annofabcli.utils.get_cache_dir()
            json_path = cache_dir / f"task-history-{project_id}.json"
            downloading_obj = DownloadingFile(self.service)
            downloading_obj.download_task_history_json(project_id, dest_path=str(task_history_json_path))

        with json_path.open(encoding="utf-8") as f:
            task_history_dict = json.load(f)
            return task_history_dict

    def create_submitted_task_count_df(
        self, project_id: str, task_history_dict: Dict[str, List[TaskHistory]]
    ) -> pandas.DataFrame:
        task__history_count_dict = defaultdict(int)
        for task_id, task_history_list in task_history_dict.items():
            for task_history in task_history_list:
                if task_history["ended_datetime"] is not None and task_history["account_id"] is not None:
                    ended_date = from_datetime_to_date(task_history["ended_datetime"])
                    task__history_count_dict[
                        (task_history["account_id"], task_history["phase"], task_history["phase_stage"], ended_date)
                    ] += 1

        data_list = []
        for key, task_count in task__history_count_dict.items():
            account_id, phaes, phase_stage, date = key
            member = self.facade.get_organization_member_from_account_id(project_id, account_id)
            data = {
                "user_id": member["user_id"],
                "username": member["username"],
                "biography": member["biography"],
                "date": date,
                "phase": phaes,
                "phase_stage": phase_stage,
            }
            data_list.append(data)

        return pandas.DataFrame(data_list)

    def main(self):
        args = self.args

        project_id = args.project_id
        super().validate_project(project_id, project_member_roles=None)

        task_history_dict = self.get_task_history_dict(project_id, args.task_history_json)
        df = self.create_submitted_task_count_df(project_id, task_history_dict=task_history_dict)
        self.print_csv(df)


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_csv_format()
    argument_parser.add_output()

    parser.add_argument(
        "--task_history_json",
        type=Path,
        help="タスク履歴情報が記載されたJSONファイルのパスを指定してます。JSONファイルは`$ annofabcli project download task_history`コマンドで取得できます。"
        "指定しない場合は、AnnoFabからタスク履歴全件ファイルをダウンロードします。",
    )

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListSubmittedTaskCount(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_submitted_task_count"
    subcommand_help = "提出したタスク数/合格にしたタスク数/差し戻したタスク数を出力します。"
    description = "日ごと、ユーザごとに、提出したタスク数（教師付フェーズ）/合格にしたタスク数（検査・受入フェーズ）/ 差し戻したタスク数を出力します。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog
    )
    parse_args(parser)
