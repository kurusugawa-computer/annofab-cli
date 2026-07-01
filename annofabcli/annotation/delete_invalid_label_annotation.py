from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import annofabapi
from annofabapi.dataclass.task import Task
from annofabapi.models import ProjectMemberRole, TaskStatus

import annofabcli.common.cli
from annofabcli.annotation.dump_annotation import DumpAnnotationMain
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeleteInvalidLabelAnnotationRequest:
    """
    不正なラベルを持つアノテーション削除用のリクエスト情報。
    """

    request_body: list[dict[str, Any]]
    """`batch_update_annotations` APIに渡すリクエストボディ。"""

    delete_count: int
    """削除対象のアノテーション数。"""


def get_existing_label_ids(annotation_specs: dict[str, Any]) -> set[str]:
    """
    アノテーション仕様に存在するラベルIDの集合を取得する。

    Args:
        annotation_specs: アノテーション仕様。

    Returns:
        アノテーション仕様に存在するラベルIDの集合。
    """
    return {label["label_id"] for label in annotation_specs["labels"]}


def create_request_body_for_delete_invalid_label_annotation(editor_annotation: dict[str, Any], *, existing_label_ids: set[str]) -> DeleteInvalidLabelAnnotationRequest:
    """
    `batch_update_annotations` に渡すリクエストボディを作成する。

    Args:
        editor_annotation: `get_editor_annotation` のレスポンス。
        existing_label_ids: アノテーション仕様に存在するラベルIDの集合。

    Returns:
        リクエスト情報。
    """

    def _to_request_body_elm(detail: dict[str, Any]) -> dict[str, Any]:
        return {
            "project_id": editor_annotation["project_id"],
            "task_id": editor_annotation["task_id"],
            "input_data_id": editor_annotation["input_data_id"],
            "updated_datetime": editor_annotation["updated_datetime"],
            "annotation_id": detail["annotation_id"],
            "_type": "Delete",
        }

    request_body = [_to_request_body_elm(detail) for detail in editor_annotation["details"] if detail["label_id"] not in existing_label_ids]
    return DeleteInvalidLabelAnnotationRequest(request_body=request_body, delete_count=len(request_body))


class DeleteInvalidLabelAnnotationMain(CommandLineWithConfirm):
    """
    アノテーション仕様に存在しないラベルを持つアノテーションを削除する本体処理。
    """

    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        project_id: str,
        include_complete_task: bool,
        all_yes: bool,
    ) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.project_id = project_id
        self.include_complete_task = include_complete_task
        self.dump_annotation_obj = DumpAnnotationMain(service, project_id)
        super().__init__(all_yes)

    def delete_invalid_label_annotation_for_input_data(self, task_id: str, input_data_id: str, existing_label_ids: set[str]) -> int:
        """
        1個の入力データに含まれる、アノテーション仕様に存在しないラベルを持つアノテーションを削除する。

        Args:
            task_id: タスクID。
            input_data_id: 入力データID。
            existing_label_ids: アノテーション仕様に存在するラベルIDの集合。

        Returns:
            削除したアノテーション数。
        """
        editor_annotation, _ = self.service.api.get_editor_annotation(self.project_id, task_id=task_id, input_data_id=input_data_id, query_params={"v": "2"})
        request = create_request_body_for_delete_invalid_label_annotation(editor_annotation, existing_label_ids=existing_label_ids)
        if request.delete_count > 0:
            self.service.api.batch_update_annotations(self.project_id, request_body=request.request_body, query_params={"v": "2"})
        else:
            logger.debug(f"task_id='{task_id}', input_data_id='{input_data_id}' :: アノテーション仕様に存在しないラベルを持つアノテーションはありませんでした。")

        logger.debug(f"task_id='{task_id}', input_data_id='{input_data_id}' :: アノテーション仕様に存在しないラベルを持つアノテーション {request.delete_count} 件を削除しました。")
        return request.delete_count

    def delete_invalid_label_annotation_for_task(
        self,
        task_id: str,
        *,
        existing_label_ids: set[str],
        backup_dir: Path | None = None,
        task_index: int | None = None,
    ) -> tuple[bool, int]:
        """
        1個のタスクに含まれる、アノテーション仕様に存在しないラベルを持つアノテーションを削除する。

        Args:
            task_id: タスクID。
            existing_label_ids: アノテーション仕様に存在するラベルIDの集合。
            backup_dir: バックアップディレクトリ。
            task_index: 処理対象タスクのインデックス。

        Returns:
            tuple[0]: 削除処理を実行した場合はTrue。
            tuple[1]: 削除したアノテーション数。
        """
        result = False
        deleted_annotation_count = 0
        logger_prefix = f"{task_index + 1!s} 件目 :: " if task_index is not None else ""
        dict_task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if dict_task is None:
            logger.warning(f"{logger_prefix}task_id='{task_id}'であるタスクは存在しません。")
            return result, deleted_annotation_count

        task: Task = Task.from_dict(dict_task)
        if task.status == TaskStatus.WORKING:
            logger.info(f"{logger_prefix}task_id='{task_id}' :: タスクが作業中状態のため、スキップします。")
            return result, deleted_annotation_count

        if not self.include_complete_task and task.status == TaskStatus.COMPLETE:
            logger.info(
                f"{logger_prefix}task_id='{task_id}' :: タスクが完了状態のため、スキップします。完了状態のタスクのアノテーションを削除するには、`--include_complete_task`オプションを指定してください。"
            )
            return result, deleted_annotation_count

        input_data_id_list = dict_task["input_data_id_list"]
        logger.info(
            f"{logger_prefix}task_id='{task_id}'の削除対象候補の入力データ数は{len(input_data_id_list)}個です。"
            f" :: task_phase='{task.phase.value}', task_status='{task.status.value}', task_updated_datetime='{task.updated_datetime}'"
        )
        if len(input_data_id_list) == 0:
            logger.info(f"{logger_prefix}task_id='{task_id}'には入力データが存在しないので、スキップします。")
            return result, deleted_annotation_count

        if not self.confirm_processing(f"task_id='{task_id}' のアノテーション仕様に存在しないラベルを持つアノテーションを削除しますか？"):
            return result, deleted_annotation_count

        if backup_dir is not None:
            self.dump_annotation_obj.dump_annotation_for_task(task_id, output_dir=backup_dir)

        failed_input_data_count = 0
        for input_data_id in input_data_id_list:
            try:
                deleted_annotation_count += self.delete_invalid_label_annotation_for_input_data(task_id, input_data_id, existing_label_ids)
            except Exception:
                logger.warning(f"{logger_prefix}task_id='{task_id}', input_data_id='{input_data_id}' :: 不正なラベルを持つアノテーションの削除に失敗しました。", exc_info=True)
                failed_input_data_count += 1

        if deleted_annotation_count > 0:
            result = True
            logger.info(
                f"{logger_prefix}task_id='{task_id}': アノテーション仕様に存在しないラベルを持つアノテーション {deleted_annotation_count} 件を削除しました。"
                f"{failed_input_data_count} 個の入力データは処理に失敗しました。"
            )
        elif failed_input_data_count > 0:
            logger.info(f"{logger_prefix}task_id='{task_id}': 削除したアノテーションはありません。{failed_input_data_count} 個の入力データは処理に失敗しました。")
        else:
            logger.info(f"{logger_prefix}task_id='{task_id}'には、アノテーション仕様に存在しないラベルを持つアノテーションが存在しません。")

        return result, deleted_annotation_count

    def delete_invalid_label_annotation_for_task_list(
        self,
        task_id_list: list[str],
        *,
        existing_label_ids: set[str],
        backup_dir: Path | None = None,
    ) -> None:
        """
        複数のタスクに対して、アノテーション仕様に存在しないラベルを持つアノテーションを削除する。

        Args:
            task_id_list: タスクID一覧。
            existing_label_ids: アノテーション仕様に存在するラベルIDの集合。
            backup_dir: バックアップディレクトリ。
        """
        project_title = self.facade.get_project_title(self.project_id)
        logger.info(f"プロジェクト'{project_title}'に対して、タスク{len(task_id_list)} 件の不正なラベルを持つアノテーションを削除します。")

        if backup_dir is not None:
            backup_dir.mkdir(exist_ok=True, parents=True)

        success_task_count = 0
        deleted_annotation_count = 0
        for task_index, task_id in enumerate(task_id_list):
            try:
                result, sub_deleted_annotation_count = self.delete_invalid_label_annotation_for_task(
                    task_id,
                    existing_label_ids=existing_label_ids,
                    backup_dir=backup_dir,
                    task_index=task_index,
                )
                deleted_annotation_count += sub_deleted_annotation_count
                if result:
                    success_task_count += 1
            except Exception:
                logger.warning(f"タスク'{task_id}'の不正なラベルを持つアノテーションの削除に失敗しました。", exc_info=True)

        logger.info(f"{success_task_count} / {len(task_id_list)} 件のタスクに対して、アノテーション仕様に存在しないラベルを持つアノテーション {deleted_annotation_count} 件を削除しました。")


class DeleteInvalidLabelAnnotationOfAnnotation(CommandLine):
    """
    アノテーション仕様に存在しないラベルを持つアノテーションを削除する。
    """

    COMMON_MESSAGE = "annofabcli annotation delete_invalid_label_annotation: error:"

    def main(self) -> None:
        args = self.args
        project_id = args.project_id
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

        annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params={"v": "3"})
        existing_label_ids = get_existing_label_ids(annotation_specs)

        if args.backup is None:
            print(  # noqa: T201
                "間違えてアノテーションを削除してしまったときに復元できるようにするため、'--backup'でバックアップ用のディレクトリを指定することを推奨します。",
                file=sys.stderr,
            )
            if not self.confirm_processing("復元用のバックアップディレクトリが指定されていません。処理を続行しますか？"):
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            backup_dir = None
        else:
            backup_dir = Path(args.backup)

        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])
        if args.include_complete_task and not self.facade.contains_any_project_member_role(project_id, [ProjectMemberRole.OWNER]):
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --include_complete_task : '--include_complete_task' 引数を利用するにはプロジェクトのオーナーロールを持つユーザーで実行する必要があります。",
                file=sys.stderr,
            )
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        main_obj = DeleteInvalidLabelAnnotationMain(self.service, project_id=project_id, include_complete_task=args.include_complete_task, all_yes=args.yes)
        main_obj.delete_invalid_label_annotation_for_task_list(
            task_id_list,
            existing_label_ids=existing_label_ids,
            backup_dir=backup_dir,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteInvalidLabelAnnotationOfAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    argument_parser.add_task_id()

    parser.add_argument(
        "--include_complete_task",
        action="store_true",
        help="完了状態のタスクの、アノテーション仕様に存在しないラベルを持つアノテーションも削除します。ただし、オーナーロールを持つユーザーでしか実行できません。",
    )

    parser.add_argument(
        "--backup",
        type=str,
        required=False,
        help="アノテーションのバックアップを保存するディレクトリを指定してください。アノテーションの復元は ``annotation restore`` コマンドで実現できます。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "delete_invalid_label_annotation"
    subcommand_help = "アノテーション仕様に存在しないラベルを持つアノテーションを削除します。"
    description = (
        "アノテーション仕様に存在しないラベルを持つアノテーションを一括で削除します。ただし、作業中状態のタスクに含まれるアノテーションは削除できません。"
        "完了状態のタスクに含まれるアノテーションは、デフォルトでは削除できません。"
        "間違えてアノテーションを削除したときに復元できるようにするため、 ``--backup`` でバックアップ用のディレクトリを指定することを推奨します。"
    )
    epilog = "オーナロールまたはチェッカーロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
