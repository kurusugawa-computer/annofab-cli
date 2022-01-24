import argparse
import logging
import multiprocessing
import sys
from typing import Any, Dict, List, Optional, Tuple

import annofabapi
import annofabapi.utils
import requests
from annofabapi.models import ProjectMemberRole, TaskPhase, TaskStatus

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


DeletedCommentsForTask = Dict[str, List[str]]
"""
タスク配下の削除対象の検査コメント
keyはinput_data_id, value: input_data_idのlist
"""

DeletedInspectionIds = Dict[str, DeletedCommentsForTask]
"""
削除対象の検査コメント
keyはtask_id
"""


class DeleteInspectionCommentsMain(AbstractCommandLineWithConfirmInterface):
    def __init__(self, service: annofabapi.Resource, project_id: str, all_yes: bool = False):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.project_id = project_id

        AbstractCommandLineWithConfirmInterface.__init__(self, all_yes)

    def _create_request_body(
        self, task: Dict[str, Any], input_data_id: str, inspection_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """batch_update_inspections に渡すリクエストボディを作成する。"""

        def _convert(inspection_id: str) -> Dict[str, Any]:
            return {
                "project_id": self.project_id,
                "task_id": task["task_id"],
                "input_data_id": input_data_id,
                "inspection_id": inspection_id,
                "_type": "Delete",
            }

        old_inspection_list, _ = self.service.api.get_inspections(self.project_id, task["task_id"], input_data_id)
        old_inspection_ids = {e["inspection_id"] for e in old_inspection_list}

        request_body = []
        for inspection_id in inspection_ids:
            if inspection_id not in old_inspection_ids:
                logger.warning(
                    f"task_id={task['task_id']}, input_data_id={input_data_id}: "
                    f"inspection_id='{inspection_id}'の検査コメントは存在しません。",
                )
                continue
            request_body.append(_convert(inspection_id))
        return request_body

    def change_to_working_status(self, project_id: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        作業中状態に遷移する。必要ならば担当者を自分自身に変更する。

        Args:
            project_id:
            task:

        Returns:
            作業中状態遷移後のタスク
        """

        task_id = task["task_id"]
        try:
            if task["account_id"] != self.service.api.account_id:
                self.facade.change_operator_of_task(project_id, task_id, self.service.api.account_id)
                logger.debug(f"{task_id}: 担当者を自分自身に変更しました。")

            changed_task = self.facade.change_to_working_status(project_id, task_id, self.service.api.account_id)
            return changed_task

        except requests.HTTPError as e:
            logger.warning(e)
            logger.warning(f"{task_id}: 担当者の変更、または作業中状態への変更に失敗しました。")
            raise

    @staticmethod
    def _can_delete_comment(
        task: Dict[str, Any],
    ) -> bool:
        task_id = task["task_id"]
        if task["phase"] == TaskPhase.ANNOTATION.value:
            logger.warning(f"task_id='{task_id}': 教師付フェーズなので、検査コメントを削除できません。")
            return False

        if task["status"] not in [TaskStatus.NOT_STARTED.value, TaskStatus.WORKING.value, TaskStatus.BREAK.value]:
            logger.warning(
                f"task_id='{task_id}' : タスクの状態が未着手,作業中,休憩中 以外の状態なので、検査コメントを削除できません。（task_status='{task['status']}'）"
            )
            return False
        return True

    def delete_comments_for_task(
        self,
        task_id: str,
        inspection_ids_for_task: DeletedCommentsForTask,
        task_index: Optional[int] = None,
    ) -> int:
        """
        タスクに対して検査コメントを削除します。

        Args:
            task_id: タスクID
            inspection_ids_for_task: 削除対象の検査コメントのIDの集合
            task_index: タスクの連番

        Returns:
            削除した検査コメントが所属する入力データ数
        """
        logging_prefix = f"{task_index+1} 件目" if task_index is not None else ""

        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"{logging_prefix} : task_id='{task_id}' のタスクは存在しないので、スキップします。")
            return 0

        logger.debug(
            f"{logging_prefix} : task_id = {task['task_id']}, "
            f"status = {task['status']}, "
            f"phase = {task['phase']}, "
        )

        if not self._can_delete_comment(
            task=task,
        ):
            return 0

        if not self.confirm_processing(f"task_id='{task_id}' のタスクに検査コメントを削除しますか？"):
            return 0

        # 検査コメントを削除するには作業中状態にする必要がある
        changed_task = self.change_to_working_status(self.project_id, task)
        added_comments_count = 0
        for input_data_id, inspection_ids in inspection_ids_for_task.items():
            if input_data_id not in task["input_data_id_list"]:
                logger.warning(
                    f"{logging_prefix} : task_id='{task_id}'のタスクに input_data_id='{input_data_id}'の入力データは存在しません。"
                )
                continue
            try:
                # 検査コメントを削除
                request_body = self._create_request_body(
                    task=changed_task, input_data_id=input_data_id, inspection_ids=inspection_ids
                )
                if len(request_body) > 0:
                    self.service.api.batch_update_inspections(
                        self.project_id, task_id, input_data_id, request_body=request_body
                    )
                    added_comments_count += 1
                    logger.debug(
                        f"{logging_prefix} : task_id={task_id}, input_data_id={input_data_id}: "
                        f"{len(request_body)}件の検査コメントを削除しました。"
                    )
                else:
                    logger.warning(
                        f"{logging_prefix} : task_id={task_id}, input_data_id={input_data_id}: "
                        f"削除できる検査コメントは存在しませんでした。"
                    )

            except Exception as e:  # pylint: disable=broad-except
                logger.warning(
                    f"{logging_prefix} : task_id={task_id}, input_data_id={input_data_id}: 検査コメントの削除に失敗しました。", e
                )

        self.facade.change_to_break_phase(self.project_id, task_id)
        return added_comments_count

    def delete_comments_for_task_wrapper(
        self,
        tpl: Tuple[int, Tuple[str, DeletedCommentsForTask]],
    ) -> int:
        task_index, (task_id, inspection_ids_for_task) = tpl
        return self.delete_comments_for_task(
            task_id=task_id, inspection_ids_for_task=inspection_ids_for_task, task_index=task_index
        )

    def delete_comments_for_task_list(
        self,
        inspection_ids_for_task_list: DeletedInspectionIds,
        parallelism: Optional[int] = None,
    ) -> None:
        comments_count = sum(len(e) for e in inspection_ids_for_task_list.values())
        logger.info(f"検査コメントを削除するタスク数: {len(inspection_ids_for_task_list)}, 検査コメントを削除する入力データ数: {comments_count}")

        if parallelism is not None:
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(
                    self.delete_comments_for_task_wrapper, enumerate(inspection_ids_for_task_list.items())
                )
                added_comments_count = sum(e for e in result_bool_list)

        else:
            # 逐次処理
            added_comments_count = 0
            for task_index, (task_id, inspection_ids_for_task) in enumerate(inspection_ids_for_task_list.items()):
                try:
                    result = self.delete_comments_for_task(
                        task_id=task_id,
                        inspection_ids_for_task=inspection_ids_for_task,
                        task_index=task_index,
                    )
                    added_comments_count += result
                except Exception as e:  # pylint: disable=broad-except
                    logger.warning(f"task_id={task_id}: 検査コメントの削除に失敗しました。", e)
                    continue

        logger.info(f"{added_comments_count} / {comments_count} 件の入力データから検査コメントを削除しました。")


class DeleteInspectionComments(AbstractCommandLineInterface):
    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli inspection_comment delete: error:"

        if args.parallelism is not None and not args.yes:
            print(
                f"{COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず ``--yes`` を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        super().validate_project(args.project_id, [ProjectMemberRole.ACCEPTER, ProjectMemberRole.OWNER])

        dict_comments = annofabcli.common.cli.get_json_from_args(args.json)
        main_obj = DeleteInspectionCommentsMain(self.service, project_id=args.project_id, all_yes=self.all_yes)
        main_obj.delete_comments_for_task_list(
            inspection_ids_for_task_list=dict_comments,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteInspectionComments(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--json",
        type=str,
        help=(
            "削除する検査コメントのIDをJSON形式で指定してください。"
            "JSONのスキーマは https://annofab-cli.readthedocs.io/ja/latest/command_reference/inspection_comment/delete.html "
            "に記載されています。"
        ),
    )

    parser.add_argument(
        "--parallelism", type=int, help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "delete"
    subcommand_help = "検査コメントを削除します。"
    description = "検査コメントを削除します。 【注意】他人の検査コメントや他のフェーズで付与された検査コメントを削除できてしまいます。"
    epilog = "チェッカーロールまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
