from __future__ import annotations

import argparse
import copy
import json
import logging
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
from annofabcli.common.task_metadata import (
    UpdateMetadataOfTaskMain,
)

logger = logging.getLogger(__name__)

DEPRECATED_METADATA_BY_TASK_ID_MESSAGE = (
    "[DEPRECATED] :: '--metadata_by_task_id' は非推奨です。代わりに `task update_metadata_per_task --json` を使用してください。 '--metadata_by_task_id' オプションは2027/01/01以降に廃止予定です。"
)


class UpdateMetadataOfTask(CommandLine):
    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli task update_metadata: error:"  # noqa: N806

        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{COMMON_MESSAGE} argument --parallelism: '--parallelism' を指定するときは、 '--yes' が必須です。",
                file=sys.stderr,
            )
            return False

        if args.metadata is not None and args.task_id is None:
            print(  # noqa: T201
                f"{COMMON_MESSAGE} argument --task_id: '--metadata' を指定するときは、 '--task_id' が必須です。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args

        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None

        if args.metadata is not None:
            metadata = annofabcli.common.cli.get_json_from_args(args.metadata)
            assert task_id_list is not None, "'--metadata'を指定したときは'--task_id'は必須です。"
            metadata_by_task_id = {task_id: copy.deepcopy(metadata) for task_id in task_id_list}
        elif args.metadata_by_task_id is not None:
            logger.warning(DEPRECATED_METADATA_BY_TASK_ID_MESSAGE)
            metadata_by_task_id = annofabcli.common.cli.get_json_from_args(args.metadata_by_task_id)
            if task_id_list is not None:
                metadata_by_task_id = {task_id: metadata for task_id, metadata in metadata_by_task_id.items() if task_id in task_id_list}
        else:
            raise RuntimeError("'--metadata'か'--metadata_by_task_id'のどちらかを指定する必要があります。")

        super().require_project_access(args.project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
        main_obj = UpdateMetadataOfTaskMain(self.service, is_overwrite_metadata=args.overwrite, parallelism=args.parallelism, all_yes=args.yes)
        main_obj.update_metadata_of_task(args.project_id, metadata_by_task_id=metadata_by_task_id)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateMetadataOfTask(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    argument_parser.add_task_id(required=False)

    metadata_group_parser = parser.add_mutually_exclusive_group(required=True)
    metadata_group_parser.add_argument(
        "--metadata",
        type=str,
        help="タスクに設定する ``metadata`` をJSON形式で指定してください。メタデータの値には文字列、数値、真偽値のいずれかを指定してください。"
        " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
    )

    sample_metadata_by_task_id = {"task1": {"priority": 2}}
    metadata_group_parser.add_argument(
        "--metadata_by_task_id",
        type=str,
        help=(
            "[DEPRECATED] キーがタスクID, 値がメタデータ( ``--metadata`` 参照)であるオブジェクトをJSON形式で指定してください。\n"
            "代わりに ``task update_metadata_per_task --json`` を使用してください。\n"
            "このオプションは2027/01/01以降に廃止予定です。\n"
            f"(ex) '{json.dumps(sample_metadata_by_task_id)}'\n"
            "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="指定した場合、メタデータを上書きして更新します（すでに設定されているメタデータは削除されます）。指定しない場合、 ``--metadata`` に指定されたキーのみ更新されます。 ``--yes`` と一緒に指定すると、処理時間は大幅に短くなります。",  # noqa: E501
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "update_metadata"
    subcommand_help = "タスクのメタデータを更新します。"
    description = "タスクのメタデータの指定したキーのみ更新します。--overwriteを指定するとメタデータ全体を置き換えます。"
    epilog = "オーナまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog)
    parse_args(parser)
    return parser
