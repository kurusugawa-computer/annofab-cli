import argparse
import datetime
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import annofabapi
import dateutil.parser
import pandas as pd

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.download import DownloadingFile
from annofabcli.common.utils import read_lines_except_blank_line

logger = logging.getLogger(__name__)


class FindBreakError(AbstractCommandLineInterface):
    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        project_id_list = get_list_from_args(args.project_id)
        self.project_id_list = list(set(project_id_list))

    def _get_username(self, project_id: str, account_id: str) -> str:
        """
        プロジェクトメンバのusernameを取得する。プロジェクトメンバでなければ、account_idを返す。
        account_idがNoneならばNoneを返す。
        """
        member = self.facade.get_project_member_from_account_id(project_id, account_id)
        if member is not None:
            return member["username"]
        else:
            return account_id

    def _get_account_id(self, project_id: str, user_id: str) -> str:
        """
        プロジェクトメンバのusernameを取得する。プロジェクトメンバでなければ、account_idを返す。
        account_idがNoneならばNoneを返す。
        """
        member = self.facade.get_account_id_from_user_id(project_id, user_id)
        if member is not None:
            return member
        else:
            return user_id

    def _get_project_title(self, project_id: str) -> str:
        """
        プロジェクトメンバのusernameを取得する。プロジェクトメンバでなければ、account_idを返す。
        account_idがNoneならばNoneを返す。
        """
        project_title = self.facade.get_project_title(project_id)
        if project_title is not None:
            return project_title
        else:
            return project_id

    def _project_task_history_events(
        self, project_id: str, import_file_path: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        タスク履歴イベント全件ファイルを取得する。
        import_fileがNone:history_events_urlパスから直接読み込む
        import_fileがNoneではない:import_fileで指定されたファイルから読み込む
        """
        project_task_history_events: List[Dict[str, Any]] = []
        if import_file_path is None:
            downloading_obj = DownloadingFile(self.service)
            cache_dir = annofabcli.utils.get_cache_dir()
            json_path = cache_dir / f"{project_id}-inspection.json"
            downloading_obj.download_task_history_event_json(project_id, str(json_path))
            with json_path.open() as f:
                project_task_history_events = json.load(f)

        else:
            history_events = read_lines_except_blank_line(import_file_path)
            project_task_history_events = json.loads(history_events[0])

        return project_task_history_events

    def get_sort_events(self, args, task_history_events: List[Dict[str, Any]]) -> Dict[str, List[pd.DataFrame]]:
        df = pd.json_normalize(task_history_events)
        df["created_datetime"] = pd.to_datetime(df["created_datetime"])
        df["created_datetime"] = df["created_datetime"].dt.tz_localize(None)

        if args.task_id:
            task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
            df_list = []
            for task_id in task_id_list:
                df_list.append(df[df["task_id"] == task_id].copy())
            df = pd.concat(df_list, axis=0)

        if args.user_id:
            account_id = self._get_account_id(project_id=args.project_id, user_id=args.user_id)
            df = df[df["account_id"] == account_id].copy()

        if args.phase:
            df = df[df["phase"] == args.phase].copy()

        if args.start_datetime:
            start_datetime = dateutil.parser.parse(args.start_datetime)
            df = df[df["created_datetime"] >= start_datetime].copy()

        if args.end_datetime:
            end_datetime = dateutil.parser.parse(args.end_datetime)
            df = df[df["created_datetime"] <= (end_datetime + pd.to_timedelta(1, unit="s"))].copy()

        df = df[df["status"] != "not_started"].copy()
        df = df.sort_values("created_datetime")

        task_sort_history_events: Dict[str, List[Any]] = {}
        for row in df.itertuples():
            if row.task_id in task_sort_history_events:
                task_sort_history_events[row.task_id].append(row)
            else:
                task_sort_history_events[row.task_id] = [row]

        return task_sort_history_events

    def get_time_sort_events(self, time: int, task_sort_history_events: Dict[str, List[pd.DataFrame]]):
        # Index = 2017,
        # project_id = 'OCI_ROBOP_3DPC_202012',
        # task_id = '2020-11-19-14-58-19.bag_UNIT2_000740',
        # task_history_id = '80693997-5e15-49dd-b47f-f53e91db27d6',
        # created_datetime = Timestamp('2020-12-25 19:12:03.481000'),
        # phase = 'annotation',
        # phase_stage = 1,
        # status = 'working',
        # account_id = 'bc9141bf-0bac-4703-9f44-791b72a83ff3',
        OUTPUT_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S+09:00"
        event_list = []
        for sort_history_events in task_sort_history_events.values():
            # タスクのかたまりごとに処理
            for i, sort_history_event in enumerate(sort_history_events):
                if sort_history_event.status == "working":
                    if len(sort_history_events) == i + 1:
                        dt_now = datetime.datetime.now()
                        time_diff = dt_now - sort_history_event.created_datetime
                        end = False
                        time_diff_minute = time_diff.total_seconds() / 60
                    else:
                        time_diff = sort_history_events[i + 1].created_datetime - sort_history_event.created_datetime
                        end = True
                        time_diff_minute = time_diff.total_seconds() / 60
                    if time_diff.total_seconds() / 60 >= time:
                        new_event = {
                            "project_id": sort_history_event.project_id,
                            "project_title": self._get_project_title(sort_history_event.project_id),
                            "task_id": sort_history_event.task_id,
                            "account_id": sort_history_event.account_id,
                            "user_id": self._get_username(
                                project_id=sort_history_event.project_id, account_id=sort_history_event.account_id
                            ),
                            "phase": sort_history_event.phase,
                            "start_task_history_id": sort_history_event.task_history_id,
                            "start_created_datetime": sort_history_event.created_datetime.strftime(
                                OUTPUT_DATETIME_FORMAT
                            ),
                            "start_status": sort_history_event.status,
                            "end_task_history_id": sort_history_events[i + 1].task_history_id if end else None,
                            "end_created_datetime": sort_history_events[i + 1].created_datetime.strftime(
                                OUTPUT_DATETIME_FORMAT
                            )
                            if end
                            else None,
                            "end_status": sort_history_events[i + 1].status if end else None,
                            "diff_time": time_diff_minute,
                        }
                        event_list.append(new_event)

        return event_list

    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli experimental find_break_error: error:"
        if args.task_history_event_json is not None:
            if not args.task_history_event_json.exists():
                print(
                    f"{COMMON_MESSAGE} argument --task_history_event_json: ファイルパスが存在しません\
                '{args.task_history_event_json}'",
                    file=sys.stderr,
                )
                return False
        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            return

        task_history_events = self._project_task_history_events(
            project_id=args.project_id, import_file_path=args.task_history_event_json
        )
        if not task_history_events:
            # 全件ファイルの更新に失敗したらスルー
            logger.warning(f"タスク履歴イベント全件ファイルの取得に失敗しました。")
            return
        task_sort_history_events = self.get_sort_events(args, task_history_events)
        time_sort_history_events = self.get_time_sort_events(args.threshold, task_sort_history_events)
        output_err_events(err_events_list=time_sort_history_events, output=self.output)


def output_err_events(err_events_list: List[Dict[str, Any]], output: str = None):
    """
    開始と終了のhistory_eventsのペアから出力する
    :param err_events_list:
    :param output:
    :return:
    """

    if not err_events_list:
        logger.warning("historyが見つからなかった為、出力しません。")
        return
    df = pd.json_normalize(err_events_list)

    to_csv_kwargs = {"index": False, "encoding": "utf_8_sig", "line_terminator": "\r\n"}

    annofabcli.utils.print_csv(
        df,
        output=output,
        to_csv_kwargs=to_csv_kwargs,
    )


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    FindBreakError(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument("--threshold", type=int, default=180, help="1履歴、何分以上を検知対象とするか。")
    parser.add_argument(
        "--task_history_event_json",
        type=Path,
        help="タスク履歴イベント全件ファイルのパスを指定してください。"
        "指定しない場合、タスク履歴全件ファイルをダウンロードします。"
        "JSONファイルは ``$ annofabcli project download task_history_event`` コマンドで取得できます。",
    )

    argument_parser.add_output()
    argument_parser.add_task_id(required=False)

    DATETIME_FORMAT = "%%Y-%%m-%%dT%%H:%%i:%%s"
    parser.add_argument(
        "--start_datetime",
        type=str,
        help=f"検索対象の時間を指定します。({DATETIME_FORMAT})",
    )
    parser.add_argument(
        "--end_datetime",
        type=str,
        help="検索対象の時間を指定します。({DATETIME_FORMAT})",
    )
    parser.add_argument("--user_id", type=str, help="ユーザー名")
    parser.add_argument("--phase", type=str, help="phase")
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "find_break_error"
    subcommand_help = "不当に長い作業時間の作業履歴を出力します"
    description = "自動休憩が作動せず不当に長い作業時間になっている履歴をCSV形式で出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
