from __future__ import annotations

import argparse
import logging
import multiprocessing
import sys
from functools import partial
from typing import Any, Collection, Dict, Optional, Union

import annofabapi
from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    AbstractCommandLineWithConfirmInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
)

logger = logging.getLogger(__name__)

Metadata = Dict[str, Union[str, bool, int]]


class UpdateMetadataOfTaskMain(AbstractCommandLineWithConfirmInterface):
    def __init__(
        self,
        service: annofabapi.Resource,
        is_overwrite_metadata: bool,
        parallelism: Optional[int] = None,
        all_yes: bool = False,
    ):
        self.service = service
        self.is_overwrite_metadata = is_overwrite_metadata
        self.parallelism = parallelism
        AbstractCommandLineWithConfirmInterface.__init__(self, all_yes)

    def get_confirm_message(self, task_id: str, metadata: dict[str, Any]) -> str:
        if self.is_overwrite_metadata:
            return f"タスク '{task_id}' のメタデータを '{metadata}' に変更しますか？ "
        else:
            return f"タスク '{task_id}' のメタデータに '{metadata}' を追加しますか？ "

    def set_metadata_to_task(
        self,
        project_id: str,
        task_id: str,
        metadata: Dict[str, Any],
        task_index: Optional[int] = None,
    ) -> bool:
        logging_prefix = f"{task_index+1} 件目" if task_index is not None else ""

        task = self.service.wrapper.get_task_or_none(project_id, task_id)
        if task is None:
            logger.warning(f"{logging_prefix} タスク '{task_id}' は存在しないのでスキップします。")
            return False

        logger.debug(f"task_id: {task_id}, metadata='{task['metadata']}'")

        if not self.confirm_processing(self.get_confirm_message(task_id, metadata)):
            return False

        task["last_updated_datetime"] = task["updated_datetime"]
        if self.is_overwrite_metadata:
            task["metadata"] = metadata
        else:
            task["metadata"].update(metadata)

        self.service.api.put_task(project_id, task_id, request_body=task)
        logger.debug(f"{logging_prefix} タスク '{task_id}' のメタデータを更新しました。")
        return True

    def set_metadata_to_task_wrapper(self, tpl: tuple[int, str], project_id: str, metadata: Dict[str, Any]):
        task_index, task_id = tpl
        return self.set_metadata_to_task(
            project_id,
            task_id,
            metadata=metadata,
            task_index=task_index,
        )

    def update_metadata_of_task(
        self,
        project_id: str,
        task_ids: Collection[str],
        metadata: Dict[str, Any],
    ):
        if self.is_overwrite_metadata:
            logger.info(f"{len(task_ids)} 件のタスクのメタデータを、{metadata} に変更します（上書き）。")
        else:
            logger.info(f"{len(task_ids)} 件のタスクのメタデータに、{metadata} を追加します。")

        if self.is_overwrite_metadata and self.all_yes:
            self.update_metadata_with_patch_tasks_metadata_api(project_id, task_ids=task_ids, metadata=metadata)
        else:
            success_count = 0
            if self.parallelism is not None:
                partial_func = partial(
                    self.set_metadata_to_task_wrapper,
                    project_id=project_id,
                    metadata=metadata,
                )
                with multiprocessing.Pool(self.parallelism) as pool:
                    result_bool_list = pool.map(partial_func, enumerate(task_ids))
                    success_count = len([e for e in result_bool_list if e])

            else:
                # 逐次処理
                for task_index, task_id in enumerate(task_ids):
                    result = self.set_metadata_to_task(
                        project_id,
                        task_id,
                        metadata=metadata,
                        task_index=task_index,
                    )
                    if result:
                        success_count += 1

            logger.info(f"{success_count} / {len(task_ids)} 件のタスクのmetadataを変更しました。")

    def update_metadata_with_patch_tasks_metadata_api_wrapper(
        self, tpl: tuple[int, int, list[str]], project_id: str, metadata: Metadata
    ):
        global_start_position, global_stop_position, task_id_list = tpl
        logger.debug(f"{global_start_position+1} 〜 {global_stop_position} 件目のタスクのmetadataを更新します。")
        request_body = {task_id: metadata for task_id in task_id_list}
        self.service.api.patch_tasks_metadata(project_id, request_body=request_body)

    def update_metadata_with_patch_tasks_metadata_api(
        self, project_id: str, task_ids: Collection[str], metadata: Metadata
    ):
        """patch_tasks_metadata webapiを呼び出して、タスクのメタデータを更新します。
        注意：メタデータは上書きされます。
        """

        # 1000件以上の大量のタスクを一度に更新しようとするとwebapiが失敗するので、何回かに分けてメタデータを更新するようにする。
        BATCH_SIZE = 500
        logger.info(f"{len(task_ids)} 件のタスクのmetadataを{metadata} に、{BATCH_SIZE}個ずつ変更します。")
        first_index = 0
        task_id_list = list(task_ids)

        if self.parallelism is None:
            while first_index < len(task_id_list):
                logger.info(
                    f"{first_index+1} 〜 {min(first_index+BATCH_SIZE, len(task_id_list))} 件目のタスクのmetadataを更新します。"
                )
                request_body = {task_id: metadata for task_id in task_id_list[first_index : first_index + BATCH_SIZE]}
                self.service.api.patch_tasks_metadata(project_id, request_body=request_body)
                first_index += BATCH_SIZE
        else:
            partial_func = partial(
                self.update_metadata_with_patch_tasks_metadata_api_wrapper,
                project_id=project_id,
                metadata=metadata,
            )
            tmp_list = []
            while first_index < len(task_id_list):
                global_start_position = first_index
                global_stop_position = min(first_index + BATCH_SIZE, len(task_id_list))
                subset_task_id_list = task_id_list[global_start_position:global_stop_position]
                tmp_list.append((global_start_position, global_stop_position, subset_task_id_list))
                first_index += BATCH_SIZE

            with multiprocessing.Pool(self.parallelism) as pool:
                pool.map(partial_func, tmp_list)


class UpdateMetadataOfTask(AbstractCommandLineInterface):
    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli task update_metadata: error:"

        if args.parallelism is not None and not args.yes:
            print(
                f"{COMMON_MESSAGE} argument --parallelism: '--parallelism' を指定するときは、必ず  ``--yes``  を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self):
        args = self.args

        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        metadata = annofabcli.common.cli.get_json_from_args(args.metadata)
        super().validate_project(args.project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
        main_obj = UpdateMetadataOfTaskMain(
            self.service, is_overwrite_metadata=args.overwrite, parallelism=args.parallelism, all_yes=args.yes
        )
        main_obj.update_metadata_of_task(args.project_id, task_ids=task_id_list, metadata=metadata)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateMetadataOfTask(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    argument_parser.add_task_id(required=True)

    parser.add_argument(
        "--metadata",
        required=True,
        type=str,
        help="タスクに設定する ``metadata`` をJSON形式で指定してください。メタデータの値には文字列、数値、真偽値のいずれかを指定してください。"
        " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="指定した場合、メタデータを上書きして更新します（すでに設定されているメタデータは削除されます）。指定しない場合、 ``--metadata`` に指定されたキーのみ更新されます。",
    )

    parser.add_argument(
        "--parallelism", type=int, help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "update_metadata"
    subcommand_help = "タスクのメタデータを更新します。"
    description = "タスクのメタデータを上書きして更新します。"
    epilog = "オーナまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog
    )
    parse_args(parser)
    return parser
