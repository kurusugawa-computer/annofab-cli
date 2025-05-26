from __future__ import annotations

import argparse
import logging
import multiprocessing
import sys
import uuid
from functools import partial
from typing import Any, Optional

import annofabapi
import annofabapi.utils
import requests
from annofabapi.dataclass.task import Task
from annofabapi.models import InputDataType, ProjectMemberRole, TaskPhase, TaskStatus
from annofabapi.plugin import EditorPluginId

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
from annofabcli.common.enums import CustomProjectType
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery, match_task_with_query

logger = logging.getLogger(__name__)


class RejectTasksMain(CommandLineWithConfirm):
    def __init__(self, service: annofabapi.Resource, *, comment_data: Optional[dict[str, Any]], all_yes: bool = False) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.comment_data = comment_data
        CommandLineWithConfirm.__init__(self, all_yes)

    def add_inspection_comment(
        self,
        project_id: str,
        task: dict[str, Any],
        inspection_comment: str,
    ) -> None:
        """
        検査コメントを付与する。

        Args:
            project_id:
            task:
            inspection_comment:

        """
        first_input_data_id = task["input_data_id_list"][0]

        req_inspection = [
            {
                "comment_id": str(uuid.uuid4()),
                "phase": task["phase"],
                "phase_stage": task["phase_stage"],
                "account_id": self.service.api.account_id,
                "comment_type": "inspection",
                "comment": inspection_comment,
                "comment_node": {"data": self.comment_data, "status": "open", "_type": "Root"},
                "_type": "Put",
            }
        ]

        self.service.api.batch_update_comments(project_id, task["task_id"], first_input_data_id, request_body=req_inspection)

    def confirm_reject_task(self, task_id: str, assign_last_annotator: bool, assigned_annotator_user_id: Optional[str]) -> bool:  # noqa: FBT001
        confirm_message = f"task_id='{task_id}' のタスクを差し戻しますか？"
        if assign_last_annotator:
            confirm_message += "最後の教師付フェーズの担当者を割り当てます。"
        elif assigned_annotator_user_id is not None:
            confirm_message += f"user_id='{assigned_annotator_user_id}'のユーザーを担当者に割り当てます。"
        else:
            confirm_message += "担当者は割り当てません。"

        return self.confirm_processing(confirm_message)

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
        last_updated_datetime = task["updated_datetime"]
        if task["account_id"] != self.service.api.account_id:
            _task = self.service.wrapper.change_task_operator(
                project_id,
                task_id,
                operator_account_id=self.service.api.account_id,
                last_updated_datetime=last_updated_datetime,
            )
            last_updated_datetime = _task["updated_datetime"]
            logger.debug(f"task_id='{task_id}'のタスクの担当者を自分自身に変更しました。")

        changed_task = self.service.wrapper.change_task_status_to_working(project_id, task_id, last_updated_datetime=last_updated_datetime)
        logger.debug(f"task_id='{task_id}'のタスクのステータスを作業中に変更しました。")
        return changed_task

    def _can_reject_task(
        self,
        task: dict[str, Any],
        *,
        assign_last_annotator: bool,
        assigned_annotator_user_id: Optional[str],
        cancel_acceptance: bool = False,
        task_query: Optional[TaskQuery] = None,
    ) -> bool:
        """
        以下の状態を見て、差し戻し可能かどうかを判断します。
        * タスクのフェーズやステータス
        * `--task_query`の条件にマッチするかどうか
        * 差し戻しの確認メッセージに対して、ユーザがOKしたかどうか
        """
        task_id = task["task_id"]
        if task["phase"] == TaskPhase.ANNOTATION.value:
            logger.warning(f"task_id='{task_id}' :: 教師付フェーズのため、差し戻しできません。")
            return False

        if task["status"] == TaskStatus.WORKING.value:
            logger.warning(f"task_id='{task_id}' :: タスクのstatusが'作業中'なので、差し戻しできません。")
            return False

        if task["status"] == TaskStatus.COMPLETE.value and not cancel_acceptance:
            logger.warning(f"task_id='{task_id}' :: タスクのstatusが'完了'なので、差し戻しできません。受入完了を取消す場合は、コマンドライン引数に'--cancel_acceptance'を追加してください。")
            return False

        if not match_task_with_query(Task.from_dict(task), task_query):
            logger.debug(f"task_id='{task_id}' : `--task_query`の条件にマッチしないため、スキップします。 :: task_query='{task_query}'")
            return False

        if not self.confirm_reject_task(task_id, assign_last_annotator=assign_last_annotator, assigned_annotator_user_id=assigned_annotator_user_id):  # noqa: SIM103
            return False

        return True

    def reject_task_with_adding_comment(
        self,
        project_id: str,
        task_id: str,
        *,
        inspection_comment: Optional[str] = None,
        assign_last_annotator: bool = True,
        assigned_annotator_user_id: Optional[str] = None,
        cancel_acceptance: bool = False,
        task_query: Optional[TaskQuery] = None,
        task_index: Optional[int] = None,
    ) -> bool:
        """
        タスクを差し戻します。

        Args:
            project_id:
            task_id_list:
            inspection_comment: 検査コメントの中身
            assign_last_annotator: Trueなら差し戻したタスクに対して、最後のannotation phaseを担当者を割り当てる
            assigned_annotator_user_id: 差し戻したタスクに割り当てるユーザのuser_id. assign_last_annotatorがTrueの場合、この引数は無視される。

        Returns:
            タスクを差し戻したかどうか
        """

        logging_prefix = f"{task_index + 1} 件目" if task_index is not None else ""

        task = self.service.wrapper.get_task_or_none(project_id, task_id)
        if task is None:
            logger.warning(f"{logging_prefix} :: task_id='{task_id}'のタスクをは存在しないので、スキップします。")
            return False

        logger.debug(f"{logging_prefix} :: task_id='{task['task_id']}', status='{task['status']}', phase='{task['phase']}'")

        if not self._can_reject_task(
            task=task,
            assign_last_annotator=assign_last_annotator,
            assigned_annotator_user_id=assigned_annotator_user_id,
            cancel_acceptance=cancel_acceptance,
            task_query=task_query,
        ):
            return False

        if task["status"] == TaskStatus.COMPLETE.value and cancel_acceptance:
            task = self.service.wrapper.cancel_completed_task(project_id, task_id, operator_account_id=self.service.api.account_id, last_updated_datetime=task["updated_datetime"])
            logger.debug(f"{logging_prefix} :: task_id='{task_id}'のタスクに対して受入取消を実施（完了状態から未着手状態に変更）しました。")

        try:
            if inspection_comment is not None:
                # タスクを作業中状態にして、検査コメントを付与できる状態にする
                task = self.change_to_working_status(project_id, task)
                # 検査コメントを付与する
                self.add_inspection_comment(project_id, task, inspection_comment)
                logger.debug(f"{logging_prefix} :: task_id='{task_id}'のタスクに検査コメントを付与しました。")

            # `reject_task`の`force`引数について
            # 検査コメントを付与しない場合は、強制差し戻しが必要なのでTrueを指定する
            # 検査コメントを付与する場合は、 強制差し戻しは不要。チェッカーロールでも実行できるようにするため、Falseにする
            self.service.wrapper.reject_task(project_id, task_id, force=(inspection_comment is None), last_updated_datetime=task["updated_datetime"])

            if assign_last_annotator:
                logger.debug(f"{logging_prefix} :: task_id='{task_id}' のタスクを差し戻しました。タスクの担当者は直前の教師付フェーズの担当者です。")
                return True

            else:
                assigned_annotator_account_id = self.facade.get_account_id_from_user_id(project_id, assigned_annotator_user_id) if assigned_annotator_user_id is not None else None

                self.service.wrapper.change_task_operator(project_id, task_id, operator_account_id=assigned_annotator_account_id)

                logger.debug(f"{logging_prefix} :: task_id='{task_id}' のタスクを差し戻しました。タスクの担当者: '{assigned_annotator_user_id}'")
                return True

        except requests.exceptions.HTTPError:
            logger.warning(f"{logging_prefix} : task_id='{task_id}'のタスクの差し戻しに失敗しました。", exc_info=True)

            task, _ = self.service.api.get_task(project_id, task_id)
            assert task is not None
            # 作業中状態のまま放置すると、作業時間が超過してしまうため、休憩状態にする
            if task["status"] == TaskStatus.WORKING.value:
                self.service.wrapper.change_task_status_to_break(project_id, task_id, last_updated_datetime=task["updated_datetime"])
                logger.debug(f"{logging_prefix} :: task_id='{task_id}' のタスクを休憩状態に戻しました。")

            return False

    def reject_task_for_task_wrapper(
        self,
        tpl: tuple[int, str],
        project_id: str,
        inspection_comment: Optional[str] = None,
        assign_last_annotator: bool = True,  # noqa: FBT001, FBT002
        assigned_annotator_user_id: Optional[str] = None,
        cancel_acceptance: bool = False,  # noqa: FBT001, FBT002
        task_query: Optional[TaskQuery] = None,
    ) -> bool:
        task_index, task_id = tpl
        try:
            return self.reject_task_with_adding_comment(
                project_id=project_id,
                task_id=task_id,
                task_index=task_index,
                inspection_comment=inspection_comment,
                assign_last_annotator=assign_last_annotator,
                assigned_annotator_user_id=assigned_annotator_user_id,
                cancel_acceptance=cancel_acceptance,
                task_query=task_query,
            )
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"タスク'{task_id}'の差し戻しに失敗しました。", exc_info=True)
            return False

    def reject_task_list(
        self,
        project_id: str,
        task_id_list: list[str],
        inspection_comment: Optional[str] = None,
        assign_last_annotator: bool = True,  # noqa: FBT001, FBT002
        assigned_annotator_user_id: Optional[str] = None,
        cancel_acceptance: bool = False,  # noqa: FBT001, FBT002
        task_query: Optional[TaskQuery] = None,
        parallelism: Optional[int] = None,
    ) -> None:
        if task_query is not None:
            task_query = self.facade.set_account_id_of_task_query(project_id, task_query)

        logger.info(f"{len(task_id_list)} 件のタスクを差し戻します。")

        if parallelism is not None:
            partial_func = partial(
                self.reject_task_for_task_wrapper,
                project_id=project_id,
                inspection_comment=inspection_comment,
                assign_last_annotator=assign_last_annotator,
                assigned_annotator_user_id=assigned_annotator_user_id,
                cancel_acceptance=cancel_acceptance,
                task_query=task_query,
            )
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(partial_func, enumerate(task_id_list))
                success_count = len([e for e in result_bool_list if e])

        else:
            # 逐次処理
            success_count = 0
            for task_index, task_id in enumerate(task_id_list):
                try:
                    result = self.reject_task_with_adding_comment(
                        project_id,
                        task_id,
                        task_index=task_index,
                        inspection_comment=inspection_comment,
                        assign_last_annotator=assign_last_annotator,
                        assigned_annotator_user_id=assigned_annotator_user_id,
                        cancel_acceptance=cancel_acceptance,
                        task_query=task_query,
                    )
                    if result:
                        success_count += 1
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"タスク'{task_id}'の差し戻しに失敗しました。", exc_info=True)
                    continue

        logger.info(f"{success_count} / {len(task_id_list)} 件 タスクを差し戻しました。")


class RejectTasks(CommandLine):
    COMMON_MESSAGE = "annofabcli task reject: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、'--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        assign_last_annotator = not args.not_assign and args.assigned_annotator_user_id is None

        if not args.cancel_acceptance and args.comment is not None:
            # 受入取消を実施しない AND 検査コメントを付与する場合はチェッカーロールでも実行できる
            super().validate_project(args.project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])
        else:
            super().validate_project(args.project_id, [ProjectMemberRole.OWNER])

        dict_task_query = annofabcli.common.cli.get_json_from_args(args.task_query)
        task_query: Optional[TaskQuery] = TaskQuery.from_dict(dict_task_query) if dict_task_query is not None else None

        comment_data = annofabcli.common.cli.get_json_from_args(args.comment_data)
        custom_project_type = CustomProjectType(args.custom_project_type) if args.custom_project_type is not None else None

        project, _ = self.service.api.get_project(args.project_id)
        if args.comment is not None and comment_data is None:
            if project["input_data_type"] == InputDataType.IMAGE.value:
                comment_data = {"x": 0, "y": 0, "_type": "Point"}
            elif project["input_data_type"] == InputDataType.MOVIE.value:
                # 注意：少なくとも0.1秒以上の区間にしないと、Annofab上で検査コメントを確認できない
                comment_data = {"start": 0, "end": 100, "_type": "Time"}
            elif project["input_data_type"] == InputDataType.CUSTOM.value:
                editor_plugin_id = project["configuration"]["plugin_id"]
                if editor_plugin_id == EditorPluginId.THREE_DIMENSION.value or custom_project_type == CustomProjectType.THREE_DIMENSION_POINT_CLOUD:
                    comment_data = {
                        "data": '{"kind": "CUBOID", "shape": {"dimensions": {"width": 1.0, "height": 1.0, "depth": 1.0}, "location": {"x": 0.0, "y": 0.0, "z": 0.0}, "rotation": {"x": 0.0, "y": 0.0, "z": 0.0}, "direction": {"front": {"x": 1.0, "y": 0.0, "z": 0.0}, "up": {"x": 0.0, "y": 0.0, "z": 1.0}}}, "version": "2"}',  # noqa: E501
                        "_type": "Custom",
                    }
                else:
                    print(  # noqa: T201
                        f"{self.COMMON_MESSAGE}: カスタムプロジェクト（ビルトインのエディタプラグインを使用していない）に検査コメントを付与する場合は、'--comment_data' または '--custom_project_type'を指定してください。",  # noqa: E501
                        file=sys.stderr,
                    )
                    sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        main_obj = RejectTasksMain(self.service, comment_data=comment_data, all_yes=self.all_yes)
        main_obj.reject_task_list(
            args.project_id,
            task_id_list,
            inspection_comment=args.comment,
            assign_last_annotator=assign_last_annotator,
            assigned_annotator_user_id=args.assigned_annotator_user_id,
            cancel_acceptance=args.cancel_acceptance,
            task_query=task_query,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    RejectTasks(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    parser.add_argument(
        "-c",
        "--comment",
        type=str,
        help="差し戻すときに付与する検査コメントを指定します。検査コメントはタスク内の先頭画像に付与します。付与する位置は ``--comment_data`` で指定できます。\n"
        "未指定の場合は、検査コメントを付与せずに差し戻します。",
    )

    parser.add_argument(
        "--comment_data",
        type=str,
        help="検査コメントの種類や付与する位置をJSON形式で指定します。"
        "指定方法は https://annofab-cli.readthedocs.io/ja/latest/command_reference/task/reject.html を参照してください。\n"
        "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。\n"
        "デフォルトの検査コメントの種類と位置は以下の通りです。\n"
        "\n"
        " * 画像プロジェクト：点。先頭画像の左上\n"
        " * 動画プロジェクト：区間。動画の先頭\n"
        " * カスタムプロジェクト(3dpc)：辺が1の立方体。原点\n",
    )

    parser.add_argument(
        "--custom_project_type",
        type=str,
        choices=[e.value for e in CustomProjectType],
        help="[BETA] カスタムプロジェクトの種類を指定します。ビルトインのエディタプラグインを使用していないカスタムプロジェクトに対して、検査コメントの位置を指定しない場合は必須です。\n",
    )

    # 差し戻したタスクの担当者の割当に関して
    assign_group = parser.add_mutually_exclusive_group()

    assign_group.add_argument(
        "--not_assign",
        action="store_true",
        help="差し戻したタスクに担当者を割り当てません。指定しない場合は、最後のannotation phaseの担当者が割り当てられます。",
    )

    assign_group.add_argument(
        "--assigned_annotator_user_id",
        type=str,
        help="差し戻したタスクに割り当てるユーザのuser_idを指定します。指定しない場合は、最後の教師付フェーズの担当者が割り当てられます。",
    )

    parser.add_argument("--cancel_acceptance", action="store_true", help="受入完了状態を取り消して、タスクを差し戻します。")

    argument_parser.add_task_query()

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "reject"
    subcommand_help = "タスクを差し戻します。"
    description = "タスクを差し戻します。差し戻す際、検査コメントを付与することもできます。作業中状態のタスクに対しては差し戻せません。"
    epilog = "オーナロールを持つユーザで実行してください。``--cancel_acceptance`` を指定していない AND ``--comment`` を指定している場合は、チェッカーロールを持つユーザーも実行できます。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
