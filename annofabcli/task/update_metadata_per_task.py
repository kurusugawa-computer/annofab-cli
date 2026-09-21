from __future__ import annotations

import argparse
import json
import sys

from annofabapi.models import ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.task.update_metadata_of_task import Metadata, UpdateMetadataOfTaskMain


class UpdateMetadataPerTask(CommandLine):
    """タスクごとに指定したメタデータを更新する。"""

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                "annofabcli task update_metadata_per_task: error: argument --parallelism: '--parallelism' を指定するときは、 '--yes' が必須です。",
                file=sys.stderr,
            )
            return False
        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        metadata_by_task_id: dict[str, Metadata] = annofabcli.common.cli.get_json_from_args(args.json)
        super().validate_project(args.project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
        main_obj = UpdateMetadataOfTaskMain(self.service, is_overwrite_metadata=args.overwrite, parallelism=args.parallelism, all_yes=args.yes)
        main_obj.update_metadata_of_task(args.project_id, metadata_by_task_id=metadata_by_task_id)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateMetadataPerTask(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    sample_json = {"task1": {"priority": 2}}
    parser.add_argument(
        "--json",
        type=str,
        required=True,
        help=(
            "キーがタスクID、値が設定するメタデータであるオブジェクトをJSON形式で指定してください。"
            "メタデータの値には文字列、数値、真偽値のいずれかを指定できます。\n"
            f"(ex) '{json.dumps(sample_json)}'\n"
            "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "指定した場合、メタデータを上書きして更新します（すでに設定されているメタデータは削除されます）。"
            "指定しない場合、JSONに指定されたキーのみ更新されます。 ``--yes`` と一緒に指定すると、処理時間は大幅に短くなります。"
        ),
    )
    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "update_metadata_per_task"
    subcommand_help = "タスクごとにメタデータを更新します。"
    description = "タスクごとに指定したメタデータを更新します。"
    epilog = "オーナまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog)
    parse_args(parser)
    return parser
