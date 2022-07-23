import argparse
import sys
from typing import List, Optional

import annofabapi

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery


class ChangeStatusMain:
    def __init__(self, service: annofabapi.Resource, all_yes: bool):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.all_yes = all_yes

    def change_status(
        self,
        project_id: str,
        task_id_list: List[str],
        task_query: Optional[TaskQuery] = None,
        parallelism: Optional[int] = None,
    ):
        print(1)


class ChangeStatus(AbstractCommandLineInterface):
    """
    作業中のタスクの状態を変更する。
    """

    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli task change_status: error:"

        if args.parallelism is not None and not args.yes:
            print(
                f"{COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず ``--yes`` を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

        dict_task_query = annofabcli.common.cli.get_json_from_args(args.task_query)
        task_query: Optional[TaskQuery] = TaskQuery.from_dict(dict_task_query) if dict_task_query is not None else None

        project_id = args.project_id

        main_obj = ChangeStatusMain(self.service, all_yes=self.all_yes)
        main_obj.change_status(
            project_id,
            task_id_list=task_id_list,
            task_query=task_query,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeStatus(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    status_group = parser.add_mutually_exclusive_group(required=True)

    status_group.add_argument("--to_break", action="store_true", help="タスクのステータスを休憩中に変更します。")

    status_group.add_argument("--to_on_hold", action="store_true", help="タスクのステータスを保留中に変更します。")

    argument_parser.add_task_query()

    parser.add_argument(
        "--parallelism", type=int, help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "change_status"
    subcommand_help = "タスクの状態を変更します。"
    description = "タスクの状態を作業中から休憩中、または保留中に変更します。"
    epilog = ""

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
