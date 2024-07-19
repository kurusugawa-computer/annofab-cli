from __future__ import annotations

import argparse
import json
import logging
import multiprocessing
import sys
from dataclasses import dataclass
from functools import partial
from typing import Any, Dict, Optional, Union

import annofabapi
from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
)
from typing import Collection
import copy
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)

Metadata = Dict[str, Union[str, bool, int]]


@dataclass(frozen=True)
class TaskMetadataInfo:
    task_id: str
    metadata: Metadata


class UpdateMetadataOfTaskMain(CommandLineWithConfirm):
    def __init__(
        self,
        service: annofabapi.Resource,
        project_id:str,
        *,
        parallelism: Optional[int] = None,
        all_yes: bool = False,
    ) -> None:
        self.service = service
        self.project_id = project_id
        self.parallelism = parallelism
        self.__init__(self, all_yes)


    def delete_metadata_keys_for_one_task(self, task_id:list[str], metadata_keys:Collection[str]) -> Metadata:
        """
        １個のタスクに対して、メタデータのキーを削除します。
        
        Args:
            task_id: 
            metadata_keys: 削除するメタデータのキー
            
        Returns:
            メタデータのキーを削除した場合はTrueを返します。
        """
        logging_prefix = ""
        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"task_id='{task_id}'であるタスクは存在しません。")
            return False
        
        old_metadata = task["metadata"]
        str_old_metadata = json.dumps(old_metadata)
        logger.debug(f"task_id='{task_id}', metadata='{str_old_metadata}'")
        new_metadata = copy.deepcopy(old_metadata)
        for key in metadata_keys:
            new_metadata.pop(key, None)
        
        if new_metadata == old_metadata:
            # メタデータを更新する必要がないのでreturnします。
            return False

        if not self.all_yes and not self.confirm_processing(f"task_id='{task_id}' :: metadata='{str_old_metadata}' からキー'{metadata_keys}'を削除しますか？"):
            return False

        request_body = {task_id: new_metadata}
        self.service.api.patch_tasks_metadata(project_id, request_body=request_body)
        logger.debug(f"{logging_prefix} task_id='{task_id}' :: タスクのメタデータからキー'{metadata_keys}'を削除しました。")
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
        logger.debug(f"{global_start_position+1} 〜 {global_stop_position} 件目のタスクのメタデータを更新します。")
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
                logger.info(f"{first_index+1} 〜 {min(first_index+BATCH_SIZE, len(metadata_info_list))} 件目のタスクのメタデータを更新します。")
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

    def delete_metadata_keys(
        self,
        project_id: str,
        task_id_list:list[str], metadata_keys:Collection[str]
    ) -> None:

        logger.info(f"{len(task_id_list)} 件のタスクのメタデータから、キー'{metadata_keys}'を削除します。")

        if self.all_yes:
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
            metadata_by_task_id = {task_id: metadata for task_id in task_id_list}
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

    parser.add_argument(
        "--metadata_key",
        type=str,
        required=True,
        nargs="+",
        help="削除したいメタデータのキーを複数指定します。\n"
        " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
    )


    parser.add_argument(
        "--parallelism",
        type=int,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",  # noqa: E501
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "delete_metadata_key"
    subcommand_help = "タスクのメタデータのキーを削除します。"
    epilog = "オーナまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
