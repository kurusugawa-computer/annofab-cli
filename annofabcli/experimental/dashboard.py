import argparse
import datetime
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List

import dateutil
import pandas
from annofabapi.models import ProjectMemberRole, Task
from dataclasses_json import dataclass_json
from dateutil.parser import parse

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
from annofabcli.common.enums import FormatArgument
from annofabcli.statistics.summarize_task_count_by_task_id import TaskStatusForSummary

logger = logging.getLogger(__name__)

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)


@dataclass_json
@dataclass
class TaskCount:
    """
    フェーズごとのタスク数
    """

    complete: int = 0
    """完了状態のタスク数"""

    annotation_not_started: int = 0
    """一度も教師付作業されていないタスク数"""

    inspection_not_started: int = 0
    """一度も検査作業されていないタスク数"""

    acceptance_not_started: int = 0
    """一度も受入作業されていないタスク数"""

    on_hold: int = 0
    """保留状態のタスク数"""

    other: int = 0
    """休憩中/作業中/2回目以降の各フェーズの未着手状態のタスク数"""


def add_info_to_task(task: Task):
    task["status_for_summary"] = TaskStatusForSummary.from_task(task).value


def get_task_count_info_from_task_list(task_list: List[Task]) -> TaskCount:
    """
    状態ごとのタスク数を取得する。

    Args:
        task_list:

    Returns:

    """
    status_list: List[str] = [e["status_for_summary"] for e in task_list]
    tmp = pandas.Series.value_counts(status_list)
    task_count = TaskCount.from_dict(tmp.to_dict())  # type: ignore
    return task_count


def _to_datetime_from_date(date: datetime.date) -> datetime.datetime:
    dt = datetime.datetime.combine(date, datetime.datetime.min.time())
    return dt.replace(tzinfo=dateutil.tz.tzlocal())


def millisecond_to_hour(millisecond: int):
    return millisecond / 1000 / 3600


def get_task_list_where_updated_datetime(
    task_list: List[Task], lower_date: datetime.date, upper_date: datetime.date
) -> List[Task]:
    """
    タスクの更新日が、対象期間内であるタスク一覧を取得する。

    Args:
        task_list:
        lower_date:
        upper_date:

    Returns:

    """

    def pred(task):
        updated_datetime = parse(task["updated_datetime"])
        return lower_datetime <= updated_datetime < upper_datetime

    lower_datetime = _to_datetime_from_date(lower_date)
    upper_datetime = _to_datetime_from_date(upper_date + datetime.timedelta(days=1))
    return [t for t in task_list if pred(t)]


def create_task_count_info(task_list: List[Task], date: datetime.date) -> Dict[str, Any]:
    """
    タスク数情報を生成する。

    Args:
        task_list:
        date: タスク数　集計対象日

    Returns:

    """
    for task in task_list:
        task["status_for_summary"] = TaskStatusForSummary.from_task(task).value
        task["worktime_hour"] = millisecond_to_hour(task["work_time_span"])

    cumulation_task_count = get_task_count_info_from_task_list(task_list)
    result = {
        "cumulation": {
            "task_count": cumulation_task_count.to_dict(),  # type: ignore
            "monitored_worktime": sum([t["worktime_hour"] for t in task_list]),
        }
    }
    if date is not None:
        task_list_for_day = get_task_list_where_updated_datetime(task_list, lower_date=date, upper_date=date)
        result["today"] = {
            "task_count": get_task_count_info_from_task_list(task_list_for_day).to_dict()  # type: ignore
        }

        week_ago = date - datetime.timedelta(days=7)
        task_list_for_week = get_task_list_where_updated_datetime(task_list, lower_date=week_ago, upper_date=date)
        result["7days"] = {
            "task_count": get_task_count_info_from_task_list(  # type: ignore
                task_list_for_week
            ).to_dict()
        }

    return result


class DashBoard(AbstractCommandLineInterface):
    def print_summarize_task_count(self, target_dict: dict) -> None:
        annofabcli.utils.print_according_to_format(
            target_dict, arg_format=FormatArgument.JSON, output=self.output,
        )

    def main(self):
        args = self.args
        project_id = args.project_id
        project_title = self.facade.get_project_title(project_id)
        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        if args.task_json is not None:
            task_json_path = args.task_json
        else:
            wait_options = get_wait_options_from_args(get_json_from_args(args.wait_options), DEFAULT_WAIT_OPTIONS)
            cache_dir = annofabcli.utils.get_cache_dir()
            task_json_path = cache_dir / f"{project_id}-task.json"

            downloading_obj = DownloadingFile(self.service)
            downloading_obj.download_task_json(
                project_id, dest_path=str(task_json_path), is_latest=args.latest, wait_options=wait_options
            )

        with open(task_json_path, encoding="utf-8") as f:
            task_list = json.load(f)

        dt_date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()

        dashboard_info = {
            "project_id": project_id,
            "project_title": project_title,
            "date": args.date,
        }
        task_count_info = create_task_count_info(task_list, date=dt_date)
        dashboard_info.update(task_count_info)
        annofabcli.utils.print_according_to_format(
            dashboard_info, arg_format=FormatArgument(self.str_format), output=self.output,
        )


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    parser.add_argument(
        "--task_json",
        type=str,
        help="タスク情報が記載されたJSONファイルのパスを指定してます。JSONファイルは`$ annofabcli project download task`コマンドで取得できます。"
        "指定しない場合は、AnnoFabからタスク全件ファイルをダウンロードします。",
    )

    parser.add_argument("--date", type=str, required=True, help="`YYYY-MM-DD`形式で実績の対象日を指定してください。")

    parser.add_argument(
        "--latest", action="store_true", help="最新のタスク一覧ファイルを参照します。このオプションを指定すると、タスク一覧ファイルを更新するのに数分待ちます。"
    )

    parser.add_argument(
        "--wait_options",
        type=str,
        help="タスク一覧ファイルの更新が完了するまで待つ際のオプションを、JSON形式で指定してください。"
        "`file://`を先頭に付けるとjsonファイルを指定できます。"
        'デフォルは`{"interval":60, "max_tries":360}` です。'
        "`interval`:完了したかを問い合わせる間隔[秒], "
        "`max_tires`:完了したかの問い合わせを最大何回行うか。",
    )

    argument_parser.add_format([FormatArgument.PRETTY_JSON, FormatArgument.JSON], default=FormatArgument.PRETTY_JSON)
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DashBoard(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "dashboard"
    subcommand_help = "ダッシュボードとなる情報（タスク数など）をJSON形式で出力します。"
    description = "ダッシュボードとなる情報（タスク数など）をJSON形式で出力します。"
    epilog = "オーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog
    )
    parse_args(parser)
