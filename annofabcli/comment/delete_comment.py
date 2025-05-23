import argparse
import json
import logging
import multiprocessing
import sys
from typing import Any, Optional

import annofabapi
import annofabapi.utils
import requests
from annofabapi.models import ProjectMemberRole, TaskStatus

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


DeletedCommentsForTask = dict[str, list[str]]
"""
タスク配下の削除対象のコメント
keyはinput_data_id, value: comment_idのlist
"""

DeletedComments = dict[str, DeletedCommentsForTask]
"""
削除対象のコメント
keyはtask_id, value: `DeletedCommentsForTask`
"""


class DeleteCommentMain(CommandLineWithConfirm):
    def __init__(self, service: annofabapi.Resource, project_id: str, all_yes: bool = False) -> None:  # noqa: FBT001, FBT002
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.project_id = project_id

        CommandLineWithConfirm.__init__(self, all_yes)

    def _create_request_body(self, task: dict[str, Any], input_data_id: str, comment_ids: list[str]) -> list[dict[str, Any]]:
        """batch_update_comments に渡すリクエストボディを作成する。"""

        def _convert(comment_id: str) -> dict[str, Any]:
            return {
                "comment_id": comment_id,
                "_type": "Delete",
            }

        old_comment_list, _ = self.service.api.get_comments(self.project_id, task["task_id"], input_data_id, query_params={"v": "2"})
        old_comment_ids = {e["comment_id"] for e in old_comment_list}
        request_body = []
        for comment_id in comment_ids:
            if comment_id not in old_comment_ids:
                logger.warning(
                    f"task_id='{task['task_id']}', input_data_id='{input_data_id}' :: comment_id='{comment_id}'のコメントは存在しません。",
                )
                continue
            request_body.append(_convert(comment_id))
        return request_body

    def change_to_working_status(self, project_id: str, task: dict[str, Any]) -> dict[str, Any]:
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
                self.service.wrapper.change_task_operator(project_id, task_id, self.service.api.account_id)
                logger.debug(f"{task_id}: 担当者を自分自身に変更しました。")

            changed_task = self.service.wrapper.change_task_status_to_working(project_id, task_id)
            return changed_task  # noqa: TRY300

        except requests.HTTPError:
            logger.warning(f"{task_id}: 担当者の変更、または作業中状態への変更に失敗しました。", exc_info=True)
            raise

    def _can_delete_comment(
        self,
        task: dict[str, Any],
    ) -> bool:
        task_id = task["task_id"]
        if task["status"] not in [TaskStatus.NOT_STARTED.value, TaskStatus.WORKING.value, TaskStatus.BREAK.value]:
            logger.warning(f"task_id='{task_id}' : タスクの状態が未着手,作業中,休憩中 以外の状態なので、コメントを削除できません。（task_status='{task['status']}'）")
            return False
        return True

    def delete_comments_for_task(
        self,
        task_id: str,
        comment_ids_for_task: DeletedCommentsForTask,
        task_index: Optional[int] = None,
    ) -> int:
        """
        タスクに対してコメントを削除します。

        Args:
            task_id: タスクID
            comment_ids_for_task: 削除対象のコメントのIDの集合
            task_index: タスクの連番

        Returns:
            削除したコメントが所属する入力データ数
        """
        logging_prefix = f"{task_index + 1} 件目" if task_index is not None else ""

        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"{logging_prefix} : task_id='{task_id}' のタスクは存在しないので、スキップします。")
            return 0

        logger.debug(f"{logging_prefix} : task_id = {task['task_id']}, status = {task['status']}, phase = {task['phase']}, ")

        if not self._can_delete_comment(
            task=task,
        ):
            return 0

        if not self.confirm_processing(f"task_id='{task_id}' のタスクに付与されたコメントを削除しますか？"):
            return 0

        # コメントを削除するには作業中状態にする必要がある
        changed_task = self.change_to_working_status(self.project_id, task)
        added_comments_count = 0
        for input_data_id, comment_ids in comment_ids_for_task.items():
            if input_data_id not in task["input_data_id_list"]:
                logger.warning(f"{logging_prefix} : task_id='{task_id}'のタスクに input_data_id='{input_data_id}'の入力データは存在しません。")
                continue
            try:
                # コメントを削除
                request_body = self._create_request_body(task=changed_task, input_data_id=input_data_id, comment_ids=comment_ids)
                if len(request_body) > 0:
                    self.service.api.batch_update_comments(self.project_id, task_id, input_data_id, request_body=request_body)
                    added_comments_count += 1
                    logger.debug(f"{logging_prefix} :: task_id='{task_id}', input_data_id='{input_data_id}' :: {len(request_body)}件のコメントを削除しました。")
                else:
                    logger.warning(f"{logging_prefix} :: task_id='{task_id}', input_data_id='{input_data_id}' :: 削除できるコメントは存在しませんでした。")

            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    f"{logging_prefix} :: task_id='{task_id}', input_data_id='{input_data_id}' :: コメントの削除に失敗しました。",
                    exc_info=True,
                )

        self.service.wrapper.change_task_status_to_break(self.project_id, task_id)
        return added_comments_count

    def delete_comments_for_task_wrapper(
        self,
        tpl: tuple[int, tuple[str, DeletedCommentsForTask]],
    ) -> int:
        task_index, (task_id, comment_ids_for_task) = tpl
        return self.delete_comments_for_task(task_id=task_id, comment_ids_for_task=comment_ids_for_task, task_index=task_index)

    def delete_comments_for_task_list(
        self,
        comment_ids_for_task_list: DeletedComments,
        parallelism: Optional[int] = None,
    ) -> None:
        comments_count = sum(len(e) for e in comment_ids_for_task_list.values())
        logger.info(f"削除対象のコメントを含むタスクの個数: {len(comment_ids_for_task_list)}, 削除対象のコメントを含む入力データ数: {comments_count}")

        if parallelism is not None:
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(self.delete_comments_for_task_wrapper, enumerate(comment_ids_for_task_list.items()))
                added_comments_count = sum(e for e in result_bool_list)

        else:
            # 逐次処理
            added_comments_count = 0
            for task_index, (task_id, comment_ids_for_task) in enumerate(comment_ids_for_task_list.items()):
                try:
                    result = self.delete_comments_for_task(
                        task_id=task_id,
                        comment_ids_for_task=comment_ids_for_task,
                        task_index=task_index,
                    )
                    added_comments_count += result
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"task_id='{task_id}' :: コメントの削除に失敗しました。", exc_info=True)
                    continue

        logger.info(f"{added_comments_count} / {comments_count} 件の入力データからコメントを削除しました。")


class DeleteComment(CommandLine):
    COMMON_MESSAGE = "annofabcli comment delete: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず '--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        super().validate_project(args.project_id, [ProjectMemberRole.ACCEPTER, ProjectMemberRole.OWNER])

        dict_comments = annofabcli.common.cli.get_json_from_args(args.json)
        if not isinstance(dict_comments, dict):
            print(f"{self.COMMON_MESSAGE} argument --json: JSON形式が不正です。オブジェクトを指定してください。", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
        main_obj = DeleteCommentMain(self.service, project_id=args.project_id, all_yes=self.all_yes)
        main_obj.delete_comments_for_task_list(
            comment_ids_for_task_list=dict_comments,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteComment(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    JSON_SAMPLE = {"task_id1": {"input_data_id1": ["comment_id1", "comment_id2"]}}  # noqa: N806
    parser.add_argument(
        "--json",
        type=str,
        required=True,
        help=(f"削除するコメントのcomment_idをJSON形式で指定してください。\n\n(ex) ``{json.dumps(JSON_SAMPLE)}``"),
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず '--yes' を指定してください。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "delete"
    subcommand_help = "コメントを削除します。"
    description = "コメントを削除します。\n【注意】他人の付けたコメントも削除できてしまいます。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
