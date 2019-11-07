import argparse
import datetime
import logging
from argparse import ArgumentParser
from typing import Any, Callable, Dict, List, Optional  # pylint: disable=unused-import

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.future.annofab_api_getter import AnnofabGetter, get_work_time_list
from annofabcli.future.utils import date_range, print_time_list_csv, work_time_list_to_print_time_list

logger = logging.getLogger(__name__)


class ListLaborWorktime(AbstractCommandLineInterface):
    """
    労務管理画面の作業時間を出力する
    """
    def get_organization_id_from_project_id(self, project_id: str) -> str:
        organization, _ = self.service.api.get_organization_of_project(project_id)
        return organization["organization_id"]

    def main(self) -> None:
        args = self.args

        project_id = args.project_id
        organization_id = self.get_organization_id_from_project_id(project_id)

        annofab_getter = AnnofabGetter(organization_id=organization_id, project_id=project_id, service=self.service)
        start_date = datetime.datetime.strptime(args.start_date, '%Y-%m-%d').date()
        end_date = datetime.datetime.strptime(args.end_date, '%Y-%m-%d').date()

        work_time_list = get_work_time_list(annofab_getter, start_date, end_date)

        date_list = []
        for date_order in date_range(start_date, end_date):
            date_list.append(date_order)

        print_time_list = work_time_list_to_print_time_list(annofab_getter.get_project_members(), work_time_list,
                                                            date_list)

        output_lines: List[str] = []
        output_lines.append(f"Start: , {start_date},  End: , {end_date}")
        output_lines.extend(
            [",".join(e) for e in print_time_list]
        )
        annofabcli.utils.output_string("\n".join(output_lines), args.output)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    ListLaborWorktime(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    parser = ArgumentParser(allow_abbrev=False)
    argument_parser.add_project_id()

    parser.add_argument("--start_date", type=str, required=True, help="集計開始日(%%Y-%%m-%%d)")
    parser.add_argument("--end_date", type=str, required=True, help="集計終了日(%%Y-%%m-%%d)")

    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_labor_worktime"
    subcommand_help = "労務管理画面の作業時間を出力します。"
    description = ("作業者ごとに、「作業者が入力した実績時間」と「AnnoFabが集計した作業時間」の差分を出力します。")

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
