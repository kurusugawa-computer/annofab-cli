import argparse
import json
import logging
from typing import List

import pandas
from annofabapi.models import ProjectMemberRole, Task, TaskStatus

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

logger = logging.getLogger(__name__)

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)


def get_task_id_prefix(task_id: str):
    tmp_list = task_id.split("_")
    if len(tmp_list) <= 1:
        return "unknown"
    else:
        return "_".join(tmp_list[0 : len(tmp_list) - 1])


def add_task_id_prefix_to_task_list(task_list: List[Task]) -> List[Task]:
    for task in task_list:
        task["task_id_prefix"] = get_task_id_prefix(task["task_id"])
    return task_list


def create_task_count_summary_df(task_list: List[Task]) -> pandas.DataFrame:
    """
    タスク数を集計したDataFrameを生成する。

    Args:
        task_list:

    Returns:

    """

    def add_columns_if_not_exists(df: pandas.DataFrame, column: str):
        if column not in df.columns:
            df[column] = 0

    df_task = pandas.DataFrame(add_task_id_prefix_to_task_list(task_list))

    df_summary = df_task.pivot_table(
        values="task_id", index=["task_id_prefix"], columns=["status"], aggfunc="count", fill_value=0
    ).reset_index()

    for status in [
        TaskStatus.COMPLETE,
        TaskStatus.NOT_STARTED,
        TaskStatus.ON_HOLD,
        TaskStatus.BREAK,
        TaskStatus.WORKING,
    ]:
        add_columns_if_not_exists(df_summary, status.value)

    df_summary["working_break_not_started"] = df_summary["working"] + df_summary["break"] + df_summary["not_started"]
    df_summary["sum"] = (
        df_task.pivot_table(values="task_id", index=["task_id_prefix"], aggfunc="count", fill_value=0)
        .reset_index()
        .fillna(0)["task_id"]
    )

    return df_summary


class SummarizeTaskCountByTaskId(AbstractCommandLineInterface):
    def print_summarize_task_count(self, df: pandas.DataFrame) -> None:
        columns = ["task_id_prefix", "complete", "on_hold", "working_break_not_started", "sum"]
        annofabcli.utils.print_according_to_format(
            df[columns], arg_format=FormatArgument(FormatArgument.CSV), output=self.output, csv_format=self.csv_format,
        )

    def main(self):
        args = self.args
        project_id = args.project_id
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

        df = create_task_count_summary_df(task_list)
        self.print_summarize_task_count(df)


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    parser.add_argument(
        "--task_json",
        type=str,
        help="タスク情報が記載されたJSONファイルのパスを指定してます。JSONファイルは`$ annofabcli project download task`コマンドで取得できます。"
        "指定しない場合は、AnnoFabからタスク全件ファイルをダウンロードします。",
    )

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

    argument_parser.add_csv_format()
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    SummarizeTaskCountByTaskId(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "summarize_task_count_by_task_id"
    subcommand_help = "task_idのプレフィックスごとにタスク数を出力します。"
    description = "task_idのプレフィックスごとにタスク数をCSV形式で出力します。"
    epilog = "オーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog
    )
    parse_args(parser)
