from __future__ import annotations
from collections import defaultdict
import argparse
import json
import logging
from pathlib import Path
from typing import Any, List, Optional

import annofabapi
from annofabapi.models import Task, TaskHistoryEvent, TaskStatus
import pandas

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.utils import T
from annofabcli.common.visualize import AddProps
from dataclasses import dataclass
from dataclasses_json import DataClassJsonMixin
from enum import Enum
from dateutil.parser import parse
logger = logging.getLogger(__name__)


class SimpleTaskHistoryEvent(DataClassJsonMixin):
    task_history_id: str
    created_datetime: str
    status: str

class WorktimeFromTaskHistoryEvent(DataClassJsonMixin):
    project_id:str
    task_id: str
    phase: str
    phase_stage: int
    account_id: str
    worktime_hour: float
    start_event: SimpleTaskHistoryEvent
    end_event: SimpleTaskHistoryEvent
    user_id: Optional[str]=None
    username: Optional[str]=None


class ListWorktimeFromTaskHistoryEventMain:
    def __init__(self, service: annofabapi.Resource):
        self.service = service

    @staticmethod
    def filter_task_history_event(
        task_history_event_list: list[TaskHistoryEvent], task_id_list: Optional[list[str]] = None
    ) -> list[TaskHistoryEvent]:
        if task_id_list is not None:
            result = []
            task_id_set = set(task_id_list)
            for event in task_history_event_list:
                if event["task_id"] in task_id_set:
                    result.append(event)

            return result
        
        return task_history_event_list

    def get_task_history_event_list(
        self, project_id: str, task_history_event_json: Optional[Path] = None, task_id_list: Optional[List[str]] = None
    ) -> list[dict[str, Any]]:
        if task_history_event_json is None:
            downloading_obj = DownloadingFile(self.service)
            cache_dir = annofabcli.utils.get_cache_dir()
            json_path = cache_dir / f"{project_id}-task_history_event.json"

            downloading_obj.download_task_history_event_json(project_id, str(json_path))
        else:
            json_path = task_history_event_json

        with json_path.open() as f:
            all_task_history_event_list = json.load(f)


        for event in filtered_task_history_event_list:
            visualize.add_properties_to_task_history_event(event)

        return filtered_task_history_event_list

    @staticmethod
    def _create_task_history_event_dict(task_history_event_list:list[TaskHistoryEvent], *, task_ids: Optional[set[str]]) -> dict[str, list[TaskHistoryEvent]]:
        """
        keyがtask_id, valueがタスク履歴イベントのlistであるdictを生成する。
        タスク履歴イベントlistは`created_datetime`の昇順にソートされている
        """
        result: dict[str, list[TaskHistoryEvent]] = defaultdict(list)

        for event in task_history_event_list:
            if task_ids is None or event["task_id"] in task_ids:
                result[event["task_id"]].append(event)    
        

        for event_list in result.values():
            event_list.sort(key=lambda e: e["created_datetime"])

        return result

    @staticmethod
    def _create_worktime(start_event: TaskHistoryEvent, end_event:TaskHistoryEvent) -> WorktimeFromTaskHistoryEvent:
        diff = parse(end_event["created_datetime"]) - parse(start_event["created_datetime"])
        worktime_seconds = diff.seconds + diff.microseconds * 0.001
        worktime_hour = worktime_seconds / 3600
        assert worktime_hour >= 0, (f"worktime_hourが負の値です。"
            f"start_event.created_datetime={start_event['created_datetime']}, end_event.created_datetime{end_event['created_datetime']}")

        return WorktimeFromTaskHistoryEvent(
            # start_eventとend_eventの以下の属性は同じなので、start_eventの値を参照する
            project_id = start_event["project_id"],
            task_id = start_event["task_id"],
            phase = start_event["phase"],
            phase_stage = start_event["phase_stage"],
            account_id = start_event["account_id"],
            worktime_hour = worktime_hour,
            start_event = start_event,
            end_event = end_event
        )        



    @classmethod
    def _create_worktime_list(cls, task_history_event_list:list[TaskHistoryEvent]) -> list[WorktimeFromTaskHistoryEvent]:
        result = []
        i = 0

        while i < len(task_history_event_list):
            event = task_history_event_list[i]            
            if event["status"] != TaskStatus.WORKING.value:
                i+=1
                continue

            start_event = event
            
            if i+1 >= len(task_history_event_list):
                # タスクの状態が作業中の場合
                break
            
            next_event = event[i+1]
            if next_event["status"] not in {TaskStatus.BREAK.value, TaskStatus.ON_HOLD.value, TaskStatus.COMPLETE.value}:
                logger.warning("作業中状態のタスク履歴イベントに対応するタスク履歴イベントが存在しませんでした。"
                    f":: start_event={start_event}, next_event={next_event}")
                i+=1
                continue
            
            worktime = cls._create_worktime(start_event, next_event)
            result.append(worktime)
            # 次のタスク履歴イベントのstatusはworkingでないことがわかっているので、インデックスを2つ増加させる
            i+=2
        
        return result


    def get_worktime_list(self, project_id: str, task_history_event_json: Optional[Path] = None, task_id_list: Optional[List[str]] = None) -> list[dict[str,Any]]:
        all_task_history_event_list = self.get_task_history_event_list(project_id,task_history_event_json=task_history_event_json)
        
        task_history_event_dict = self._create_task_history_event_dict(task_history_event_list, task_id_list)

        pass    



class ListWorktimeFromTaskHistoryEvent(AbstractCommandLineInterface):
    def print_worktime_from_task_history_event(
        self,
        project_id: str,
        task_history_event_json: Optional[Path],
        task_id_list: Optional[list[str]],
        arg_format: FormatArgument,
    ):

        super().validate_project(project_id, project_member_roles=None)

        main_obj = ListWorktimeFromTaskHistoryEventMain(self.service)
        task_history_event_list = main_obj.get_task_history_event_list(
            project_id, task_history_event_json=task_history_event_json, task_id_list=task_id_list
        )
        if arg_format == FormatArgument.CSV:
            df = pandas.json_normalize(task_history_event_list)
            self.print_csv(df)
        else:
            self.print_according_to_format(task_history_event_list)

    def main(self):
        args = self.args

        task_id_list = get_list_from_args(args.task_id) if args.task_id is not None else None

        self.print_worktime_from_task_history_event(
            args.project_id,
            task_history_event_json=args.task_history_event_json,
            task_id_list=task_id_list,
            arg_format=FormatArgument(args.format),
        )

    @staticmethod
    def to_all_task_history_event_list_from_dict(
        task_history_event_dict: dict[str, list[dict[str, Any]]]
    ) -> List[dict[str, Any]]:
        all_task_history_event_list = []
        for task_history_event_list in task_history_event_dict.values():
            all_task_history_event_list.extend(task_history_event_list)
        return all_task_history_event_list


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListWorktimeFromTaskHistoryEvent(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "-t",
        "--task_id",
        type=str,
        nargs="+",
        help="対象のタスクのtask_idを指定します。\n" " ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "--task_history_event_json",
        type=Path,
        help="タスク履歴イベント全件ファイルパスを指定すると、JSONに記載された情報を元にタスク履歴イベント一覧を出力します。\n"
        "指定しない場合は、タスク履歴イベント全件ファイルをダウンロードします。\n"
        "JSONファイルは ``$ annofabcli project download task_history_event`` コマンドで取得できます。",
    )

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON],
        default=FormatArgument.CSV,
    )
    argument_parser.add_output()
    argument_parser.add_csv_format()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "list_worktime"
    subcommand_help = "タスク履歴イベントから作業時間の一覧を出力します。"
    description = ("タスク履歴イベントから作業時間の一覧を出力します。\n"
        "「作業中状態から休憩状態までの作業時間」など、`annofabcli task_history list`で出力したタスク履歴一覧より詳細な作業時間の情報を出力します。")

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
