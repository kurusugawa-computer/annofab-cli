from __future__ import annotations

import argparse
import logging
import multiprocessing
from functools import partial
from typing import Any, Collection, Dict, Optional, Union

import annofabapi
from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    AbstractCommandLineWithConfirmInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
)

logger = logging.getLogger(__name__)

Metadata = Dict[str, Union[str, bool, int]]


class UpdateMetadataOfTaskMain(AbstractCommandLineWithConfirmInterface):
    def __init__(self, service: annofabapi.Resource, is_overwrite_metadata: bool, all_yes: bool = False):
        self.service = service
        self.is_overwrite_metadata = is_overwrite_metadata
        AbstractCommandLineWithConfirmInterface.__init__(self, all_yes)

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

        if not self.confirm_processing(f"タスク '{task_id}' のメタデータを更新しますか？ "):
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

    def update_metadata_of_task2(
        self,
        project_id: str,
        task_ids: Collection[str],
        metadata: Dict[str, Any],
        parallelism: Optional[int] = None,
    ):
        if self.is_overwrite_metadata:
            logger.info(f"{len(task_ids)} 件のタスクのmetadataを、{metadata} に変更します（上書き）。")
        else:
            logger.info(f"{len(task_ids)} 件のタスクのmetadataに、{metadata} を追加します。")

        if self.is_overwrite_metadata and self.all_yes:
            self.update_metadata_with_patch_tasks_metadata_api(project_id, task_ids=task_ids, metadata=metadata)
        else:
            success_count = 0
            if parallelism is not None:
                partial_func = partial(
                    self.set_metadata_to_task_wrapper,
                    project_id=project_id,
                    metadata=metadata,
                )
                with multiprocessing.Pool(parallelism) as pool:
                    result_bool_list = pool.map(partial_func, enumerate(task_ids))
                    success_count = len([e for e in result_bool_list if e])

            else:
                # 逐次処理
                for task_index, task_id in enumerate(task_ids):
                    result = self.set_metadata_to_task_wrapper(
                        project_id,
                        task_id,
                        metadata=metadata,
                        task_index=task_index,
                    )
                    if result:
                        success_count += 1

            logger.info(f"{success_count} / {len(task_ids)} 件のタスクのmetadataを変更しました。")

    def update_metadata_with_patch_tasks_metadata_api(
        self, project_id: str, task_ids: Collection[str], metadata: Metadata
    ):
        """patch_tasks_metadata webapiを呼び出して、タスクのメタデータを更新します。
        注意：メタデータは上書きされます。
        """
        BATCH_SIZE = 500
        logger.info(f"{len(task_ids)} 件のタスクのmetadataを{metadata} に、{BATCH_SIZE}個ずつ変更します。")
        first_index = 0
        while first_index < len(task_ids):
            logger.info(f"{first_index+1} 〜 {min(first_index+BATCH_SIZE, len(task_ids))} 件目のタスクのmetadataを更新します。")
            request_body = {task_id: metadata for task_id in task_ids[first_index : first_index + BATCH_SIZE]}
            self.service.api.patch_tasks_metadata(project_id, request_body=request_body)
            first_index += BATCH_SIZE


class UpdateMetadataOfTask(AbstractCommandLineInterface):
    def main(self):
        args = self.args
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        metadata = annofabcli.common.cli.get_json_from_args(args.metadata)
        super().validate_project(args.project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
        main_obj = UpdateMetadataOfTaskMain(self.service, is_overwrite_metadata=args.overwrite, all_yes=args.yes)
        main_obj.update_metadata_of_task(args.project_id, task_id_list=task_id_list, metadata=metadata)


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
