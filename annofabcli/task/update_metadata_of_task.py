from __future__ import annotations

import argparse
import copy
import json
import logging
import multiprocessing
import sys
from dataclasses import dataclass
from functools import partial
from typing import Any, Optional, Union

import annofabapi
from annofabapi.models import ProjectMemberRole

import annofabcli
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

Metadata = dict[str, Union[str, bool, int]]


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
        parallelism: Optional[int] = None,
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
        task_index: Optional[int] = None,
    ) -> bool:
        logging_prefix = f"{task_index + 1} 件目" if task_index is not None else ""
        task = self.service.wrapper.get_task_or_none(project_id, task_id)
        if task is None:
            logger.warning(f"{logging_prefix} タスク '{task_id}' は存在しないのでスキップします。")
            return False

        logger.debug(f"task_id='{task_id}', metadata='{json.dumps(task['metadata'])}'")

        if not self.confirm_processing(self.get_confirm_message(task_id, metadata)):
            return False

        if self.is_overwrite_metadata:
            new_metadata = metadata
        else:
            new_metadata = {**task["metadata"], **metadata}

        request_body = {task_id: new_metadata}
        self.service.api.patch_tasks_metadata(project_id, request_body=request_body)

        logger.debug(f"{logging_prefix} タスク '{task_id}' のメタデータを更新しました。")
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
            metadata_by_task_id = annofabcli.common.cli.get_json_from_args(args.metadata_by_task_id)
            if task_id_list is not None:
                metadata_by_task_id = {task_id: metadata for task_id, metadata in metadata_by_task_id.items() if task_id in task_id_list}
        else:
            raise RuntimeError("'--metadata'か'--metadata_by_task_id'のどちらかを指定する必要があります。")

        super().validate_project(args.project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
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
            "キーがタスクID, 値がメタデータ( ``--metadata`` 参照)であるオブジェクトをJSON形式で指定してください。\n"
            f"(ex) '{json.dumps(sample_metadata_by_task_id)}'\n"
            " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
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


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "update_metadata"
    subcommand_help = "タスクのメタデータを更新します。"
    description = "タスクのメタデータを上書きして更新します。"
    epilog = "オーナまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog)
    parse_args(parser)
    return parser
