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


def get_err_history_events(
    task_history_events: List[Dict[str, Any]], task_id_list: List[str]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    対象のtask_idが含まれるhistory_eventsを返す
    """
    err_history_events_dict: Dict[str, List[Dict[str, Any]]] = {}

    for task_history_event in task_history_events:
        if task_id_list:
            if task_history_event["task_id"] in task_id_list:
                if task_history_event["task_id"] in err_history_events_dict:
                    err_history_events_dict[task_history_event["task_id"]].append(task_history_event)
                else:
                    err_history_events_dict[task_history_event["task_id"]] = [task_history_event]
        else:
            if task_history_event["task_id"] in err_history_events_dict:
                err_history_events_dict[task_history_event["task_id"]].append(task_history_event)
            else:
                err_history_events_dict[task_history_event["task_id"]] = [task_history_event]

    return err_history_events_dict


class FindBreakError(AbstractCommandLineInterface):
    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        project_id_list = get_list_from_args(args.project_id)
        self.project_id_list = list(set(project_id_list))

    def _get_username(self, project_id: str, account_id: str) -> Optional[str]:
        """
        プロジェクトメンバのusernameを取得する。プロジェクトメンバでなければ、account_idを返す。
        account_idがNoneならばNoneを返す。
        """
        member = self.facade.get_project_member_from_account_id(project_id, account_id)
        if member is not None:
            return member["username"]
        else:
            return account_id

    def _get_all_tasks(self, project_id: str, task_query: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        task一覧を取得する
        """
        tasks = self.service.wrapper.get_all_tasks(project_id, query_params=task_query)
        return tasks

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

    def get_err_events(
        self, err_history_events: Dict[str, List[Dict[str, Any]]], time_list: List[str]
    ) -> List[List[Dict[str, Any]]]:
        """
        しきい値以上の作業時間になっている開始と終了のhistory_eventsのペアを返す
        """

        def check_applicable_time(
            from_time: datetime.datetime, to_time: datetime.datetime, date_time_list: List[datetime.datetime]
        ):
            # timeが検索対象と合致しているかを探す
            from_time = dateutil.parser.parse(from_time.strftime("%Y-%m-%d %H:%M:%S"))
            to_time = dateutil.parser.parse(to_time.strftime("%Y-%m-%d %H:%M:%S"))

            if date_time_list:
                for date_time in date_time_list:
                    date_time = dateutil.parser.parse(date_time.strftime("%Y-%m-%d %H:%M:%S"))
                    if date_time in [from_time, to_time]:
                        return True
            else:
                return True
            return False

        err_events_list = []
        date_time_list = [dateutil.parser.parse(time) for time in time_list]
        for v in err_history_events.values():
            v.sort(key=lambda x: x["created_datetime"])
            for i, history_events in enumerate(v):
                if history_events["status"] == "working":
                    if len(v) == i + 1:
                        continue
                    next_history_events = v[i + 1]
                    if next_history_events["status"] in ["on_hold", "break", "complete"]:
                        next_time = dateutil.parser.parse(next_history_events["created_datetime"])
                        this_time = dateutil.parser.parse(history_events["created_datetime"])
                        working_time = next_time - this_time
                        if working_time > datetime.timedelta(
                            minutes=self.args.task_history_time_threshold
                        ) and check_applicable_time(this_time, next_time, date_time_list):
                            history_events["user_name"] = self._get_username(
                                history_events["project_id"], history_events["account_id"]
                            )
                            next_history_events["user_name"] = self._get_username(
                                history_events["project_id"], history_events["account_id"]
                            )
                            history_events["project_title"] = self.facade.get_project_title(
                                history_events["project_id"]
                            )
                            next_history_events["project_title"] = self.facade.get_project_title(
                                history_events["project_id"]
                            )
                            err_events_list.append([history_events, next_history_events])
        return err_events_list

    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli experimental find_break_error: error:"
        if args.import_file_path is not None:
            if not Path(args.import_file_path).is_file():
                print(
                    f"{COMMON_MESSAGE} argument --import_file_path: ファイルパスが存在しません\
                '{args.import_file_path}'",
                    file=sys.stderr,
                )
                return False
        project_id_list = get_list_from_args(args.project_id)
        if len(project_id_list) > 1 and args.task_id:
            print(
                f"{COMMON_MESSAGE} argument --project_id: task_idを指定した場合はproject_idは複数指定できません\
                            '{args.project_id}'",
                file=sys.stderr,
            )
            return False
        if args.task_id and len(args.task_id) > 1 and args.time:
            print(
                f"{COMMON_MESSAGE} argument --task_id: timeを指定した場合はtask_idは複数指定できません\
                            '{args.project_id}'",
                file=sys.stderr,
            )
            return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            return

        err_events = []
        for project_id in args.project_id:
            task_history_events = self._project_task_history_events(
                project_id=project_id, import_file_path=args.import_file_path
            )
            if not task_history_events:
                # 全件ファイルの更新に失敗したらスルー
                continue
            # task_id 絞り込み
            err_history_events = get_err_history_events(
                task_history_events=task_history_events, task_id_list=args.task_id if args.task_id else []
            )
            # timeとしきい値絞り込み
            err_events.extend(
                self.get_err_events(err_history_events=err_history_events, time_list=args.time if args.time else [])
            )

        output_err_events(err_events_list=err_events, output=self.output, add=args.add)


def output_err_events(err_events_list: List[List[Dict[str, Any]]], output: str = None, add: bool = False):
    """
    開始と終了のhistory_eventsのペアから出力する
    :param err_events_list:
    :param output:
    :return:
    """

    def _timedelta_to_HM(td: datetime.timedelta):
        sec = td.total_seconds()
        return str(round(sec // 3600)) + "時間" + str(round(sec % 3600 // 60)) + "分"

    data_list = []
    for i, data in enumerate(err_events_list):
        start_data, end_data = data
        start_time = dateutil.parser.parse(start_data["created_datetime"])
        end_time = dateutil.parser.parse(end_data["created_datetime"])
        start_data["datetime"] = start_time.isoformat()
        end_data["datetime"] = end_time.isoformat()
        start_data["working_time"] = ""
        end_data["working_time"] = _timedelta_to_HM(end_time - start_time)

        df = pd.DataFrame([start_data, end_data])
        df["no"] = i + 1

        del df["phase_stage"]
        del df["account_id"]
        del df["created_datetime"]
        data_list.append(df)

    if not data_list:
        logger.warning("historyが見つからなかった為、出力しません。")
        return
    elif len(data_list) == 1:
        pd_data = data_list[0]
    else:
        pd_data = pd.concat(data_list)

    if add:
        to_csv_kwargs = {
            "index": False,
            "mode": "a",
            "header": False,
            "encoding": "utf_8_sig",
            "line_terminator": "\r\n",
        }
    else:
        to_csv_kwargs = {"index": False, "encoding": "utf_8_sig", "line_terminator": "\r\n"}

    annofabcli.utils.print_csv(
        pd_data[
            [
                "no",
                "project_title",
                "project_id",
                "task_id",
                "user_name",
                "phase",
                "status",
                "datetime",
                "task_history_id",
                "working_time",
            ]
        ],
        output=output,
        to_csv_kwargs=to_csv_kwargs,
    )


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    FindBreakError(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    parser.add_argument("--task_history_time_threshold", type=int, default=180, help="1履歴、何分以上を検知対象とするか。")
    parser.add_argument("--import_file_path", type=str, help="importするタスク履歴イベント全件ファイル,指定しない場合はタスク履歴イベント全件を新規取得する")

    argument_parser.add_output()
    parser.add_argument(
        "-p",
        "--project_id",
        type=str,
        required=True,
        nargs="+",
        help="対象のプロジェクトのproject_idを指定します。複数指定可、但しtask_idを指定した場合は1つしか指定できません。"
        "`file://`を先頭に付けると、project_idの一覧が記載されたファイルを指定できます。",
    )
    parser.add_argument(
        "-t",
        "--task_id",
        type=str,
        nargs="+",
        help="対象のプロジェクトのtask_idを指定します。複数指定可、但しtimeを指定した場合は1つしか指定できません。"
        "`file://`を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )
    parser.add_argument(
        "--time",
        type=str,
        nargs="+",
        help="検索対象の時間を指定します。(%%Y/%%m/%%d %%H:%%i:%%s)",
    )
    parser.add_argument("--add", action="store_true", help="出力する際に追記で書き込む")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "found_break_error"
    subcommand_help = "不当に長い作業時間の作業履歴を出力します"
    description = "自動休憩が作動せず不当に長い作業時間になっている履歴を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
