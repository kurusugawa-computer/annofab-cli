from __future__ import annotations

import argparse
import sys
from pathlib import Path

from annofabapi.models import ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.cli import PARALLELISM_CHOICES, ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.task.task_creation import (
    ApiWithCreatingTask,
    TaskCreatingMain,
    get_task_relation_dict_from_headerless_csv,
    get_task_relation_dict_from_json_args,
)

DEPRECATED_MESSAGE = "[DEPRECATED] :: `task put` コマンドは非推奨です。代わりに `task create` コマンドを使用してください。 `task put` コマンドは2027年01月01日以降に廃止予定です。"


class PutTask(CommandLine):
    def main(self) -> None:
        args = self.args
        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        api_with_creating_task = ApiWithCreatingTask(args.api) if args.api is not None else None
        main_obj = TaskCreatingMain(
            self.service,
            project_id=args.project_id,
            parallelism=args.parallelism,
            should_wait=args.wait,
        )

        if args.csv is not None:
            task_relation_dict = get_task_relation_dict_from_headerless_csv(args.csv)
        else:
            task_relation_dict = get_task_relation_dict_from_json_args(args.json, command_name="annofabcli task put")

        main_obj.generate_task(api_with_creating_task, task_relation_dict)


def print_deprecated_message() -> None:
    """`task put` の非推奨メッセージを標準エラー出力に出力する。"""

    print(DEPRECATED_MESSAGE, file=sys.stderr)  # noqa: T201


def main(args: argparse.Namespace) -> None:
    print_deprecated_message()
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PutTask(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    file_group = parser.add_mutually_exclusive_group(required=True)
    file_group.add_argument(
        "--csv",
        type=Path,
        help=(
            "タスクに割り当てる入力データが記載されたCSVファイルのパスを指定してください。"
            "CSVのフォーマットは、以下の通りです。"
            "タスク作成画面でアップロードするCSVと同じフォーマットです。\n"
            "\n"
            " * ヘッダ行なし, カンマ区切り\n"
            " * 1列目: task_id\n"
            " * 2列目: input_data_id\n"
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
        "--api",
        type=str,
        choices=[e.value for e in ApiWithCreatingTask],
        help="タスク作成に使うWebAPIを指定できます。未指定の場合は、作成するタスク数に応じて適切なWebAPIを選択します。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="並列度。指定しない場合は、逐次的に処理します。``put_task`` WebAPIを使うときのみ有効なオプションです。",
    )

    parser.add_argument(
        "--wait",
        action="store_true",
        help="タスク登録ジョブが終了するまで待ちます。``initiate_tasks_generation`` WebAPIを使うときのみ有効なオプションです。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "put"
    subcommand_help = "[DEPRECATED] タスクを作成します。"
    description = f"{subcommand_help}\n`task put` コマンドは非推奨です。代わりに `task create` コマンドを使用してください。 `task put` コマンドは2027年01月01日以降に廃止予定です。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
