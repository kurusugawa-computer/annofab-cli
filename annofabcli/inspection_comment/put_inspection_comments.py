import argparse
import logging
import multiprocessing
import sys
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import annofabapi
import annofabapi.utils
import requests
from annofabapi.models import ProjectMemberRole, TaskPhase, TaskStatus
from dataclasses_json import DataClassJsonMixin

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


@dataclass
class AddedComment(DataClassJsonMixin):
    """
    追加対象の検査コメント
    """

    comment: str
    """検査コメントの中身"""

    data: Dict[str, Any]
    """検査コメントを付与する位置や区間"""

    annotation_id: Optional[str] = None
    """検査コメントに紐付ける"""

    phrases: Optional[List[str]] = None
    """参照している定型指摘ID"""


AddedCommentsForTask = Dict[str, List[AddedComment]]
"""
タスク配下の追加対象の検査コメント
keyはinput_data_id
"""

AddedComments = Dict[str, AddedCommentsForTask]
"""
追加対象の検査コメント
keyはtask_id
"""


class AddInspectionCommentsMain(AbstractCommandLineWithConfirmInterface):
    def __init__(self, service: annofabapi.Resource, project_id: str, all_yes: bool = False):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.project_id = project_id

        AbstractCommandLineWithConfirmInterface.__init__(self, all_yes)

    def _create_request_body(
        self, task: Dict[str, Any], input_data_id: str, comments: List[AddedComment]
    ) -> List[Dict[str, Any]]:
        """batch_update_comments に渡すリクエストボディを作成する。"""

        def _create_dict_annotation_id() -> Dict[str, str]:
            content, _ = self.service.api.get_editor_annotation(self.project_id, task["task_id"], input_data_id)
            details = content["details"]
            return {e["annotation_id"]: e["label_id"] for e in details}

        dict_annotation_id_label_id = _create_dict_annotation_id()

        def _convert(comment: AddedComment) -> Dict[str, Any]:
            return {
                "comment_id": str(uuid.uuid4()),
                "phase": task["phase"],
                "phase_stage": task["phase_stage"],
                "account_id": self.service.api.account_id,
                "comment_type": "inspection",
                "comment": comment.comment,
                "comment_node": {
                    "data": comment.data,
                    "annotation_id": comment.annotation_id,
                    "label_id": dict_annotation_id_label_id.get(comment.annotation_id)
                    if comment.annotation_id is not None
                    else None,
                    "status": "open",
                    "_type": "Root",
                },
                "phrases": comment.phrases,
                # "_type": "Put",
            }

        return [_convert(e) for e in comments]

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
    def _can_add_comment(
        task: Dict[str, Any],
    ) -> bool:
        task_id = task["task_id"]
        if task["phase"] == TaskPhase.ANNOTATION.value:
            logger.warning(f"task_id='{task_id}': 教師付フェーズなので、検査コメントを付与できません。")
            return False

        if task["status"] not in [TaskStatus.NOT_STARTED.value, TaskStatus.WORKING.value, TaskStatus.BREAK.value]:
            logger.warning(
                f"task_id='{task_id}' : タスクの状態が未着手,作業中,休憩中 以外の状態なので、検査コメントを付与できません。（task_status='{task['status']}'）"
            )
            return False
        return True

    def add_comments_for_task(
        self,
        task_id: str,
        comments_for_task: AddedCommentsForTask,
        task_index: Optional[int] = None,
    ) -> int:
        """
        タスクに検査コメントを付与します。

        Args:
            task_id: タスクID
            comments_for_task: 1つのタスクに付与する検査コメントの集合
            task_index: タスクの連番

        Returns:
            付与した検査コメントの数
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

        if not self._can_add_comment(
            task=task,
        ):
            return 0

        if not self.confirm_processing(f"task_id='{task_id}' のタスクに検査コメントを付与しますか？"):
            return 0

        # 検査コメントを付与するには作業中状態にする必要がある
        changed_task = self.change_to_working_status(self.project_id, task)
        added_comments_count = 0
        for input_data_id, comments in comments_for_task.items():
            if input_data_id not in task["input_data_id_list"]:
                logger.warning(
                    f"{logging_prefix} : task_id='{task_id}'のタスクに input_data_id='{input_data_id}'の入力データは存在しません。"
                )
                continue
            try:
                # 検査コメントを付与する
                request_body = self._create_request_body(
                    task=changed_task, input_data_id=input_data_id, comments=comments
                )
                self.service.api.batch_update_comments(
                    self.project_id, task_id, input_data_id, request_body=request_body
                )
                added_comments_count += 1
                logger.debug(
                    f"{logging_prefix} : task_id={task_id}, input_data_id={input_data_id}: "
                    f"{len(comments)}件の検査コメントを付与しました。"
                )
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    f"{logging_prefix} : task_id={task_id}, input_data_id={input_data_id}: 検査コメントの付与に失敗しました。",
                    exc_info=True,
                )
            finally:
                self.facade.change_to_break_phase(self.project_id, task_id)
                # 担当者が変えている場合は、元に戻す
                if task["account_id"] != changed_task["account_id"]:
                    self.facade.change_operator_of_task(self.project_id, task_id, task["account_id"])
                    logger.debug(f"{task_id}: 担当者を元のユーザ( account_id={task['account_id']}）に戻しました。")

        return added_comments_count

    def add_comments_for_task_wrapper(
        self,
        tpl: Tuple[int, Tuple[str, AddedCommentsForTask]],
    ) -> int:
        task_index, (task_id, comments_for_task) = tpl
        return self.add_comments_for_task(task_id=task_id, comments_for_task=comments_for_task, task_index=task_index)

    def add_comments_for_task_list(
        self,
        comments_for_task_list: AddedComments,
        parallelism: Optional[int] = None,
    ) -> None:
        comments_count = sum(len(e) for e in comments_for_task_list.values())
        logger.info(f"検査コメントを付与するタスク数: {len(comments_for_task_list)}, 検査コメント付与する入力データ数: {comments_count}")

        if parallelism is not None:
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(
                    self.add_comments_for_task_wrapper, enumerate(comments_for_task_list.items())
                )
                added_comments_count = sum(e for e in result_bool_list)

        else:
            # 逐次処理
            added_comments_count = 0
            for task_index, (task_id, comments_for_task) in enumerate(comments_for_task_list.items()):
                try:
                    result = self.add_comments_for_task(
                        task_id=task_id,
                        comments_for_task=comments_for_task,
                        task_index=task_index,
                    )
                    added_comments_count += result
                except Exception as e:  # pylint: disable=broad-except
                    logger.warning(f"task_id={task_id}: 検査コメントの付与に失敗しました。", e)
                    continue

        logger.info(f"{added_comments_count} / {comments_count} 件の入力データに検査コメントを付与しました。")


class PutInspectionComments(AbstractCommandLineInterface):
    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli inspection_comment put: error:"

        if args.parallelism is not None and not args.yes:
            print(
                f"{COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず ``--yes`` を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    @staticmethod
    def _convert_comments(dict_comments: Dict[str, Any]) -> AddedComments:
        def _covert_comments_for_task(comments_for_task):
            return {
                input_data_id: AddedComment.schema().load(comments, many=True)
                for input_data_id, comments in comments_for_task.items()
            }

        return {
            task_id: _covert_comments_for_task(comments_for_task)
            for task_id, comments_for_task in dict_comments.items()
        }

    def main(self):
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        super().validate_project(args.project_id, [ProjectMemberRole.ACCEPTER, ProjectMemberRole.OWNER])

        dict_comments = annofabcli.common.cli.get_json_from_args(args.json)
        comments_for_task_list = self._convert_comments(dict_comments)
        main_obj = AddInspectionCommentsMain(self.service, project_id=args.project_id, all_yes=self.all_yes)
        main_obj.add_comments_for_task_list(
            comments_for_task_list=comments_for_task_list,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PutInspectionComments(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--json",
        type=str,
        help=(
            "付与する検査コメントをJSON形式で指定してください。"
            "JSONのスキーマは https://annofab-cli.readthedocs.io/ja/latest/command_reference/inspection_comment/put.html "
            "に記載されています。"
        ),
    )

    parser.add_argument(
        "--parallelism", type=int, help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "put"
    subcommand_help = "検査コメントを付与します。"
    description = "検査コメントを付与します。"
    epilog = "チェッカーロールまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
