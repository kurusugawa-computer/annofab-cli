import argparse
import logging
import multiprocessing
import sys
import uuid
from dataclasses import dataclass
from functools import partial
from typing import Any, Collection, Dict, List, Optional, Tuple

import annofabapi
import annofabapi.utils
from annofabapi.models import InputDataType, ProjectMemberRole, TaskPhase, TaskStatus
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
    get_list_from_args,
)

logger = logging.getLogger(__name__)


@dataclass
class AddedSimpleComment(DataClassJsonMixin):
    """
    付与するシンプルな検査コメント
    """

    comment: str
    """検査コメントの中身"""

    data: Dict[str, Any]
    """検査コメントを付与する位置や区間"""

    phrases: Optional[List[str]] = None
    """参照している定型指摘ID"""


class PutInspectionCommentsSimplyMain(AbstractCommandLineWithConfirmInterface):
    def __init__(self, service: annofabapi.Resource, project_id: str, all_yes: bool = False):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.project_id = project_id

        AbstractCommandLineWithConfirmInterface.__init__(self, all_yes)

    def _create_request_body(self, task: Dict[str, Any], comment_info: AddedSimpleComment) -> List[Dict[str, Any]]:
        """batch_update_comments に渡すリクエストボディを作成する。"""

        def _convert(comment: AddedSimpleComment) -> Dict[str, Any]:
            return {
                "comment": comment.comment,
                "comment_id": str(uuid.uuid4()),
                "phase": task["phase"],
                "phase_stage": task["phase_stage"],
                "comment_type": "inspection",
                "account_id": self.service.api.account_id,
                "comment_node": {"data": comment.data, "status": "open", "_type": "Root"},
                "phrases": comment.phrases,
                "_type": "Put",
            }

        return [_convert(comment_info)]

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

        if task["account_id"] != self.service.api.account_id:
            self.facade.change_operator_of_task(project_id, task_id, self.service.api.account_id)
            logger.debug(f"{task_id}: 担当者を自分自身に変更しました。")

        changed_task = self.facade.change_to_working_status(project_id, task_id, self.service.api.account_id)
        return changed_task

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

    def put_inspection_comment_for_task(
        self,
        task_id: str,
        comment_info: AddedSimpleComment,
        task_index: Optional[int] = None,
    ) -> bool:
        """
        タスクに検査コメントを付与します。

        Args:
            task_id: タスクID
            comment_info: コメント情報
            task_index: タスクの連番

        Returns:
            付与した検査コメントの数
        """
        logging_prefix = f"{task_index+1} 件目" if task_index is not None else ""

        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"{logging_prefix} : task_id='{task_id}' のタスクは存在しないので、スキップします。")
            return False

        logger.debug(
            f"{logging_prefix} : task_id = {task['task_id']}, "
            f"status = {task['status']}, "
            f"phase = {task['phase']}, "
        )

        if not self._can_add_comment(
            task=task,
        ):
            return False

        if not self.confirm_processing(f"task_id='{task_id}' のタスクに検査コメントを付与しますか？"):
            return False

        # 検査コメントを付与するには作業中状態にする必要があるので、タスクの状態を作業中にする
        changed_task = self.change_to_working_status(self.project_id, task)

        input_data_id = task["input_data_id_list"][0]

        try:
            # 検査コメントを付与する
            request_body = self._create_request_body(task=changed_task, comment_info=comment_info)
            self.service.api.batch_update_comments(self.project_id, task_id, input_data_id, request_body=request_body)
            logger.debug(f"{logging_prefix} : task_id={task_id} のタスクに検査コメントを付与しました。")
            return True
        except Exception:  # pylint: disable=broad-except
            logger.warning(
                f"{logging_prefix} : task_id={task_id}, input_data_id={input_data_id}: 検査コメントの付与に失敗しました。", exc_info=True
            )
            return False
        finally:
            self.facade.change_to_break_phase(self.project_id, task_id)
            # 担当者が変えている場合は、元に戻す
            if task["account_id"] != changed_task["account_id"]:
                self.facade.change_operator_of_task(self.project_id, task_id, task["account_id"])
                logger.debug(f"{task_id}: 担当者を元のユーザ( account_id={task['account_id']}）に戻しました。")

    def add_comments_for_task_wrapper(self, tpl: Tuple[int, str], comment_info: AddedSimpleComment) -> bool:
        task_index, task_id = tpl
        try:
            return self.put_inspection_comment_for_task(
                task_id=task_id, comment_info=comment_info, task_index=task_index
            )
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"task_id={task_id}: 検査コメントの付与に失敗しました。", exc_info=True)
            return False

    def put_inspection_comment_for_task_list(
        self,
        task_ids: Collection[str],
        comment_info: AddedSimpleComment,
        parallelism: Optional[int] = None,
    ) -> None:

        logger.info(f"{len(task_ids)} 件のタスクに検査コメントを付与します。")

        if parallelism is not None:
            func = partial(self.add_comments_for_task_wrapper, comment_info=comment_info)
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(func, enumerate(task_ids))
                success_count = len([e for e in result_bool_list if e])

        else:
            # 逐次処理
            success_count = 0
            for task_index, task_id in enumerate(task_ids):
                try:
                    result = self.put_inspection_comment_for_task(
                        task_id=task_id,
                        comment_info=comment_info,
                        task_index=task_index,
                    )
                    if result:
                        success_count += 1
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"task_id={task_id}: 検査コメントの付与に失敗しました。", exc_info=True)
                    continue

        logger.info(f"{success_count} / {len(task_ids)} 件のタスクに検査コメントを付与しました。")


class PutInspectionCommentsSimply(AbstractCommandLineInterface):

    COMMON_MESSAGE = "annofabcli inspection_comment put_simply: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず ``--yes`` を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        super().validate_project(args.project_id, [ProjectMemberRole.ACCEPTER, ProjectMemberRole.OWNER])

        comment_data = annofabcli.common.cli.get_json_from_args(args.comment_data)
        project, _ = self.service.api.get_project(args.project_id)
        if comment_data is None:
            if project["input_data_type"] == InputDataType.IMAGE.value:
                comment_data = {"x": 0, "y": 0, "_type": "Point"}
            elif project["input_data_type"] == InputDataType.MOVIE.value:
                # 注意：少なくとも0.1秒以上の区間にしないと、Annofab上で検査コメントを確認できない
                comment_data = {"start": 0, "end": 100, "_type": "Time"}
            elif project["input_data_type"] == InputDataType.CUSTOM.value:
                # customプロジェクト
                print(
                    f"{self.COMMON_MESSAGE} argument --comment_data: カスタムプロジェクトに検査コメントを付与する場合は必須です。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        task_id_list = get_list_from_args(args.task_id)
        phrase_id_list = get_list_from_args(args.phrase_id)
        main_obj = PutInspectionCommentsSimplyMain(self.service, project_id=args.project_id, all_yes=self.all_yes)
        main_obj.put_inspection_comment_for_task_list(
            task_ids=task_id_list,
            comment_info=AddedSimpleComment(comment=args.comment, data=comment_data, phrases=phrase_id_list),
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PutInspectionCommentsSimply(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "-t",
        "--task_id",
        type=str,
        nargs="+",
        required=True,
        help=("検査コメントを付与するタスクのtask_idを指定してください。\n" "``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。"),
    )

    parser.add_argument(
        "--comment",
        type=str,
        required=True,
        help="付与する検査コメントのメッセージを指定します。",
    )

    parser.add_argument("--phrase_id", type=str, nargs="+", help="定型指摘コメントのIDを指定してください。")

    parser.add_argument(
        "--comment_data",
        type=str,
        help="検査コメントを付与する位置や区間をJSON形式で指定します。\n"
        "指定方法は https://annofab-cli.readthedocs.io/ja/latest/command_reference/inspection_comment/put_simply.html を参照してください。\n"  # noqa: E501
        " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。\n"
        "デフォルトでは画像プロジェクトならば画像の左上(x=0,y=0)、動画プロジェクトなら動画の先頭（start=0, end=100)に付与します。"
        "カスタムプロジェクトに検査コメントを付与する場合は必須です。",
    )

    parser.add_argument(
        "--parallelism", type=int, help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "put_simply"
    subcommand_help = "``inspection_comment put`` コマンドよりも、簡単に検査コメントを付与します。"
    epilog = "チェッカーロールまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
