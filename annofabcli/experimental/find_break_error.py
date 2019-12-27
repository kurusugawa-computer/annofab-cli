import argparse
import datetime
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple  # pylint: disable=unused-import

import annofabapi
import dateutil.parser
import pandas as pd
import requests

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.utils import read_lines_except_blank_line

logger = logging.getLogger(__name__)


def download_content(url: str) -> Any:
    """
    HTTP GETで取得した内容を保存せずそのまま返す

    Args:
        url: ダウンロード対象のURL
    """
    response = requests.get(url)
    annofabapi.utils.raise_for_status(response)
    return response.content


def get_err_history_events(task_list: List[str], task_history_events: List[Dict[str, Any]]) \
        -> Dict[str, List[Dict[str, Any]]]:
    """
    しきい値以上のタスクリストのtask_idが含まれるhistory_eventsを返す
    """
    err_history_events_dict: Dict[str, List[Dict[str, Any]]] = {}
    for task_history_event in task_history_events:
        if task_history_event["task_id"] in task_list:
            if task_history_event["task_id"] in err_history_events_dict:
                err_history_events_dict[task_history_event["task_id"]].append(task_history_event)
            else:
                err_history_events_dict[task_history_event["task_id"]] = [task_history_event]
    return err_history_events_dict


class FindBreakError(AbstractCommandLineInterface):

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.project_id = args.project_id

    def _get_username(self, account_id: Optional[str]) -> Optional[str]:
        """
        プロジェクトメンバのusernameを取得する。プロジェクトメンバでなければ、account_idを返す。
        account_idがNoneならばNoneを返す。
        """
        if account_id is None:
            return None

        member = self.facade.get_organization_member_from_account_id(self.project_id, account_id)
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

    def _project_task_history_events(self, project_id: str, import_file_path: Optional[str] = None) \
            -> List[Dict[str, Any]]:
        """
        タスク履歴イベント全件ファイルを取得する。
        import_fileがNone:history_events_urlパスから直接読み込む
        import_fileがNoneではない:import_fileで指定されたファイルから読み込む
        """
        project_task_history_events: List[Dict[str, Any]] = []
        if import_file_path is None:
            content, _ = self.service.wrapper.api.get_project_task_history_events_url(project_id=project_id)
            url = content["url"]
            history_events = download_content(url)
            project_task_history_events = json.loads(history_events)

        else:
            history_events = read_lines_except_blank_line(import_file_path)
            project_task_history_events = json.loads(history_events[0])

        return project_task_history_events

    def found_err_task(self, tasks: List[Dict[str, Any]]) -> List[str]:
        """
        タスクリストから作業時間合計がしきい値以上のタスクだけを返す
        """
        return [task["task_id"] for task in tasks if task["work_time_span"] > (self.args.task_time_threshold * 60000)]

    def get_err_events(self, err_history_events: Dict[str, List[Dict[str, Any]]]):
        """
        しきい値以上の作業時間になっている開始と終了のhistory_eventsのペアを返す
        """
        err_events_list = []
        for v in err_history_events.values():
            v.sort(key=lambda x: x["created_datetime"])
            for i, history_events in enumerate(v):
                if history_events["status"] == "working":
                    if v[i + 1]["status"] in ["on_hold", "break", "complete"]:
                        working_time = dateutil.parser.parse(v[i + 1]["created_datetime"]) - dateutil.parser.parse(
                            history_events["created_datetime"])
                        if working_time > datetime.timedelta(minutes=self.args.task_history_time_threshold):
                            err_events_list.append((history_events, v[i + 1]))
        return err_events_list

    def output_err_events(self, err_events_list: List[Tuple[Dict[str, Any], Dict[str, Any]]], output: str = None):
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
            username = self._get_username(start_data["account_id"])
            start_data["user_name"] = "" if username is None else username
            end_data["user_name"] = "" if username is None else username
            start_time = dateutil.parser.parse(start_data["created_datetime"])
            end_time = dateutil.parser.parse(end_data["created_datetime"])
            start_data["datetime"] = start_time.isoformat()
            end_data["datetime"] = end_time.isoformat()
            start_data["working_time"] = ""
            end_data["working_time"] = \
                _timedelta_to_HM(end_time - start_time)

            df = pd.DataFrame([start_data, end_data])
            df["no"] = i + 1

            del df["project_id"]
            del df["phase_stage"]
            del df["account_id"]
            del df["created_datetime"]
            data_list.append(df)

        pd_data = pd.concat(data_list)
        pd_data.set_index(["no", "task_id"])

        annofabcli.utils.print_csv(
            pd_data[["no", "task_id", "user_name", "phase", "status", "datetime", "task_history_id", "working_time"]],
            output=output,
            to_csv_kwargs={"index": False})

    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli experimental find_break_error: error:"
        if args.import_file_path is not None:
            if not Path(args.import_file_path).is_file():
                print(f"{COMMON_MESSAGE} argument --import_file_path: ファイルパスが存在しません。 '{args.import_file_path}'",
                      file=sys.stderr)
                return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            return

        tasks = self._get_all_tasks(project_id=args.project_id)
        task_history_events = self._project_task_history_events(project_id=args.project_id,
                                                                import_file_path=args.import_file_path)
        err_task_list = self.found_err_task(tasks)
        err_history_events = get_err_history_events(task_list=err_task_list,
                                                    task_history_events=task_history_events)
        err_events = self.get_err_events(err_history_events=err_history_events)
        self.output_err_events(err_events_list=err_events, output=self.output)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    FindBreakError(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    parser.add_argument('--task_time_threshold', type=int, default=600,
                        help="1タスク何分以上を検知対象とするか。指定しない場合は600分(10時間)")
    parser.add_argument('--task_history_time_threshold', type=int, default=300,
                        help="1履歴何分以上を検知対象とするか。指定しない場合は300分(5時間)")
    parser.add_argument('--import_file_path', type=str,
                        help="importするタスク履歴イベント全件ファイル,指定しない場合はタスク履歴イベント全件を新規取得する")

    argument_parser.add_output()
    argument_parser.add_project_id()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "found_break_error"
    subcommand_help = "不当に長い作業時間の作業履歴を出力します"
    description = ("自動休憩が作動せず不当に長い作業時間になっている履歴を出力します。")

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
