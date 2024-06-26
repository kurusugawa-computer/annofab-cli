import argparse
import logging
from typing import Any, Dict, List, Optional

import annofabapi
import pandas

import annofabcli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class ListTaskCreationHistoryMain:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)

    def get_data_list(self, project_id: str) -> List[Dict[str, Any]]:
        def create_elm(job: Dict[str, Any]) -> Dict[str, Any]:
            job_detail = job["job_detail"]
            return {
                "project_id": job["project_id"],
                "job_id": job["job_id"],
                "job_status": job["job_status"],
                "generated_task_count": job_detail["generated_task_count"],
                "created_datetime": job["created_datetime"],
                "updated_datetime": job["updated_datetime"],
                "task_generated_rule": job_detail["request"]["task_generate_rule"],
            }

        query_params = {"type": "gen-tasks"}
        job_list = self.service.wrapper.get_all_project_job(project_id, query_params=query_params)
        return [create_elm(job) for job in job_list]


class ListTaskCreationHistory(CommandLine):
    def main(self) -> None:
        args = self.args
        main_obj = ListTaskCreationHistoryMain(self.service)
        data_list = main_obj.get_data_list(args.project_id)

        if args.format == FormatArgument.CSV.value:
            data_list = self.search_with_jmespath_expression(data_list)
            df = pandas.DataFrame(data_list)
            self.print_csv(df)
        else:
            self.print_according_to_format(data_list)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListTaskCreationHistory(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    argument_parser.add_format(choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON], default=FormatArgument.CSV)
    argument_parser.add_output()
    argument_parser.add_csv_format()

    argument_parser.add_query()
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_task_creation_history"
    subcommand_help = "タスクの作成履歴一覧を出力します。"
    description = "タスクの作成履歴一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
