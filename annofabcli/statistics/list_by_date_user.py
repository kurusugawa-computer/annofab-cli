import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import annofabapi
import pandas
from annofabapi.models import ProjectMemberRole, TaskHistory, TaskPhase

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile
from annofabcli.common.utils import isoduration_to_hour

logger = logging.getLogger(__name__)


class ListSubmittedTaskCountMain:
    def __init__(self, service: annofabapi.Resource):
        self.service = service
        self.facade = AnnofabApiFacade(service)

    @staticmethod
    def from_datetime_to_date(datetime: str) -> str:
        return datetime[0:10]

    @staticmethod
    def _get_actual_worktime_hour(labor: Dict[str, Any]) -> float:
        working_time_by_user = labor["values"]["working_time_by_user"]
        if working_time_by_user is None:
            return 0

        value = working_time_by_user.get("results")
        if value is None:
            return 0
        else:
            return value / 3600 / 1000

    @staticmethod
    def to_formatted_dataframe(
        submitted_task_count_df: pandas.DataFrame,
        account_statistics_df: pandas.DataFrame,
        labor_df: pandas.DataFrame,
        user_df: pandas.DataFrame,
    ):
        df = (
            submitted_task_count_df.merge(account_statistics_df, how="outer", on=["date", "account_id"])
            .merge(labor_df, how="outer", on=["date", "account_id"])
            .fillna(0)
            .merge(user_df, how="inner", on="account_id")
        )
        df.sort_values(["date", "user_id"], inplace=True)
        columns = [
            "date",
            "user_id",
            "username",
            "biography",
            "monitored_worktime_hour",
            "actual_worktime_hour",
            "annotation_submitted_task_count",
            "inspection_submitted_task_count",
            "acceptance_submitted_task_count",
            "rejected_task_count",
        ]

        return df[columns]

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

        logger.debug(f"タスク履歴全件ファイルを読み込み中。{json_path}")
        with json_path.open(encoding="utf-8") as f:
            task_history_dict = json.load(f)
            return task_history_dict

    def create_user_df(self, project_id: str):
        member_list = self.facade.get_organization_members_from_project_id(project_id)
        return pandas.DataFrame(member_list, columns=["account_id", "user_id", "username", "biography"])

    @staticmethod
    def _is_contained_daterange(target_date: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
        if start_date is not None:
            if target_date < start_date:
                return False
        if end_date is not None:
            if target_date > end_date:
                return False
        return True

    def create_account_statistics_df(
        self, project_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> pandas.DataFrame:
        account_statistics = self.service.wrapper.get_account_statistics(project_id)
        data_list: List[Dict[str, Any]] = []
        for stat_by_user in account_statistics:
            account_id = stat_by_user["account_id"]
            histories = stat_by_user["histories"]
            for stat in histories:
                data = {
                    "account_id": account_id,
                    "monitored_worktime_hour": isoduration_to_hour(stat["worktime"]),
                    "rejected_task_count": stat["tasks_rejected"],
                    "date": stat["date"],
                }
                if not self._is_contained_daterange(data["date"], start_date=start_date, end_date=end_date):
                    continue

                if data["monitored_worktime_hour"] == 0 and data["rejected_task_count"] == 0:
                    continue

                data_list.append(data)

        if len(data_list) > 0:
            return pandas.DataFrame(data_list)
        else:
            return pandas.DataFrame(columns=["date", "account_id", "monitored_worktime_hour", "rejected_task_count"])

    def create_labor_df(
        self, project_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> pandas.DataFrame:
        def to_new_labor(e: Dict[str, Any]) -> Dict[str, Any]:
            return dict(
                date=e["date"],
                account_id=e["account_id"],
                actual_worktime_hour=self._get_actual_worktime_hour(e),
            )

        labor_list: List[Dict[str, Any]] = self.service.api.get_labor_control(
            {"project_id": project_id, "from": start_date, "to": end_date}
        )[0]
        new_labor_list = [
            to_new_labor(e) for e in labor_list if e["account_id"] is not None and self._get_actual_worktime_hour(e) > 0
        ]
        if len(new_labor_list) > 0:
            return pandas.DataFrame(new_labor_list)
        else:
            return pandas.DataFrame(columns=["date", "account_id", "actual_worktime_hour"])

    def create_submitted_task_count_df(
        self,
        task_history_dict: Dict[str, List[TaskHistory]],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pandas.DataFrame:
        def _set_zero_if_not_exists(df: pandas.DataFrame):
            for phase in TaskPhase:
                col = f"{phase.value}_submitted_task_count"
                if col not in df.columns:
                    df[col] = 0

        task_history_count_dict: Dict[Tuple[str, str, str], int] = defaultdict(int)
        for _, task_history_list in task_history_dict.items():
            for task_history in task_history_list:
                if task_history["ended_datetime"] is not None and task_history["account_id"] is not None:
                    ended_date = self.from_datetime_to_date(task_history["ended_datetime"])
                    task_history_count_dict[(task_history["account_id"], task_history["phase"], ended_date)] += 1

        data_list = []
        for key, task_count in task_history_count_dict.items():
            account_id, phaes, date = key
            data: Dict[str, Any] = {"date": date, "phase": phaes, "account_id": account_id, "task_count": task_count}
            if not self._is_contained_daterange(data["date"], start_date=start_date, end_date=end_date):
                continue

            data_list.append(data)

        if len(data_list) == 0:
            return pandas.DataFrame(
                columns=[
                    "date",
                    "account_id",
                    "annotation_submitted_task_count",
                    "inspection_submitted_task_count",
                    "acceptance_submitted_task_count",
                ]
            )

        df = pandas.DataFrame(data_list)
        df2 = df.pivot_table(columns="phase", values="task_count", index=["date", "account_id"]).fillna(0)
        df2.rename(
            columns={
                "annotation": "annotation_submitted_task_count",
                "inspection": "inspection_submitted_task_count",
                "acceptance": "acceptance_submitted_task_count",
            },
            inplace=True,
        )
        _set_zero_if_not_exists(df2)
        return df2

    def create_user_statistics_by_date(
        self,
        project_id: str,
        task_history_json_path: Optional[Path],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pandas.DataFrame:
        task_history_dict = self.get_task_history_dict(project_id, task_history_json_path)

        submitted_task_count_df = self.create_submitted_task_count_df(
            task_history_dict=task_history_dict, start_date=start_date, end_date=end_date
        )
        labor_df = self.create_labor_df(project_id, start_date=start_date, end_date=end_date)
        account_statistics_df = self.create_account_statistics_df(project_id, start_date=start_date, end_date=end_date)
        user_df = self.create_user_df(project_id)

        df2 = self.to_formatted_dataframe(submitted_task_count_df, account_statistics_df, labor_df, user_df)
        return df2


class ListSubmittedTaskCountArgs(AbstractCommandLineInterface):
    def main(self):
        args = self.args

        project_id = args.project_id
        super().validate_project(
            project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER]
        )

        main_obj = ListSubmittedTaskCountMain(service=self.service)
        df = main_obj.create_user_statistics_by_date(
            project_id, args.task_history_json, start_date=args.start_date, end_date=args.end_date
        )
        self.print_csv(df)


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--task_history_json",
        type=Path,
        help="タスク履歴情報が記載されたJSONファイルのパスを指定してます。JSONファイルは`$ annofabcli project download task_history`コマンドで取得できます。"
        "指定しない場合は、AnnoFabからタスク履歴全件ファイルをダウンロードします。",
    )

    parser.add_argument("--start_date", type=str, help="集計対象の開始日(YYYY-mm-dd)")
    parser.add_argument("--end_date", type=str, help="集計対象の終了日(YYYY-mm-dd)")

    argument_parser.add_csv_format()
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListSubmittedTaskCountArgs(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_by_date_user"
    subcommand_help = "タスク数や作業時間などの情報を、日ごとユーザごとに出力します。"
    description = "タスク数や作業時間などの情報を、日ごとユーザごとに出力します。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog
    )
    parse_args(parser)
