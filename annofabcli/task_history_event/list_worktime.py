from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

import annofabapi
import pandas
from annofabapi.models import TaskHistoryEvent, TaskStatus
from dataclasses_json import DataClassJsonMixin
from dateutil.parser import parse

import annofabcli
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


@dataclass
class SimpleTaskHistoryEvent(DataClassJsonMixin):
    task_history_id: str
    created_datetime: str
    status: str


@dataclass
class WorktimeFromTaskHistoryEvent(DataClassJsonMixin):
    project_id: str
    task_id: str
    phase: str
    phase_stage: int
    account_id: str
    user_id: str
    username: str
    worktime_hour: float
    start_event: SimpleTaskHistoryEvent
    end_event: SimpleTaskHistoryEvent


class ListWorktimeFromTaskHistoryEventMain:
    def __init__(self, service: annofabapi.Resource, *, project_id: str):
        self.service = service
        self.visualize = AddProps(service, project_id)

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
        self, project_id: str, task_history_event_json: Optional[Path] = None
    ) -> list[dict[str, Any]]:
        if task_history_event_json is None:
            downloading_obj = DownloadingFile(self.service)
            cache_dir = annofabcli.common.utils.get_cache_dir()
            json_path = cache_dir / f"{project_id}-task_history_event.json"

            downloading_obj.download_task_history_event_json(project_id, str(json_path))
        else:
            json_path = task_history_event_json

        with json_path.open(encoding="utf-8") as f:
            all_task_history_event_list = json.load(f)

        return all_task_history_event_list

    @staticmethod
    def _create_task_history_event_dict(
        task_history_event_list: list[TaskHistoryEvent],
        *,
        task_ids: Optional[set[str]],
        account_ids: Optional[set[str]],
    ) -> dict[str, list[TaskHistoryEvent]]:
        """
        keyがtask_id, valueがタスク履歴イベントのlistであるdictを生成する。
        タスク履歴イベントlistは`created_datetime`の昇順にソートされている
        """
        result: dict[str, list[TaskHistoryEvent]] = defaultdict(list)

        for event in task_history_event_list:
            if account_ids is not None and event["account_id"] not in account_ids:
                continue

            if task_ids is not None and event["task_id"] not in task_ids:
                continue

            result[event["task_id"]].append(event)

        for event_list in result.values():
            event_list.sort(key=lambda e: e["created_datetime"])

        return result

    def _create_worktime(
        self, start_event: TaskHistoryEvent, end_event: TaskHistoryEvent
    ) -> WorktimeFromTaskHistoryEvent:
        diff = parse(end_event["created_datetime"]) - parse(start_event["created_datetime"])
        worktime_hour = diff.total_seconds() / 3600
        assert worktime_hour >= 0, (
            f"worktime_hourが負の値です。"
            f"start_event.created_datetime={start_event['created_datetime']}, "
            f"end_event.created_datetime{end_event['created_datetime']}"
        )

        member = self.visualize.get_project_member_from_account_id(start_event["account_id"])
        if member is not None:
            user_id = member["user_id"]
            username = member["username"]
        else:
            user_id = None
            username = None

        return WorktimeFromTaskHistoryEvent(
            # start_eventとend_eventの以下の属性は同じなので、start_eventの値を参照する
            project_id=start_event["project_id"],
            task_id=start_event["task_id"],
            phase=start_event["phase"],
            phase_stage=start_event["phase_stage"],
            account_id=start_event["account_id"],
            user_id=user_id,
            username=username,
            worktime_hour=worktime_hour,
            start_event=SimpleTaskHistoryEvent(
                task_history_id=start_event["task_history_id"],
                created_datetime=start_event["created_datetime"],
                status=start_event["status"],
            ),
            end_event=SimpleTaskHistoryEvent(
                task_history_id=end_event["task_history_id"],
                created_datetime=end_event["created_datetime"],
                status=end_event["status"],
            ),
        )

    def _create_worktime_list(
        self, task_history_event_list: list[TaskHistoryEvent]
    ) -> list[WorktimeFromTaskHistoryEvent]:
        """タスク履歴イベントから、作業時間のリストを生成する。

        Args:
            task_history_event_list: タスク履歴イベントのlist。すべて同じtask_idで、created_datetimeでソートされていること
        """
        result = []
        i = 0

        while i < len(task_history_event_list):
            event = task_history_event_list[i]
            # account_idを判定している理由：
            # 受入完了状態のタスクで作成されたアノテーションを、アノテーション一覧画面からオーナーが一括編集すると、account_idがnullのタスク履歴イベントが生成されるため
            if event["status"] != TaskStatus.WORKING.value or event["account_id"] is None:
                i += 1
                continue

            start_event = event

            if i + 1 >= len(task_history_event_list):
                # タスクの状態が作業中の場合
                break

            next_event = task_history_event_list[i + 1]
            if next_event["status"] not in {
                TaskStatus.BREAK.value,
                TaskStatus.ON_HOLD.value,
                TaskStatus.COMPLETE.value,
            }:
                logger.warning(
                    "作業中状態のタスク履歴イベントに対応するタスク履歴イベントが存在しませんでした。" f":: start_event={start_event}, next_event={next_event}"
                )
                i += 1
                continue

            worktime = self._create_worktime(start_event, next_event)
            result.append(worktime)
            # 次のタスク履歴イベントのstatusはworkingでないことがわかっているので、インデックスを2つ増加させる
            i += 2

        return result

    def get_account_ids_from_user_ids(self, project_id: str, user_ids: set[str]) -> set[str]:
        project_member_list = self.service.wrapper.get_all_project_members(
            project_id, query_params={"include_inactive_member": True}
        )
        return {e["account_id"] for e in project_member_list if e["user_id"] in user_ids}

    def get_worktime_list(
        self,
        project_id: str,
        task_history_event_json: Optional[Path] = None,
        task_id_list: Optional[List[str]] = None,
        user_id_list: Optional[List[str]] = None,
    ) -> list[WorktimeFromTaskHistoryEvent]:
        all_task_history_event_list = self.get_task_history_event_list(
            project_id, task_history_event_json=task_history_event_json
        )

        task_id_set = set(task_id_list) if task_id_list is not None else None
        account_id_set = (
            self.get_account_ids_from_user_ids(project_id, set(user_id_list)) if user_id_list is not None else None
        )

        task_history_event_dict = self._create_task_history_event_dict(
            all_task_history_event_list, task_ids=task_id_set, account_ids=account_id_set
        )

        worktime_list = []
        for subset_event_list in task_history_event_dict.values():
            subset_worktime_list = self._create_worktime_list(subset_event_list)
            worktime_list.extend(subset_worktime_list)
        return worktime_list


class ListWorktimeFromTaskHistoryEvent(AbstractCommandLineInterface):
    def print_worktime_from_task_history_event(
        self,
        project_id: str,
        task_history_event_json: Optional[Path],
        task_id_list: Optional[list[str]],
        user_id_list: Optional[list[str]],
        arg_format: FormatArgument,
    ):

        super().validate_project(project_id, project_member_roles=None)

        main_obj = ListWorktimeFromTaskHistoryEventMain(self.service, project_id=project_id)
        worktime_list = main_obj.get_worktime_list(
            project_id,
            task_history_event_json=task_history_event_json,
            task_id_list=task_id_list,
            user_id_list=user_id_list,
        )

        logger.debug(f"作業時間一覧の件数: {len(worktime_list)}")

        if len(worktime_list) > 0:
            dict_worktime_list = [e.to_dict() for e in worktime_list]
            if arg_format == FormatArgument.CSV:
                df = pandas.json_normalize(dict_worktime_list)
                self.print_csv(df)
            else:
                self.print_according_to_format(dict_worktime_list)
        else:
            logger.warning(f"作業時間一覧の件数が0件であるため、出力しません。")
            return

    def main(self):
        args = self.args

        task_id_list = get_list_from_args(args.task_id) if args.task_id is not None else None
        user_id_list = get_list_from_args(args.user_id) if args.user_id is not None else None

        self.print_worktime_from_task_history_event(
            args.project_id,
            task_history_event_json=args.task_history_event_json,
            task_id_list=task_id_list,
            user_id_list=user_id_list,
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
        help="対象のタスクのuser_idを指定します。\n" "``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "-u",
        "--user_id",
        type=str,
        nargs="+",
        help="絞り込み対象のユーザのuser_idを指定します。\n" "``file://`` を先頭に付けると、user_idの一覧が記載されたファイルを指定できます。",
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
    description = "タスク履歴イベントから作業時間の一覧を出力します。\nタスク履歴より詳細な作業時間の情報を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
