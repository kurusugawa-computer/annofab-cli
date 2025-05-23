from __future__ import annotations

import argparse
import copy
import json
import logging
import multiprocessing
import sys
from collections.abc import Collection
from dataclasses import dataclass
from functools import partial
from typing import Optional, Union

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


class DeleteMetadataKeysOfTaskMain(CommandLineWithConfirm):
    def __init__(
        self,
        service: annofabapi.Resource,
        project_id: str,
        *,
        parallelism: Optional[int] = None,
        all_yes: bool = False,
    ) -> None:
        self.service = service
        self.project_id = project_id
        self.parallelism = parallelism
        super().__init__(all_yes=all_yes)

    def delete_metadata_keys_for_one_task(self, task_id: str, metadata_keys: Collection[str], *, task_index: Optional[int] = None) -> bool:
        """
        １個のタスクに対して、メタデータのキーを削除します。

        Args:
            task_id:
            metadata_keys: 削除するメタデータのキー

        Returns:
            メタデータのキーを削除した場合はTrueを返します。
        """
        logging_prefix = f"{task_index + 1} 件目" if task_index is not None else ""
        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"{logging_prefix} task_id='{task_id}'であるタスクは存在しません。")
            return False

        old_metadata = task["metadata"]
        str_old_metadata = json.dumps(old_metadata)

        deleted_keys = set(metadata_keys) & set(old_metadata.keys())  # 削除可能な（存在する）メタデータのキー
        logger.debug(f"{logging_prefix} task_id='{task_id}', metadata='{str_old_metadata}' :: 削除対象のキーが {len(deleted_keys)} 件存在します。")

        new_metadata = copy.deepcopy(old_metadata)
        for key in deleted_keys:
            new_metadata.pop(key, None)

        if len(deleted_keys) == 0:
            # メタデータを更新する必要がないのでreturnします。
            return False

        if not self.all_yes and not self.confirm_processing(f"task_id='{task_id}' :: metadata='{str_old_metadata}' からキー'{deleted_keys}'を削除しますか？"):
            return False

        request_body = {task_id: new_metadata}
        self.service.api.patch_tasks_metadata(self.project_id, request_body=request_body)
        str_new_metadata = json.dumps(new_metadata)
        logger.debug(f"{logging_prefix} task_id='{task_id}' :: タスクのメタデータからキー'{deleted_keys}'を削除しました。 :: metadata='{str_new_metadata}'")
        return True

    def delete_metadata_keys_for_one_task_wrapper(self, tpl: tuple[int, str], metadata_keys: Collection[str]) -> bool:
        task_index, task_id = tpl
        try:
            return self.delete_metadata_keys_for_one_task(
                task_id=task_id,
                metadata_keys=metadata_keys,
                task_index=task_index,
            )
        except Exception:
            logger.warning(f"task_id='{task_id}' :: タスクのメタデータのキーを削除するのに失敗しました。", exc_info=True)
            return False

    def delete_metadata_keys_for_task_list(self, task_id_list: list[str], metadata_keys: Collection[str]) -> None:
        logger.info(f"{len(task_id_list)} 件のタスクのメタデータから、キー'{metadata_keys}'を削除します。")

        success_count = 0
        if self.parallelism is not None:
            assert self.all_yes
            partial_func = partial(
                self.delete_metadata_keys_for_one_task_wrapper,
                metadata_keys=metadata_keys,
            )
            with multiprocessing.Pool(self.parallelism) as pool:
                result_bool_list = pool.map(partial_func, enumerate(task_id_list))
                success_count = len([e for e in result_bool_list if e])

        else:
            # 逐次処理
            for task_index, task_id in enumerate(task_id_list):
                try:
                    result = self.delete_metadata_keys_for_one_task(
                        task_id,
                        metadata_keys=metadata_keys,
                        task_index=task_index,
                    )
                    if result:
                        success_count += 1
                except Exception:
                    logger.warning(f"task_id='{task_id}' :: タスクのメタデータのキーを削除するのに失敗しました。", exc_info=True)
                    continue

        logger.info(f"{success_count} / {len(task_id_list)} 件のタスクのメタデータから、キー'{metadata_keys}'を削除しました。")


class UpdateMetadataOfTask(CommandLine):
    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli task delete_metadata_key: error:"  # noqa: N806

        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{COMMON_MESSAGE} argument --parallelism: '--parallelism' を指定するときは、 '--yes' が必須です。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args

        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        metadata_keys = annofabcli.common.cli.get_list_from_args(args.metadata_key)

        super().validate_project(args.project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
        main_obj = DeleteMetadataKeysOfTaskMain(self.service, project_id=args.project_id, parallelism=args.parallelism, all_yes=args.yes)
        main_obj.delete_metadata_keys_for_task_list(task_id_list=task_id_list, metadata_keys=metadata_keys)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateMetadataOfTask(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    argument_parser.add_task_id(required=True)

    parser.add_argument(
        "--metadata_key",
        type=str,
        required=True,
        nargs="+",
        help="削除したいメタデータのキーを複数指定します。\n``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定します。指定する場合は ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "delete_metadata_key"
    subcommand_help = "タスクのメタデータのキーを削除します。"
    epilog = "オーナまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
