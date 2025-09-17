from __future__ import annotations

import argparse
import datetime
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import pandas
from dateutil.parser import parse

import annofabcli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.task_history_event.list_worktime import (
    ListWorktimeFromTaskHistoryEventMain,
    WorktimeFromTaskHistoryEvent,
)

logger = logging.getLogger(__name__)

WorktimeDict = dict[tuple[str, str, str], float]
"""key: date, account_id, phase"""


def _get_worktime_dict_from_event(event: WorktimeFromTaskHistoryEvent) -> WorktimeDict:
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


def get_worktime_dict_from_event_list(task_history_event_list: list[WorktimeFromTaskHistoryEvent]) -> WorktimeDict:
    dict_result: WorktimeDict = defaultdict(float)

    for event in task_history_event_list:
        dict_tmp = _get_worktime_dict_from_event(event)
        for key, value in dict_tmp.items():
            dict_result[key] += value
    return dict_result


def get_df_worktime(task_history_event_list: list[WorktimeFromTaskHistoryEvent], member_list: list[dict[str, Any]]) -> pandas.DataFrame:
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

    df_member = pandas.DataFrame(member_list)[["account_id", "user_id", "username", "biography"]]

    df = df.merge(df_member, how="left", on="account_id")
    return df[
        [
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
    ]


class ListWorktimeFromTaskHistoryEvent(CommandLine):
    def print_worktime_list(
        self,
        project_id: str,
        task_history_event_json: Optional[Path],
    ) -> None:
        super().validate_project(project_id, project_member_roles=None)

        main_obj = ListWorktimeFromTaskHistoryEventMain(self.service, project_id=project_id)
        worktime_list = main_obj.get_worktime_list(
            project_id,
            task_history_event_json=task_history_event_json,
        )
        project_member_list = self.service.wrapper.get_all_project_members(project_id, query_params={"include_inactive_member": ""})
        df = get_df_worktime(worktime_list, project_member_list)

        if len(worktime_list) > 0:
            self.print_csv(df)
        else:
            logger.warning("データ件数が0件であるため、出力しません。")

    def main(self) -> None:
        args = self.args

        self.print_worktime_list(
            args.project_id,
            task_history_event_json=args.task_history_event_json,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListWorktimeFromTaskHistoryEvent(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--task_history_event_json",
        type=Path,
        help="タスク履歴イベント全件ファイルパスを指定すると、JSONに記載された情報を元にタスク履歴イベント一覧を出力します。\n"
        "指定しない場合は、タスク履歴イベント全件ファイルをダウンロードします。\n"
        "JSONファイルは ``$ annofabcli task_history_event download`` コマンドで取得できます。",
    )

    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_worktime"
    subcommand_help = "日ごとユーザごとの作業時間の一覧を出力します。"
    description = "タスク履歴イベント全件ファイルから、日ごとユーザごとの作業時間の一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
