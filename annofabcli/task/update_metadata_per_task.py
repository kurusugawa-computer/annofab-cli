from __future__ import annotations

import argparse
import json
import logging
import multiprocessing
import sys
from dataclasses import dataclass
from functools import partial
from typing import Any

import annofabapi
from annofabapi.models import ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)

Metadata = dict[str, str | bool | int]


@dataclass(frozen=True)
class TaskMetadataInfo:
    task_id: str
    metadata: Metadata


class UpdateMetadataOfTaskMain(CommandLineWithConfirm):
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        is_overwrite_metadata: bool,
        parallelism: int | None = None,
        all_yes: bool = False,
    ) -> None:
        self.service = service
        self.is_overwrite_metadata = is_overwrite_metadata
        self.parallelism = parallelism
        CommandLineWithConfirm.__init__(self, all_yes)

    def get_confirm_message(self, task_id: str, metadata: dict[str, Any]) -> str:
        if self.is_overwrite_metadata:
            return f"タスク '{task_id}' のメタデータを '{json.dumps(metadata)}' に変更しますか？ "
        else:
            return f"タスク '{task_id}' のメタデータに '{json.dumps(metadata)}' を追加しますか？ "

    def set_metadata_to_task(
        self,
        project_id: str,
        task_id: str,
        metadata: dict[str, Any],
        task_index: int | None = None,
    ) -> bool:
        logging_prefix = f"{task_index + 1} 件目" if task_index is not None else ""
        logging_prefix += f" task_id='{task_id}' :: "
        task = self.service.wrapper.get_task_or_none(project_id, task_id)
        if task is None:
            logger.warning(f"{logging_prefix}タスクは存在しないのでスキップします。")
            return False

        logger.debug(f"{logging_prefix}現在のmetadata='{json.dumps(task['metadata'])}'")

        if not self.confirm_processing(self.get_confirm_message(task_id, metadata)):
            return False

        if self.is_overwrite_metadata:
            new_metadata = metadata
        else:
            new_metadata = {**task["metadata"], **metadata}

        request_body = {task_id: new_metadata}
        self.service.api.patch_tasks_metadata(project_id, request_body=request_body)

        logger.debug(f"{logging_prefix}タスクのメタデータを更新しました。 :: 新しいmetadata={json.dumps(new_metadata)}")
        return True

    def set_metadata_to_task_wrapper(self, tpl: tuple[int, TaskMetadataInfo], project_id: str) -> bool:
        task_index, info = tpl
        try:
            return self.set_metadata_to_task(
                project_id,
                info.task_id,
                metadata=info.metadata,
                task_index=task_index,
            )
        except Exception:
            logger.warning(f"タスク'{info.task_id}'のメタデータの更新に失敗しました。", exc_info=True)
            return False

    def _update_metadata_with_patch_tasks_metadata_api_wrapper(self, tpl: tuple[int, int, list[TaskMetadataInfo]], project_id: str) -> None:
        global_start_position, global_stop_position, info_list = tpl
        logger.debug(f"{global_start_position + 1} 〜 {global_stop_position} 件目のタスクのメタデータを更新します。")
        request_body = {info.task_id: info.metadata for info in info_list}
        self.service.api.patch_tasks_metadata(project_id, request_body=request_body)

    def update_metadata_with_patch_tasks_metadata_api(self, project_id: str, metadata_by_task_id: dict[str, Metadata]) -> None:
        """patch_tasks_metadata webapiを呼び出して、タスクのメタデータを更新します。
        注意：メタデータは上書きされます。
        """

        # 1000件以上の大量のタスクを一度に更新しようとするとwebapiが失敗するので、何回かに分けてメタデータを更新するようにする。
        BATCH_SIZE = 500  # noqa: N806
        first_index = 0

        metadata_info_list = [TaskMetadataInfo(task_id, metadata) for task_id, metadata in metadata_by_task_id.items()]

        if self.parallelism is None:
            while first_index < len(metadata_info_list):
                logger.info(f"{first_index + 1} 〜 {min(first_index + BATCH_SIZE, len(metadata_info_list))} 件目のタスクのメタデータを更新します。")
                request_body = {info.task_id: info.metadata for info in metadata_info_list[first_index : first_index + BATCH_SIZE]}
                self.service.api.patch_tasks_metadata(project_id, request_body=request_body)
                first_index += BATCH_SIZE
        else:
            partial_func = partial(
                self._update_metadata_with_patch_tasks_metadata_api_wrapper,
                project_id=project_id,
            )
            tmp_list = []
            while first_index < len(metadata_info_list):
                global_start_position = first_index
                global_stop_position = min(first_index + BATCH_SIZE, len(metadata_info_list))
                subset_info_list = metadata_info_list[global_start_position:global_stop_position]
                tmp_list.append((global_start_position, global_stop_position, subset_info_list))
                first_index += BATCH_SIZE

            with multiprocessing.Pool(self.parallelism) as pool:
                pool.map(partial_func, tmp_list)

    def update_metadata_of_task(
        self,
        project_id: str,
        metadata_by_task_id: dict[str, Metadata],
    ) -> None:
        if self.is_overwrite_metadata:
            logger.info(f"{len(metadata_by_task_id)} 件のタスクのメタデータを変更します（上書き）。")
        else:
            logger.info(f"{len(metadata_by_task_id)} 件のタスクのメタデータを変更します（追記）。")

        if self.is_overwrite_metadata and self.all_yes:
            self.update_metadata_with_patch_tasks_metadata_api(project_id, metadata_by_task_id)
            logger.info(f"{len(metadata_by_task_id)} 件のタスクのメタデータを変更しました。")
        else:
            success_count = 0
            if self.parallelism is not None:
                partial_func = partial(
                    self.set_metadata_to_task_wrapper,
                    project_id=project_id,
                )
                metadata_info_list = [TaskMetadataInfo(task_id, metadata) for task_id, metadata in metadata_by_task_id.items()]
                with multiprocessing.Pool(self.parallelism) as pool:
                    result_bool_list = pool.map(partial_func, enumerate(metadata_info_list))
                    success_count = len([e for e in result_bool_list if e])

            else:
                # 逐次処理
                for task_index, (task_id, metadata) in enumerate(metadata_by_task_id.items()):
                    try:
                        result = self.set_metadata_to_task(
                            project_id,
                            task_id,
                            metadata=metadata,
                            task_index=task_index,
                        )
                        if result:
                            success_count += 1
                    except Exception:
                        logger.warning(f"タスク'{task_id}'のメタデータの更新に失敗しました。", exc_info=True)
                        continue

            logger.info(f"{success_count} / {len(metadata_by_task_id)} 件のタスクのメタデータを変更しました。")


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
        super().require_project_access(args.project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
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


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "update_metadata_per_task"
    subcommand_help = "タスクごとにメタデータを更新します。"
    description = "タスクごとに指定したメタデータを更新します。"
    epilog = "オーナまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.create_parser(subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog)
    parse_args(parser)
    return parser
