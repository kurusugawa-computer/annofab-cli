from __future__ import annotations

import argparse
from pathlib import Path

from annofabapi.models import ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.cli import PARALLELISM_CHOICES, ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.task.task_creation import (
    TaskCreatingMain,
    get_task_relation_dict_from_header_csv,
    get_task_relation_dict_from_json_args,
)


class CreateTask(CommandLine):
    def main(self) -> None:
        args = self.args
        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        main_obj = TaskCreatingMain(
            self.service,
            project_id=args.project_id,
            parallelism=args.parallelism,
        )

        if args.csv is not None:
            task_relation_dict = get_task_relation_dict_from_header_csv(args.csv)
        else:
            task_relation_dict = get_task_relation_dict_from_json_args(args.json, command_name="annofabcli task create")

        main_obj.create_task_list(task_relation_dict)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CreateTask(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    file_group = parser.add_mutually_exclusive_group(required=True)
    file_group.add_argument(
        "--csv",
        type=Path,
        help=(
            "タスクに割り当てる入力データが記載されたCSVファイルのパスを指定してください。CSVのフォーマットは、以下の通りです。\n\n * ヘッダ行あり, カンマ区切り\n * 必須列: task_id, input_data_id\n"
        ),
    )

    json_sample = '{"task1":["input1","input2"]}'
    file_group.add_argument(
        "--json",
        type=str,
        help=(
            "タスクに割り当てる入力データをJSON形式で指定してください。"
            "keyがtask_id, valueがinput_data_idのlistです。\n"
            f"(ex) ``{json_sample}`` \n"
            "``file://`` を先頭に付けるとjsonファイルを指定できます。"
        ),
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="並列度。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "create"
    subcommand_help = "タスクを作成します。"
    description = "タスクを作成します。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
