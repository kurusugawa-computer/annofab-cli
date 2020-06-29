import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas
from annofabapi.models import ProjectMemberRole, TaskHistory, TaskPhase

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile

logger = logging.getLogger(__name__)


def from_datetime_to_date(datetime: str) -> str:
    return datetime[0:10]


def to_formatted_dataframe(df: pandas.DataFrame):
    def get_phase_list(columns):
        print(columns)
        phase_list = []
        for phase in TaskPhase:
            str_phase = phase.value
            if str_phase in columns:
                phase_list.append(str_phase)
        return phase_list

    user_df = df.groupby("account_id").first()[["user_id", "username", "biography"]]
    df2 = df.pivot_table(columns="phase", values="task_count", index=["date", "account_id"]).fillna(0)
    df3 = df2.join(user_df, how="left").reset_index()
    df3.rename(
        columns={
            "annotation": "annotation_task_count",
            "inspection": "inspection_task_count",
            "acceptance": "acceptance_task_count",
        },
        inplace=True,
    )
    df3.sort_values(["date", "user_id"], inplace=True)

    phase_list = get_phase_list(df2.columns)
    columns = ["date", "account_id", "user_id", "username", "biography"] + [
        f"{phase}_task_count" for phase in phase_list
    ]
    return df3[columns]


class ListSubmittedTaskCount(AbstractCommandLineInterface):
    def get_task_history_dict(
        self, project_id: str, task_history_json_path: Optional[Path]
    ) -> Dict[str, List[TaskHistory]]:
        if task_history_json_path is not None:
            json_path = task_history_json_path
        else:
            cache_dir = annofabcli.utils.get_cache_dir()
            json_path = cache_dir / f"task-history-{project_id}.json"
            downloading_obj = DownloadingFile(self.service)
            downloading_obj.download_task_history_json(project_id, dest_path=str(json_path))

        with json_path.open(encoding="utf-8") as f:
            task_history_dict = json.load(f)
            return task_history_dict

    def create_submitted_task_count_df(
        self, project_id: str, task_history_dict: Dict[str, List[TaskHistory]]
    ) -> pandas.DataFrame:
        task_history_count_dict: Dict[Tuple[str, str, str], int] = defaultdict(int)
        for _, task_history_list in task_history_dict.items():
            for task_history in task_history_list:
                if task_history["ended_datetime"] is not None and task_history["account_id"] is not None:
                    ended_date = from_datetime_to_date(task_history["ended_datetime"])
                    task_history_count_dict[(task_history["account_id"], task_history["phase"], ended_date)] += 1

        data_list = []
        for key, task_count in task_history_count_dict.items():
            account_id, phaes, date = key
            member = self.facade.get_organization_member_from_account_id(project_id, account_id)
            data: Dict[str, Any] = {"date": date, "phase": phaes, "account_id": account_id}
            if member is not None:
                data.update(
                    {
                        "user_id": member["user_id"],
                        "username": member["username"],
                        "biography": member["biography"],
                        "task_count": task_count,
                    }
                )
            else:
                data.update({"user_id": None, "username": None, "biography": None})

            data_list.append(data)

        return pandas.DataFrame(data_list)

    def main(self):
        args = self.args

        project_id = args.project_id
        super().validate_project(
            project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER]
        )

        task_history_dict = self.get_task_history_dict(project_id, args.task_history_json)
        df = self.create_submitted_task_count_df(project_id, task_history_dict=task_history_dict)
        df2 = to_formatted_dataframe(df)
        self.print_csv(df2)


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--task_history_json",
        type=Path,
        help="タスク履歴情報が記載されたJSONファイルのパスを指定してます。JSONファイルは`$ annofabcli project download task_history`コマンドで取得できます。"
        "指定しない場合は、AnnoFabからタスク履歴全件ファイルをダウンロードします。",
    )

    argument_parser.add_csv_format()
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListSubmittedTaskCount(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_submitted_task_count"
    subcommand_help = "提出したタスク数/合格にしたタスク数/差し戻したタスク数を出力します。"
    description = "日ごと、ユーザごとに、提出したタスク数（教師付フェーズ）/合格にしたタスク数（検査・受入フェーズ）/ 差し戻したタスク数を出力します。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog
    )
    parse_args(parser)
