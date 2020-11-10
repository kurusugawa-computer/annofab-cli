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


class LaborTimePerUser(AbstractCommandLineInterface):
    """
    メンバ別の作業時間を出力する。
    """

    def get_labor_time_per_user(self, project_id: str) -> List[Dict[str, Any]]:
        """
        メンバ別の作業時間をCSVに出力するための dict 配列を作成する。

        Args:
            project_id:

        Returns:
            メンバ別の作業時間をCSVに出力するための dict 配列

        """
        account_statistics = self.service.wrapper.get_account_statistics(project_id)
        row_list: List[Dict[str, Any]] = []
        for stat_by_user in account_statistics:
            account_id = stat_by_user["account_id"]
            member = self.facade.get_project_member_from_account_id(project_id, account_id)

            histories = stat_by_user["histories"]
            for stat in histories:
                stat["account_id"] = account_id
                stat["user_id"] = member["user_id"] if member is not None else None
                stat["username"] = member["username"] if member is not None else None
                stat["biography"] = member["biography"] if member is not None else None
                stat["worktime_hour"] = isoduration_to_hour(stat["worktime"])

            row_list.extend(histories)
        return row_list

    def list_cumulative_labor_time(self, project_id: str) -> None:
        super().validate_project(project_id, project_member_roles=None)

        account_stat_list = self.get_labor_time_per_user(project_id)
        df = pandas.DataFrame(account_stat_list)
        if len(df) > 0:
            # 出力対象の列を指定する
            target_df = df[
                [
                    "date",
                    "account_id",
                    "user_id",
                    "username",
                    "biography",
                    "worktime_hour",
                    "tasks_completed",
                    "tasks_rejected",
                ]
            ]
            annofabcli.utils.print_csv(target_df, output=self.output, to_csv_kwargs=self.csv_format)
        else:
            logger.error(f"出力対象データが0件のため、出力しません。")

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
    LaborTimePerUser(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_labor_time_per_user"
    subcommand_help = "メンバ別の作業時間、完了数、差し戻し回数を出力する。"
    description = "メンバ別の作業時間、完了数、差し戻し回数をCSV形式で出力する。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
