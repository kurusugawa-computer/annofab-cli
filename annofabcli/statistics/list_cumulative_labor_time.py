import argparse
import logging
from typing import Any, Dict, List

import pandas

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.utils import isoduration_to_hour

logger = logging.getLogger(__name__)


class TaskProgress(AbstractCommandLineInterface):
    """
    タスクフェーズ別の累積作業時間を出力する。
    """

    def get_task_phase_statistics(self, project_id: str) -> List[Dict[str, Any]]:
        """
        フェーズごとの累積作業時間をCSVに出力するための dict 配列を作成する。

        Args:
            project_id:

        Returns:
            フェーズごとの累積作業時間に対応するdict配列

        """
        task_phase_statistics = self.service.wrapper.get_task_phase_statistics(project_id)
        row_list: List[Dict[str, Any]] = []
        for stat_by_date in task_phase_statistics:
            date = stat_by_date["date"]
            phase_stat_list = stat_by_date["phases"]
            for phase_stat in phase_stat_list:
                phase_stat["date"] = date
                phase_stat["worktime_hour"] = isoduration_to_hour(phase_stat["worktime"])
            row_list.extend(phase_stat_list)
        return row_list

    def list_cumulative_labor_time(self, project_id: str) -> None:
        super().validate_project(project_id, project_member_roles=None)

        phase_stat_list = self.get_task_phase_statistics(project_id)
        if len(phase_stat_list) == 0:
            logger.info("タスクフェーズ別の累積作業時間情報がないため出力しません。")
            return

        df = pandas.DataFrame(phase_stat_list)
        # 出力対象の列を指定する
        target_df = df[["date", "phase", "worktime_hour"]]
        annofabcli.utils.print_csv(target_df, output=self.output, to_csv_kwargs=self.csv_format)

    def main(self):
        args = self.args

        project_id = args.project_id
        self.list_cumulative_labor_time(project_id)


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_csv_format()
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    TaskProgress(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_cumulative_labor_time"
    subcommand_help = "日ごとタスクフェーズごとの累積作業時間を出力する。"
    description = "日ごとタスクフェーズごとの累積作業時間をCSV形式で出力する。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
