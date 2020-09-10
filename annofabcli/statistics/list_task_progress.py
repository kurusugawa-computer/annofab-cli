import argparse
import logging
from typing import Any, Dict, List

import pandas

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class TaskProgress(AbstractCommandLineInterface):
    """
    タスクの進捗状況を出力する。
    """

    def get_task_statistics(self, project_id: str) -> List[Dict[str, Any]]:
        """
        タスクの進捗状況をCSVに出力するための dict 配列を作成する。

        Args:
            project_id:

        Returns:
            タスクの進捗状況に対応するdict配列

        """
        task_statistics = self.service.wrapper.get_task_statistics(project_id)
        row_list: List[Dict[str, Any]] = []
        for stat_by_date in task_statistics:
            date = stat_by_date["date"]
            task_stat_list = stat_by_date["tasks"]
            for task_stat in task_stat_list:
                task_stat["date"] = date
            row_list.extend(task_stat_list)
        return row_list

    def list_task_progress(self, project_id: str) -> None:
        super().validate_project(project_id, project_member_roles=None)

        task_stat_list = self.get_task_statistics(project_id)
        if len(task_stat_list) == 0:
            logger.info(f"タスクの進捗状況の情報がないため、出力しません。")
            return

        df = pandas.DataFrame(task_stat_list)
        # 出力対象の列を指定する
        target_df = df[["date", "phase", "status", "count"]]

        annofabcli.utils.print_csv(target_df, output=self.output, to_csv_kwargs=self.csv_format)

    def main(self):
        args = self.args

        project_id = args.project_id
        self.list_task_progress(project_id)


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
    subcommand_name = "list_task_progress"
    subcommand_help = "タスク進捗情報を出力する"
    description = "タスク進捗状況をCSV形式で出力する。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
