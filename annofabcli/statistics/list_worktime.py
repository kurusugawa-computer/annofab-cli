from __future__ import annotations

import argparse
import datetime
import json
import logging
import tempfile
from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import annofabapi
import pandas
from annofabapi.models import TaskHistoryEvent, TaskStatus
from dataclasses_json import DataClassJsonMixin
from dateutil.parser import parse

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


@dataclass
class SimpleTaskHistoryEvent(DataClassJsonMixin):
    task_history_id: str
    created_datetime: str
    status: str


@dataclass
class RequestOfTaskHistoryEvent(DataClassJsonMixin):
    """operateTask APIによってタスク履歴イベントが生成されたときのリクエストボディ

    ただし、CLIユーザーにとって不要な情報は除いています。
    """

    status: str
    force: bool
    account_id: str | None
    user_id: str | None
    username: str | None


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
    end_event_request: RequestOfTaskHistoryEvent
    """operateTask APIによってタスク履歴イベントが生成されたときのリクエストボディ"""


class ListWorktimeFromTaskHistoryEventMain:
    def __init__(self, service: annofabapi.Resource, *, project_id: str) -> None:
        self.service = service
        self.visualize = AddProps(service, project_id)

    @staticmethod
    def filter_task_history_event(task_history_event_list: list[TaskHistoryEvent], task_id_list: list[str] | None = None) -> list[TaskHistoryEvent]:
        if task_id_list is not None:
            result = []
            task_id_set = set(task_id_list)
            for event in task_history_event_list:
                if event["task_id"] in task_id_set:
                    result.append(event)  # noqa: PERF401

            return result

        return task_history_event_list

    def get_task_history_event_list(self, project_id: str, task_history_event_json: Path | None = None, temp_dir: Path | None = None) -> list[dict[str, Any]]:
        if task_history_event_json is not None:
            with task_history_event_json.open(encoding="utf-8") as f:
                return json.load(f)

        downloading_obj = DownloadingFile(self.service)
        if temp_dir is not None:
            json_path = downloading_obj.download_task_history_event_json_to_dir(project_id, temp_dir)
            with json_path.open(encoding="utf-8") as f:
                return json.load(f)

        with tempfile.TemporaryDirectory() as str_temp_dir:
            json_path = downloading_obj.download_task_history_event_json_to_dir(project_id, Path(str_temp_dir))
            with json_path.open(encoding="utf-8") as f:
                return json.load(f)

    @staticmethod
    def _create_task_history_event_dict(
        task_history_event_list: list[TaskHistoryEvent],
        *,
        task_ids: set[str] | None,
        account_ids: set[str] | None,
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

    def _create_worktime(self, start_event: TaskHistoryEvent, end_event: TaskHistoryEvent) -> WorktimeFromTaskHistoryEvent:
        diff = parse(end_event["created_datetime"]) - parse(start_event["created_datetime"])
        worktime_hour = diff.total_seconds() / 3600
        assert worktime_hour >= 0, f"worktime_hourが負の値です。start_event.created_datetime={start_event['created_datetime']}, end_event.created_datetime{end_event['created_datetime']}"

        member = self.visualize.get_project_member_from_account_id(start_event["account_id"])
        if member is not None:
            user_id = member["user_id"]
            username = member["username"]
        else:
            user_id = None
            username = None

        end_event_request_account_id = end_event["request"]["account_id"]
        end_event_request_member = self.visualize.get_project_member_from_account_id(end_event_request_account_id)
        if end_event_request_member is not None:
            end_event_request_user_id = end_event_request_member["user_id"]
            end_event_request_username = end_event_request_member["username"]
        else:
            end_event_request_user_id = None
            end_event_request_username = None

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
            end_event_request=RequestOfTaskHistoryEvent(
                status=end_event["request"]["status"],
                force=end_event["request"]["force"],
                account_id=end_event["request"]["account_id"],
                user_id=end_event_request_user_id,
                username=end_event_request_username,
            ),
        )

    def _create_worktime_list(self, task_id: str, task_history_event_list: list[TaskHistoryEvent]) -> list[WorktimeFromTaskHistoryEvent]:
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
                    f"task_id='{task_id}' :: 作業開始のイベント（task_history_id='{event['task_history_id']}'）の次のイベント（task_history_id='{next_event['task_history_id']}'）は、"
                    f"作業終了のイベントではないため、作業時間を算出できません。スキップします。"
                    f"タスク履歴イベントが不整合な状態なので、Annofabチームに問い合わせてください。 :: "
                    f"start_event='{start_event}', next_event='{next_event}'"
                )
                i += 1
                continue

            worktime = self._create_worktime(start_event, next_event)
            result.append(worktime)
            # 次のタスク履歴イベントのstatusはworkingでないことがわかっているので、インデックスを2つ増加させる
            i += 2

        return result

    def get_account_ids_from_user_ids(self, project_id: str, user_ids: set[str]) -> set[str]:
        project_member_list = self.service.wrapper.get_all_project_members(project_id, query_params={"include_inactive_member": True})
        return {e["account_id"] for e in project_member_list if e["user_id"] in user_ids}

    def get_worktime_list(
        self,
        project_id: str,
        task_history_event_json: Path | None = None,
        task_id_list: list[str] | None = None,
        user_id_list: list[str] | None = None,
        temp_dir: Path | None = None,
    ) -> list[WorktimeFromTaskHistoryEvent]:
        all_task_history_event_list = self.get_task_history_event_list(project_id, task_history_event_json=task_history_event_json, temp_dir=temp_dir)

        task_id_set = set(task_id_list) if task_id_list is not None else None
        account_id_set = self.get_account_ids_from_user_ids(project_id, set(user_id_list)) if user_id_list is not None else None

        task_history_event_dict = self._create_task_history_event_dict(all_task_history_event_list, task_ids=task_id_set, account_ids=account_id_set)

        worktime_list = []
        for task_id, subset_event_list in task_history_event_dict.items():
            subset_worktime_list = self._create_worktime_list(task_id, subset_event_list)
            worktime_list.extend(subset_worktime_list)
        return worktime_list


WorktimeDict = dict[tuple[str, str, str], float]
"""日付、アカウントID、工程をキーとする作業時間（時間単位）。"""

WORKTIME_COLUMNS = [
    "date",
    "account_id",
    "user_id",
    "username",
    "biography",
    "worktime_hour",
    "annotation_worktime_hour",
    "inspection_worktime_hour",
    "acceptance_worktime_hour",
]
"""作業時間集計の出力列。"""


def _get_worktime_dict_from_event(event: WorktimeFromTaskHistoryEvent) -> WorktimeDict:
    """作業区間を日付ごとに分割する。

    Args:
        event: 作業区間の情報。

    Returns:
        日付、アカウントID、工程ごとの作業時間。
    """
    dict_result: WorktimeDict = defaultdict(float)

    dt_start = parse(event.start_event.created_datetime)
    dt_end = parse(event.end_event.created_datetime)

    if dt_start.date() == dt_end.date():
        worktime_hour = (dt_end - dt_start).total_seconds() / 3600
        dict_result[(str(dt_start.date()), event.account_id, event.phase)] = worktime_hour
    else:
        jst_tzinfo = datetime.timezone(datetime.timedelta(hours=9))
        dt_tmp_start = dt_start

        while dt_tmp_start.date() < dt_end.date():
            dt_next_date = dt_tmp_start.date() + datetime.timedelta(days=1)
            dt_tmp_end = datetime.datetime(year=dt_next_date.year, month=dt_next_date.month, day=dt_next_date.day, tzinfo=jst_tzinfo)
            worktime_hour = (dt_tmp_end - dt_tmp_start).total_seconds() / 3600
            dict_result[(str(dt_tmp_start.date()), event.account_id, event.phase)] = worktime_hour
            dt_tmp_start = dt_tmp_end

        worktime_hour = (dt_end - dt_tmp_start).total_seconds() / 3600
        dict_result[(str(dt_tmp_start.date()), event.account_id, event.phase)] = worktime_hour

    return dict_result


def get_worktime_dict_from_event_list(task_history_event_list: Collection[WorktimeFromTaskHistoryEvent]) -> WorktimeDict:
    """作業区間を日付、アカウントID、工程ごとに集計する。

    Args:
        task_history_event_list: 作業区間の一覧。

    Returns:
        日付、アカウントID、工程ごとの作業時間。
    """
    dict_result: WorktimeDict = defaultdict(float)

    for event in task_history_event_list:
        dict_tmp = _get_worktime_dict_from_event(event)
        for key, value in dict_tmp.items():
            dict_result[key] += value
    return dict_result


def get_df_worktime(task_history_event_list: Collection[WorktimeFromTaskHistoryEvent], member_list: list[dict[str, Any]]) -> pandas.DataFrame:
    """ユーザーごと日付ごとの作業時間を表にする。

    Args:
        task_history_event_list: 作業区間の一覧。
        member_list: プロジェクトメンバーの一覧。

    Returns:
        工程別の作業時間と合計作業時間を持つDataFrame。
    """
    if not task_history_event_list:
        return pandas.DataFrame(columns=WORKTIME_COLUMNS)

    dict_worktime = get_worktime_dict_from_event_list(task_history_event_list)

    s = pandas.Series(
        dict_worktime.values(),
        index=pandas.MultiIndex.from_tuples(dict_worktime.keys(), names=("date", "account_id", "phase")),
    )
    df = s.unstack()  # noqa: PD010 : pandas.Seriesにはpivot_tableがないので、警告を無視する
    df.reset_index(inplace=True)
    df.rename(
        columns={
            "annotation": "annotation_worktime_hour",
            "inspection": "inspection_worktime_hour",
            "acceptance": "acceptance_worktime_hour",
        },
        inplace=True,
    )

    # 列数を固定させる
    for phase in ["annotation", "inspection", "acceptance"]:
        column = f"{phase}_worktime_hour"
        if column not in df.columns:
            df[column] = 0

    df.fillna({"annotation_worktime_hour": 0, "inspection_worktime_hour": 0, "acceptance_worktime_hour": 0}, inplace=True)

    df["worktime_hour"] = df["annotation_worktime_hour"] + df["inspection_worktime_hour"] + df["acceptance_worktime_hour"]

    df_member = pandas.DataFrame(member_list, columns=["account_id", "user_id", "username", "biography"])

    df = df.merge(df_member, how="left", on="account_id")
    return df[WORKTIME_COLUMNS]


class ListWorktimeFromTaskHistoryEvent(CommandLine):
    def print_worktime_list(
        self,
        project_id: str,
        task_history_event_json: Path | None,
    ) -> None:
        """タスク履歴イベントから作業時間を集計して出力する。

        Args:
            project_id: プロジェクトID。
            task_history_event_json: タスク履歴イベント全件ファイルのパス。

        Returns:
            None
        """
        super().require_project_access(project_id, project_member_roles=None)

        main_obj = ListWorktimeFromTaskHistoryEventMain(self.service, project_id=project_id)
        worktime_list = main_obj.get_worktime_list(
            project_id,
            task_history_event_json=task_history_event_json,
        )
        project_member_list = self.service.wrapper.get_all_project_members(project_id, query_params={"include_inactive_member": ""})
        df = get_df_worktime(worktime_list, project_member_list)

        if self.str_format == OutputFormat.CSV.value:
            self.print_csv(df)
        else:
            self.print_according_to_format(df.to_dict(orient="records"))

    def main(self) -> None:
        """コマンドライン引数に従って集計する。

        Args:
            なし。

        Returns:
            None
        """
        args = self.args

        self.print_worktime_list(
            args.project_id,
            task_history_event_json=args.task_history_event_json,
        )


DEPRECATED_MESSAGE = "[DEPRECATED] statistics list_worktimeは非推奨です。代わりに task_history_event summarize_worktime_by_user_and_dateを使用してください。"


def main(args: argparse.Namespace) -> None:
    """認証して作業時間集計コマンドを実行する。

    Args:
        args: コマンドライン引数。

    Returns:
        None
    """
    logger.warning(DEPRECATED_MESSAGE)
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListWorktimeFromTaskHistoryEvent(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    """作業時間集計のコマンドライン引数を定義する。

    Args:
        parser: 引数パーサー。

    Returns:
        None
    """
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--task_history_event_json",
        type=Path,
        help="タスク履歴イベント全件ファイルパスを指定すると、JSONに記載された情報を元に作業時間を集計します。\n"
        "指定しない場合は、タスク履歴イベント全件ファイルをダウンロードします。\n"
        "JSONファイルは ``$ annofabcli task_history_event download`` コマンドで取得できます。",
    )

    argument_parser.add_format(choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON], default=OutputFormat.CSV)
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """旧コマンドのサブパーサーを追加する。

    Args:
        subparsers: サブパーサー。

    Returns:
        追加した引数パーサー。
    """
    subcommand_help = "[DEPRECATED] 日ごとユーザーごとの作業時間の一覧を出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, "list_worktime", subcommand_help, description=f"{subcommand_help}\n{DEPRECATED_MESSAGE}")
    parse_args(parser)
    return parser
