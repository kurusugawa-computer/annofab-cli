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
from annofabcli.task.update_metadata_of_task import TaskMetadataInfo, UpdateMetadataOfTaskMain


def get_task_metadata_info_list_from_json_args(json_value: str) -> list[TaskMetadataInfo]:
    """JSON引数からタスクごとのメタデータ更新情報を取得します。

    Args:
        json_value: ``task list --format json`` と同じ形式のJSON文字列、またはJSONファイルのパス

    Returns:
        タスクごとのメタデータ更新情報

    Raises:
        TypeError: JSONの形式が不正な場合
        ValueError: task_idが重複している場合
    """

    task_list = annofabcli.common.cli.get_json_from_args(json_value)
    if not isinstance(task_list, list):
        raise TypeError("配列を指定してください。")

    result: list[TaskMetadataInfo] = []
    task_id_set: set[str] = set()
    for index, task in enumerate(task_list, start=1):
        if not isinstance(task, dict):
            raise TypeError(f"{index}番目の要素にはオブジェクトを指定してください。")

        try:
            task_id = task["task_id"]
            metadata = task["metadata"]
        except KeyError as e:
            raise TypeError(f"{index}番目の要素には 'task_id' と 'metadata' キーを指定してください。") from e

        if not isinstance(task_id, str):
            raise TypeError(f"{index}番目の要素の'task_id'には文字列を指定してください。")
        if not isinstance(metadata, dict):
            raise TypeError(f"{index}番目の要素の'metadata'にはオブジェクトを指定してください。")
        if task_id in task_id_set:
            raise ValueError(f"{index}番目の要素の'task_id'が重複しています。 :: task_id='{task_id}'")

        task_id_set.add(task_id)
        result.append(TaskMetadataInfo(task_id=task_id, metadata=metadata))

    return result


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

        metadata_info_list = get_task_metadata_info_list_from_json_args(args.json)
        metadata_by_task_id = {info.task_id: info.metadata for info in metadata_info_list}
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

    sample_json = [{"task_id": "task1", "metadata": {"priority": 2}}]
    parser.add_argument(
        "--json",
        type=str,
        required=True,
        help=(
            "``task list --format json`` と同じ形式のJSON配列を指定してください。"
            "各要素の ``task_id`` と ``metadata`` キーを参照し、それ以外のキーは無視します。"
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
