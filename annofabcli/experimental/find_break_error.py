import argparse
import csv
import datetime
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import annofabapi
import dateutil.parser
import pandas as pd
import pytz
import requests

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
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


def get_tsv(csv_path: str):
    with Path(csv_path).open("r",) as f:
        reader = csv.reader(f, delimiter="\t")
        return reader


def get_err_task_history_list(tsv_path: str) -> List[Dict[str, Any]]:
    tsv_list = get_tsv(tsv_path)
    err_task_history_list = []
    for tsv_data in tsv_list:
        err_task_history = {}
        err_task_history["project_id"] = tsv_data[0]
        err_task_history["task_id"] = tsv_data[2]
        err_task_history["started_datetime"] = tsv_data[7]
        err_task_history["ended_datetime"] = tsv_data[8]
        err_task_history["modified_value"] = tsv_data[11]
        err_task_history_list.append(err_task_history)

    return err_task_history_list


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
        member = self.facade.get_organization_member_from_account_id(project_id, account_id)
        if member is not None:
            return member["username"]
        else:
            return account_id

    def _project_task_history_events(
        self, project_id: str, import_file_path: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        タスク履歴イベント全件ファイルを取得する。
        import_fileがNone:history_events_urlパスから直接読み込む
        import_fileがNoneではない:import_fileで指定されたファイルから読み込む
        """
        project_task_history_events: Dict[str, Any]
        if import_file_path is None:
            content, _ = self.service.wrapper.api.get_project_task_histories_url(project_id=project_id)
            url = content["url"]
            try:
                history_events = download_content(url)
            except requests.HTTPError:
                # TODO:全件JSONは今のところ30日で消える仕様の回避
                logger.warning(f"プロジェクトの停止から30日以上が経過しているため検索対象外になります project_id:{project_id}")
                return None
            project_task_history_events = json.loads(history_events)

        else:
            history_events = read_lines_except_blank_line(import_file_path)
            project_task_history_events = json.loads(history_events[0])

        return project_task_history_events

    def get_err_events(
        self, task_history_events: Dict[str, List[Dict[str, Any]]], err_task_history_list: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        しきい値以上の作業時間になっている開始と終了のhistory_eventsのペアを返す
        """

        def check_applicable_time(task_history: Dict[str, Any], err_task_history_list: List[Dict[str, Any]]):
            # project_id,task_id,timeが検索対象と合致しているかを探す
            for err_task_history in err_task_history_list:
                if (
                    task_history["project_id"] == err_task_history["project_id"]
                    and task_history["task_id"] == err_task_history["task_id"]
                ):
                    err_task_history_started_datetime = dateutil.parser.parse(
                        err_task_history["started_datetime"]
                    ).strftime("%Y-%m-%d %H:%M:%S")
                    if err_task_history["ended_datetime"]:
                        err_task_history_ended_datetime = dateutil.parser.parse(
                            err_task_history["ended_datetime"]
                        ).strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        err_task_history_ended_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    task_history_started_datetime = dateutil.parser.parse(task_history["started_datetime"]).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    if task_history["ended_datetime"]:
                        task_history_ended_datetime = dateutil.parser.parse(task_history["ended_datetime"]).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    else:
                        task_history_ended_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    if (
                        err_task_history_started_datetime == task_history_started_datetime
                        or err_task_history_ended_datetime == task_history_ended_datetime
                    ):
                        task_history["modified_value"] = err_task_history["modified_value"]
                        task_history["modified_ended_datetime"] = (
                            dateutil.parser.parse(task_history["started_datetime"])
                            + datetime.timedelta(minutes=int(err_task_history["modified_value"]))
                            if not err_task_history["modified_value"] == ""
                            else ""
                        )
                        return True

            return False

        def check_period(task_history, start_date, end_date):
            if not task_history["ended_datetime"]:
                return False

            task_history_started_datetime = dateutil.parser.parse(task_history["started_datetime"])
            task_history_ended_datetime = dateutil.parser.parse(task_history["ended_datetime"])

            jp = pytz.timezone("Asia/Tokyo")

            started_datetime = jp.localize(dateutil.parser.parse(start_date))
            ended_datetime = jp.localize(dateutil.parser.parse(end_date))

            return (
                task_history_started_datetime >= started_datetime and task_history_started_datetime <= ended_datetime
            ) or (task_history_ended_datetime >= started_datetime and task_history_ended_datetime <= ended_datetime)

        err_events_list = []
        for task_history_event in task_history_events.values():
            for task_history in task_history_event:
                if check_applicable_time(task_history, err_task_history_list):
                    task_history["user_name"] = self._get_username(
                        task_history["project_id"], task_history["account_id"]
                    )
                    task_history["project_title"] = self.facade.get_project_title(task_history["project_id"])
                    err_events_list.append(task_history)
                elif annofabcli.common.utils.isoduration_to_minute(
                    task_history["accumulated_labor_time_milliseconds"]
                ) >= self.args.threshold and check_period(task_history, self.args.start_date, self.args.end_date):
                    task_history["modified_ended_datetime"] = ""
                    task_history["modified_value"] = ""
                    task_history["user_name"] = self._get_username(
                        task_history["project_id"], task_history["account_id"]
                    )
                    task_history["project_title"] = self.facade.get_project_title(task_history["project_id"])
                    err_events_list.append(task_history)
                else:
                    continue

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
            if not Path(args.err_file_path).is_file():
                print(
                    f"{COMMON_MESSAGE} argument --err_file_path: ファイルパスが存在しません\
                    '{args.err_file_path}'",
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
            # timeとしきい値絞り込み
            err_events.extend(
                self.get_err_events(
                    task_history_events=task_history_events,
                    err_task_history_list=get_err_task_history_list(args.err_file_path) if args.err_file_path else [],
                )
            )

        output_err_events(err_events_list=err_events, output=self.output)


def output_err_events(err_events_list: List[Dict[str, Any]], output: str = None):
    """
    開始と終了のhistory_eventsのペアから出力する
    :param err_events_list:
    :param output:
    :return:
    """

    if not err_events_list:
        logger.warning("err_historyが見つからなかった為、出力しません。")
        return

    df = pd.DataFrame(err_events_list)
    to_csv_kwargs = {"index": False, "encoding": "utf_8_sig", "line_terminator": "\r\n", "sep": "\t"}

    annofabcli.utils.print_csv(
        df[
            [
                "project_id",
                "project_title",
                "task_id",
                "task_history_id",
                "phase",
                "phase_stage",
                "user_name",
                "started_datetime",
                "ended_datetime",
                "accumulated_labor_time_milliseconds",
                "modified_ended_datetime",
                "modified_value",
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

    parser.add_argument("--threshold", type=int, default=180, help="1履歴何分以上を検知対象とするか。指定しない場合は300分(5時間)")
    parser.add_argument("--start_date", type=str, required=True, help="集計開始日(YYYY-mm-dd)")
    parser.add_argument("--end_date", type=str, required=True, help="集計終了日(YYYY-mm-dd)")
    parser.add_argument("--import_file_path", type=str, help="importするタスク履歴イベント全件ファイル,指定しない場合はタスク履歴イベント全件を新規取得する")
    parser.add_argument("--err_file_path", type=str, help="errの一覧のファイルpath")

    argument_parser.add_output()
    parser.add_argument(
        "-p",
        "--project_id",
        type=str,
        required=True,
        nargs="+",
        help="対象のプロジェクトのproject_idを指定します。複数指定可" "`file://`を先頭に付けると、project_idの一覧が記載されたファイルを指定できます。",
    )
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "found_break_error"
    subcommand_help = "不当に長い作業時間の作業履歴を出力します"
    description = "自動休憩が作動せず不当に長い作業時間になっている履歴を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
