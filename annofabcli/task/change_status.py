import argparse
from typing import Optional

import annofabcli
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade


class ChangeStatus(AbstractCommandLineInterface):
    def main(self):
        print(1)


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
    description = "タスクの状態を変更します。"
    epilog = ""

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
