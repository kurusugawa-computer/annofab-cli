import argparse
import datetime
import logging
from typing import Any, Callable, Dict, List, Optional  # pylint: disable=unused-import

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login, ArgumentParser
from annofabcli.future.annofab_api_getter import AnnofabGetter, get_work_time_list
from annofabcli.future.utils import date_range, work_time_list_to_print_time_list,work_time_lists_to_print_time_list

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

        project_ids = list(set(annofabcli.common.cli.get_list_from_args(args.project_ids)))
        start_date = datetime.datetime.strptime(args.start_date, '%Y-%m-%d').date()
        end_date = datetime.datetime.strptime(args.end_date, '%Y-%m-%d').date()
        if len(project_ids) == 1:
            organization_id = self.get_organization_id_from_project_id(project_ids[0])

            annofab_getter = AnnofabGetter(organization_id=organization_id, project_id=project_ids[0], service=self.service)
            work_time_list = get_work_time_list(annofab_getter, start_date, end_date)

            date_list = []
            for date_order in date_range(start_date, end_date):
                date_list.append(date_order)

            print_time_list = work_time_list_to_print_time_list(annofab_getter.get_project_members(), work_time_list,
                                                                date_list)
        else:
            # project_idが複数の場合は合計を出力
            work_time_lists = []
            date_list = []
            project_members = []
            for date_order in date_range(start_date, end_date):
                date_list.append(date_order)

            for project_id in project_ids:
                organization_id = self.get_organization_id_from_project_id(project_id)

                annofab_getter = AnnofabGetter(organization_id=organization_id, project_id=project_id,
                                               service=self.service)

                work_time_list = get_work_time_list(annofab_getter, start_date, end_date)
                work_time_lists.append(work_time_list)
                add_project_members = annofab_getter.get_project_members()
                project_members.extend(add_project_members["list"])


            print_time_list = work_time_lists_to_print_time_list(project_members,
                                                                work_time_lists,
                                                                date_list)
        output_lines: List[str] = []
        output_lines.append(f"Start: , {start_date},  End: , {end_date}")
        output_lines.extend([",".join([str(cell) for cell in row]) for row in print_time_list])
        annofabcli.utils.output_string("\n".join(output_lines), args.output)



def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    ListLaborWorktime(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    parser.add_argument('--project_ids', type=str, required=True, nargs='+', help="対象のタスクのproject_idを指定します。' '`file://`を先頭に付けると、project_idの一覧が記載されたファイルを指定できます。")
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
