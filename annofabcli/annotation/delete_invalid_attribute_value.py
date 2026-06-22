from __future__ import annotations

import argparse
import copy
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import annofabapi
import requests
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
class DeleteAttributeValueCount:
    """
    アノテーション属性値削除件数。
    """

    success: int
    """属性値の削除に成功したアノテーション数。"""

    failed: int
    """属性値の削除に失敗またはスキップしたアノテーション数。"""


@dataclass(frozen=True)
class DeleteAttributeValueRequest:
    """
    アノテーション属性値削除用のリクエスト情報。
    """

    request_body: dict[str, Any]
    """`put_annotation` APIに渡すリクエストボディ。"""

    count: DeleteAttributeValueCount
    """アノテーション属性値削除件数。"""


def get_allowed_attribute_ids_by_label_id(annotation_specs: dict[str, Any]) -> dict[str, set[str]]:
    """
    ラベルごとに、付与できる属性IDの集合を取得する。

    Args:
        annotation_specs: アノテーション仕様。

    Returns:
        ラベルIDをキー、ラベルに含まれる属性ID集合を値にしたdict。
    """
    return {label["label_id"]: set(label["additional_data_definitions"]) for label in annotation_specs["labels"]}


def filter_invalid_additional_data_list(additional_data_list: list[dict[str, Any]], allowed_attribute_ids: set[str]) -> list[dict[str, Any]]:
    """
    ラベルに含まれている属性IDの属性値だけを返す。

    Args:
        additional_data_list: アノテーションに設定されている属性値の一覧。
        allowed_attribute_ids: ラベルに含まれている属性IDの集合。

    Returns:
        ラベルに含まれていない属性値を除外した属性値一覧。
    """
    return [additional_data for additional_data in additional_data_list if additional_data["definition_id"] in allowed_attribute_ids]


def create_request_body_for_delete_attribute_value(
    editor_annotation: dict[str, Any],
    *,
    allowed_attribute_ids_by_label_id: dict[str, set[str]],
) -> DeleteAttributeValueRequest:
    """
    `put_annotation` に渡すリクエストボディを作成する。

    Args:
        editor_annotation: `get_editor_annotation` のレスポンス。
        allowed_attribute_ids_by_label_id: ラベルIDをキー、ラベルに含まれる属性ID集合を値にしたdict。

    Returns:
        リクエスト情報。
    """
    request_details: list[dict[str, Any]] = []
    changed_annotation_ids: set[str] = set()

    for detail in editor_annotation["details"]:
        new_detail = copy.deepcopy(detail)
        new_detail["_type"] = "Update"
        # アノテーションdataは変更しない。`body=None` を指定すると、putAnnotationでbodyが維持される。
        new_detail["body"] = None

        old_additional_data_list = detail["additional_data_list"]
        allowed_attribute_ids = allowed_attribute_ids_by_label_id[detail["label_id"]]
        new_additional_data_list = filter_invalid_additional_data_list(old_additional_data_list, allowed_attribute_ids)
        if len(old_additional_data_list) != len(new_additional_data_list):
            new_detail["additional_data_list"] = new_additional_data_list
            changed_annotation_ids.add(detail["annotation_id"])

        request_details.append(new_detail)

    request_body = {
        "project_id": editor_annotation["project_id"],
        "task_id": editor_annotation["task_id"],
        "input_data_id": editor_annotation["input_data_id"],
        "details": request_details,
        "updated_datetime": editor_annotation["updated_datetime"],
        "format_version": "2.0.0",
    }

    return DeleteAttributeValueRequest(
        request_body=request_body,
        count=DeleteAttributeValueCount(success=len(changed_annotation_ids), failed=0),
    )


class DeleteAnnotationAttributeValueMain(CommandLineWithConfirm):
    """
    アノテーションに設定されている属性値を削除する本体処理。
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

    def delete_attribute_value_for_input_data(self, task_id: str, input_data_id: str, allowed_attribute_ids_by_label_id: dict[str, set[str]]) -> DeleteAttributeValueCount:
        """
        1個の入力データに含まれるアノテーション属性値を削除する。

        Args:
            task_id: タスクID。
            input_data_id: 入力データID。
            allowed_attribute_ids_by_label_id: ラベルIDをキー、ラベルに含まれる属性ID集合を値にしたdict。

        Returns:
            属性値削除件数。
        """
        editor_annotation, _ = self.service.api.get_editor_annotation(self.project_id, task_id=task_id, input_data_id=input_data_id, query_params={"v": "2"})
        request = create_request_body_for_delete_attribute_value(editor_annotation, allowed_attribute_ids_by_label_id=allowed_attribute_ids_by_label_id)
        if request.count.success > 0:
            self.service.api.put_annotation(self.project_id, task_id, input_data_id, request_body=request.request_body, query_params={"v": "2"})
        else:
            logger.debug(f"task_id='{task_id}', input_data_id='{input_data_id}' :: ラベルに含まれていない属性値はありませんでした。")

        logger.debug(
            f"task_id='{task_id}', input_data_id='{input_data_id}' :: "
            f"{request.count.success} 件のアノテーションから、ラベルに含まれていない属性値を削除しました。"
            f"{request.count.failed} 件のアノテーションは属性値を削除できませんでした。"
        )
        return request.count

    def delete_attribute_value_for_task(
        self,
        task_id: str,
        *,
        allowed_attribute_ids_by_label_id: dict[str, set[str]],
        backup_dir: Path | None = None,
        task_index: int | None = None,
    ) -> tuple[bool, int]:
        """
        1個のタスクに含まれるアノテーション属性値を削除する。

        Args:
            task_id: タスクID。
            allowed_attribute_ids_by_label_id: ラベルIDをキー、ラベルに含まれる属性ID集合を値にしたdict。
            backup_dir: バックアップディレクトリ。
            task_index: 処理対象タスクのインデックス。

        Returns:
            tuple[0]: 更新処理を実行した場合はTrue。
            tuple[1]: 属性値を削除したアノテーション数。
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
                f"{logger_prefix}task_id='{task_id}' :: タスクが完了状態のため、スキップします。完了状態のタスクの属性値を削除するには、`--include_complete_task`オプションを指定してください。"
            )
            return result, deleted_annotation_count

        input_data_id_list = dict_task["input_data_id_list"]
        logger.info(
            f"{logger_prefix}task_id='{task_id}'の属性値削除対象候補の入力データ数は{len(input_data_id_list)}個です。"
            f" :: task_phase='{task.phase.value}', task_status='{task.status.value}', task_updated_datetime='{task.updated_datetime}'"
        )
        if len(input_data_id_list) == 0:
            logger.info(f"{logger_prefix}task_id='{task_id}'には入力データが存在しないので、スキップします。")
            return result, deleted_annotation_count

        if not self.confirm_processing(f"task_id='{task_id}' のアノテーションから、ラベルに含まれていない属性値を削除しますか？"):
            return result, deleted_annotation_count

        if backup_dir is not None:
            self.dump_annotation_obj.dump_annotation_for_task(task_id, output_dir=backup_dir)

        failed_annotation_count = 0
        for input_data_id in input_data_id_list:
            try:
                count = self.delete_attribute_value_for_input_data(task_id, input_data_id, allowed_attribute_ids_by_label_id)
                deleted_annotation_count += count.success
                failed_annotation_count += count.failed
            except requests.HTTPError:
                logger.warning(f"{logger_prefix}task_id='{task_id}', input_data_id='{input_data_id}' :: アノテーション属性値の削除に失敗しました。", exc_info=True)
                failed_annotation_count += 1
            except Exception:
                logger.warning(f"{logger_prefix}task_id='{task_id}', input_data_id='{input_data_id}' :: アノテーション属性値の削除に失敗しました。", exc_info=True)
                failed_annotation_count += 1

        if deleted_annotation_count == 0:
            logger.info(f"{logger_prefix}task_id='{task_id}'には、ラベルに含まれていない属性値が設定されているアノテーションが存在しません。")
        else:
            result = True
            logger.info(
                f"{logger_prefix}task_id='{task_id}': {deleted_annotation_count} 個のアノテーションから、ラベルに含まれていない属性値を削除しました。"
                f"{failed_annotation_count} 個のアノテーションは属性値を削除できませんでした。"
            )

        return result, deleted_annotation_count

    def delete_attribute_value_for_task_list(
        self,
        task_id_list: list[str],
        *,
        allowed_attribute_ids_by_label_id: dict[str, set[str]],
        backup_dir: Path | None = None,
    ) -> None:
        """
        複数のタスクに対して、アノテーション属性値を削除する。

        Args:
            task_id_list: タスクID一覧。
            allowed_attribute_ids_by_label_id: ラベルIDをキー、ラベルに含まれる属性ID集合を値にしたdict。
            backup_dir: バックアップディレクトリ。
        """
        project_title = self.facade.get_project_title(self.project_id)
        logger.info(f"プロジェクト'{project_title}'に対して、タスク{len(task_id_list)} 件のラベルに含まれていない属性値を削除します。")

        if backup_dir is not None:
            backup_dir.mkdir(exist_ok=True, parents=True)

        success_task_count = 0
        deleted_annotation_count = 0
        for task_index, task_id in enumerate(task_id_list):
            try:
                result, sub_deleted_annotation_count = self.delete_attribute_value_for_task(
                    task_id,
                    allowed_attribute_ids_by_label_id=allowed_attribute_ids_by_label_id,
                    backup_dir=backup_dir,
                    task_index=task_index,
                )
                deleted_annotation_count += sub_deleted_annotation_count
                if result:
                    success_task_count += 1
            except Exception:
                logger.warning(f"タスク'{task_id}'のアノテーション属性値の削除に失敗しました。", exc_info=True)

        logger.info(f"{success_task_count} / {len(task_id_list)} 件のタスクに対して {deleted_annotation_count} 件のアノテーションから、ラベルに含まれていない属性値を削除しました。")


class DeleteInvalidAttributeValueOfAnnotation(CommandLine):
    """
    アノテーション属性値を削除する。
    """

    COMMON_MESSAGE = "annofabcli annotation delete_invalid_attribute_value: error:"

    def main(self) -> None:
        args = self.args
        project_id = args.project_id
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

        annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params={"v": "3"})
        allowed_attribute_ids_by_label_id = get_allowed_attribute_ids_by_label_id(annotation_specs)

        if args.backup is None:
            print(  # noqa: T201
                "間違えてアノテーション属性値を削除してしまっときに復元できるようにするため、'--backup'でバックアップ用のディレクトリを指定することを推奨します。",
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

        main_obj = DeleteAnnotationAttributeValueMain(self.service, project_id=project_id, include_complete_task=args.include_complete_task, all_yes=args.yes)
        main_obj.delete_attribute_value_for_task_list(
            task_id_list,
            allowed_attribute_ids_by_label_id=allowed_attribute_ids_by_label_id,
            backup_dir=backup_dir,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteInvalidAttributeValueOfAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    argument_parser.add_task_id()

    parser.add_argument(
        "--include_complete_task",
        action="store_true",
        help="完了状態のタスクの、ラベルに含まれていない属性値も削除します。ただし、オーナーロールを持つユーザーでしか実行できません。",
    )

    parser.add_argument(
        "--backup",
        type=str,
        required=False,
        help="アノテーションのバックアップを保存するディレクトリを指定してください。アノテーションの復元は ``annotation restore`` コマンドで実現できます。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "delete_invalid_attribute_value"
    subcommand_help = "ラベルに含まれていない属性値を削除します。"
    description = (
        "ラベルに含まれていない属性値を一括で削除します。ただし、作業中状態のタスクに含まれるアノテーションは変更できません。"
        "完了状態のタスクに含まれるアノテーションは、デフォルトでは変更できません。"
        "間違えてアノテーション属性値を削除したときに復元できるようにするため、 ``--backup`` でバックアップ用のディレクトリを指定することを推奨します。"
    )
    epilog = "オーナロールまたはチェッカーロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
