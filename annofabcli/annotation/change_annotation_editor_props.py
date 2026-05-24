from __future__ import annotations

import argparse
import copy
import json
import logging
import multiprocessing
import sys
from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import annofabapi
import pydantic
from annofabapi.models import ProjectMemberRole, TaskStatus
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor
from annofabapi.utils import can_put_annotation

import annofabcli.common.cli
from annofabcli.annotation.dump_annotation import DumpAnnotationMain
from annofabcli.annotation.import_annotation import validate_editor_props_for_cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
    get_json_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChangeEditorPropsCount:
    """`editor_props` 変更件数。"""

    success: int
    """変更に成功したアノテーション数。"""

    failed: int
    """変更に失敗またはスキップしたアノテーション数。"""


@dataclass(frozen=True)
class ChangeEditorPropsRequest:
    """`editor_props` 変更用のリクエスト情報。"""

    request_body: dict[str, Any]
    """`put_annotation` APIに渡すリクエストボディ。"""

    count: ChangeEditorPropsCount
    """`editor_props` 変更件数。"""


def get_label_ids_from_label_names(annotation_specs: dict[str, Any], label_names: Collection[str]) -> set[str]:
    """ラベル名（英語）の集合に対応するラベルIDの集合を取得する。"""
    accessor = AnnotationSpecsAccessor(annotation_specs)
    return {accessor.get_label(label_name=label_name)["label_id"] for label_name in label_names}


def get_annotation_ids_per_input_data_id(annotation_list: list[dict[str, Any]], target_label_ids: set[str]) -> dict[str, set[str]]:
    """入力データIDごとに、変更対象のアノテーションIDをまとめる。

    Args:
        annotation_list: `listAnnotation` APIのレスポンス。
        target_label_ids: 変更対象のラベルID。

    Returns:
        入力データIDをキー、アノテーションIDの集合を値にした辞書。
    """
    result: dict[str, set[str]] = defaultdict(set)
    for annotation in annotation_list:
        detail = annotation["detail"]
        if detail["label_id"] not in target_label_ids:
            continue
        result[annotation["input_data_id"]].add(detail["annotation_id"])
    return result


def create_request_body_for_change_editor_props(
    editor_annotation: dict[str, Any],
    target_annotation_ids: set[str],
    editor_props: dict[str, Any],
) -> ChangeEditorPropsRequest:
    """`put_annotation` に渡すリクエストボディを作成する。

    Args:
        editor_annotation: `get_editor_annotation` のレスポンス。
        target_annotation_ids: 変更対象のアノテーションID。
        editor_props: 変更後の `editor_props`。既存の `editor_props` にマージされる。

    Returns:
        リクエスト情報。
    """
    request_details: list[dict[str, Any]] = []
    changed_annotation_ids: set[str] = set()

    for detail in editor_annotation["details"]:
        new_detail = copy.deepcopy(detail)
        new_detail.pop("url", None)
        new_detail["_type"] = "Update"
        new_detail["body"] = None

        annotation_id = detail["annotation_id"]
        if annotation_id in target_annotation_ids:
            new_detail["editor_props"] = {**detail.get("editor_props", {}), **editor_props}
            changed_annotation_ids.add(annotation_id)

        request_details.append(new_detail)

    failed_count = len(target_annotation_ids - changed_annotation_ids)
    for annotation_id in target_annotation_ids - changed_annotation_ids:
        logger.warning(
            f"task_id='{editor_annotation['task_id']}', input_data_id='{editor_annotation['input_data_id']}' :: "
            f"annotation_id='{annotation_id}'であるアノテーションが存在しないため、このアノテーションのeditor_propsの変更をスキップします。"
        )

    request_body = {
        "project_id": editor_annotation["project_id"],
        "task_id": editor_annotation["task_id"],
        "input_data_id": editor_annotation["input_data_id"],
        "details": request_details,
        "updated_datetime": editor_annotation["updated_datetime"],
        "format_version": "2.0.0",
    }

    return ChangeEditorPropsRequest(
        request_body=request_body,
        count=ChangeEditorPropsCount(success=len(changed_annotation_ids), failed=failed_count),
    )


class ChangeAnnotationEditorPropsMain(CommandLineWithConfirm):
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        project_id: str,
        target_label_ids: set[str],
        editor_props: dict[str, Any],
        change_operator_to_me: bool,
        include_complete_task: bool,
        include_on_hold_task: bool,
        all_yes: bool,
        backup_dir: Path | None = None,
    ) -> None:
        self.service = service
        self.project_id = project_id
        self.target_label_ids = target_label_ids
        self.editor_props = editor_props
        self.change_operator_to_me = change_operator_to_me
        self.include_complete_task = include_complete_task
        self.include_on_hold_task = include_on_hold_task
        self.backup_dir = backup_dir
        self.dump_annotation_obj = DumpAnnotationMain(service, project_id)
        super().__init__(all_yes)

    def get_annotation_list_for_task(self, task_id: str) -> list[dict[str, Any]]:
        """タスク内の変更対象ラベルのアノテーション一覧を取得する。"""
        result: list[dict[str, Any]] = []
        for label_id in self.target_label_ids:
            dict_query = {"task_id": task_id, "exact_match_task_id": True, "label_id": label_id}
            result.extend(self.service.wrapper.get_all_annotation_list(self.project_id, query_params={"query": dict_query}))
        return result

    def change_editor_props_by_input_data(self, task_id: str, input_data_id: str, annotation_ids: set[str]) -> ChangeEditorPropsCount:
        """1個の入力データに含まれるアノテーションの `editor_props` を変更する。"""
        editor_annotation, _ = self.service.api.get_editor_annotation(self.project_id, task_id=task_id, input_data_id=input_data_id, query_params={"v": "2"})

        if self.backup_dir is not None:
            (self.backup_dir / task_id).mkdir(exist_ok=True, parents=True)
            self.dump_annotation_obj.dump_editor_annotation(editor_annotation, json_path=self.backup_dir / task_id / f"{input_data_id}.json")

        request = create_request_body_for_change_editor_props(editor_annotation, annotation_ids, self.editor_props)
        if request.count.success > 0:
            self.service.api.put_annotation(self.project_id, task_id, input_data_id, request_body=request.request_body, query_params={"v": "2"})
        else:
            logger.debug(f"task_id='{task_id}', input_data_id='{input_data_id}' :: 変更対象のアノテーションがありませんでした。")

        logger.debug(
            f"task_id='{task_id}', input_data_id='{input_data_id}' :: "
            f"{request.count.success}/{len(annotation_ids)} 件のeditor_propsを変更しました。"
            f"{request.count.failed} 件のアノテーションは変更できませんでした。"
        )
        return request.count

    def change_editor_props_for_task(self, task_id: str, task_index: int | None = None) -> tuple[bool, ChangeEditorPropsCount]:  # noqa: PLR0911, PLR0912
        """1個のタスクに含まれるアノテーションの `editor_props` を変更する。"""
        logger_prefix = f"{task_index + 1!s} 件目 :: " if task_index is not None else ""
        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"{logger_prefix}task_id='{task_id}' :: タスクが存在しません。")
            return False, ChangeEditorPropsCount(success=0, failed=0)

        logger.debug(f"{logger_prefix}task_id='{task_id}', phase='{task['phase']}', status='{task['status']}'")
        if task["status"] == TaskStatus.WORKING.value:
            logger.info(f"{logger_prefix}task_id='{task_id}' :: タスクが作業中状態のため、editor_propsの変更をスキップします。")
            return False, ChangeEditorPropsCount(success=0, failed=0)

        if not self.include_complete_task and task["status"] == TaskStatus.COMPLETE.value:
            logger.info(
                f"{logger_prefix}task_id='{task_id}' :: タスクが完了状態のため、editor_propsの変更をスキップします。"
                "完了状態のタスクのアノテーションも変更するには、`--include_complete_task` オプションを指定してください。"
            )
            return False, ChangeEditorPropsCount(success=0, failed=0)

        if not self.include_on_hold_task and task["status"] == TaskStatus.ON_HOLD.value:
            logger.info(
                f"{logger_prefix}task_id='{task_id}' :: タスクが保留中状態のため、editor_propsの変更をスキップします。"
                "保留中状態のタスクのアノテーションも変更するには、`--include_on_hold_task` オプションを指定してください。"
            )
            return False, ChangeEditorPropsCount(success=0, failed=0)

        old_account_id: str | None = task["account_id"]
        changed_operator = False
        if self.change_operator_to_me:
            if not can_put_annotation(task, self.service.api.account_id):
                logger.debug(f"{logger_prefix}task_id='{task_id}' :: 担当者を自分自身に変更します。")
                task = self.service.wrapper.change_task_operator(
                    self.project_id,
                    task_id,
                    operator_account_id=self.service.api.account_id,
                    last_updated_datetime=task["updated_datetime"],
                )
                changed_operator = True

        else:  # noqa: PLR5501
            if not can_put_annotation(task, self.service.api.account_id):
                logger.debug(
                    f"{logger_prefix}task_id='{task_id}'は、過去に誰かに割り当てられたタスクで、現在の担当者が自分自身でないため、"
                    "アノテーションのeditor_propsの変更をスキップします。"
                    "担当者を自分自身に変更してeditor_propsを変更する場合は `--change_operator_to_me` を指定してください。"
                )
                return False, ChangeEditorPropsCount(success=0, failed=0)

        try:
            annotation_list = self.get_annotation_list_for_task(task_id)
            annotation_ids_per_input_data_id = get_annotation_ids_per_input_data_id(annotation_list, self.target_label_ids)
            target_annotation_count = sum(len(v) for v in annotation_ids_per_input_data_id.values())
            logger.info(f"{logger_prefix}task_id='{task_id}'の変更対象アノテーション数：{target_annotation_count}")
            if target_annotation_count == 0:
                logger.info(f"{logger_prefix}task_id='{task_id}'には変更対象のアノテーションが存在しないので、スキップします。")
                return False, ChangeEditorPropsCount(success=0, failed=0)

            if not self.confirm_processing(f"task_id='{task_id}' に含まれるアノテーション{target_annotation_count}件のeditor_propsを変更しますか？"):
                return False, ChangeEditorPropsCount(success=0, failed=target_annotation_count)

            success_count = 0
            failed_count = 0
            for input_data_id, annotation_ids in annotation_ids_per_input_data_id.items():
                try:
                    count = self.change_editor_props_by_input_data(task_id, input_data_id, annotation_ids)
                    success_count += count.success
                    failed_count += count.failed
                except Exception:
                    logger.warning(f"task_id='{task_id}', input_data_id='{input_data_id}' :: アノテーションのeditor_propsの変更に失敗しました。", exc_info=True)
                    failed_count += len(annotation_ids)
                    continue

            return success_count > 0, ChangeEditorPropsCount(success=success_count, failed=failed_count)

        finally:
            if changed_operator:
                logger.debug(f"{logger_prefix}task_id='{task_id}' :: 担当者を元に戻します。")
                self.service.wrapper.change_task_operator(
                    self.project_id,
                    task_id,
                    operator_account_id=old_account_id,
                    last_updated_datetime=task["updated_datetime"],
                )

    def change_editor_props_for_task_wrapper(self, tpl: tuple[int, str]) -> tuple[bool, ChangeEditorPropsCount]:
        task_index, task_id = tpl
        try:
            return self.change_editor_props_for_task(task_id, task_index=task_index)
        except Exception:
            logger.warning(f"task_id='{task_id}' :: アノテーションのeditor_propsの変更に失敗しました。", exc_info=True)
            return False, ChangeEditorPropsCount(success=0, failed=0)

    def change_editor_props_for_task_list(self, task_id_list: list[str], parallelism: int | None = None) -> None:
        """複数タスクに対してアノテーションの `editor_props` を変更する。"""
        if self.backup_dir is not None:
            self.backup_dir.mkdir(exist_ok=True, parents=True)

        changed_task_count = 0
        total_success_count = 0
        total_failed_count = 0
        if parallelism is not None:
            with multiprocessing.Pool(parallelism) as pool:
                result_list = pool.map(self.change_editor_props_for_task_wrapper, enumerate(task_id_list))
        else:
            result_list = []
            for task_index, task_id in enumerate(task_id_list):
                logger.debug(f"{task_index + 1} / {len(task_id_list)} 件目: task_id='{task_id}'のアノテーションのeditor_propsを変更します。")
                result_list.append(self.change_editor_props_for_task(task_id, task_index=task_index))

        for is_changed, count in result_list:
            if is_changed:
                changed_task_count += 1
            total_success_count += count.success
            total_failed_count += count.failed

        logger.info(
            f"{changed_task_count} / {len(task_id_list)} 件のタスクに対してアノテーションのeditor_propsを変更しました。成功: {total_success_count} 件、失敗またはスキップ: {total_failed_count} 件"
        )


class ChangeAnnotationEditorProps(CommandLine):
    """
    アノテーションの `editor_props` を変更する。
    """

    COMMON_MESSAGE = "annofabcli annotation change_editor_props: error:"

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

        project_id = args.project_id
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        label_names = set(annofabcli.common.cli.get_list_from_args(args.label_name))
        if len(label_names) == 0:
            print(f"{self.COMMON_MESSAGE} argument '--label_name' には1個以上のラベル名を指定してください。", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        try:
            editor_props = validate_editor_props_for_cli(get_json_from_args(args.editor_props))
        except (json.JSONDecodeError, pydantic.ValidationError) as e:
            print(f"{self.COMMON_MESSAGE} argument '--editor_props' の値が不正です。{e}", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
        if len(editor_props) == 0:
            print(f"{self.COMMON_MESSAGE} argument '--editor_props' には1個以上のキーを指定してください。", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params={"v": "3"})
        try:
            target_label_ids = get_label_ids_from_label_names(annotation_specs, label_names)
        except ValueError as e:
            print(f"{self.COMMON_MESSAGE} argument '--label_name' の値が不正です。{e}", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        if args.backup is None:
            print(  # noqa: T201
                "間違えてアノテーションを変更してしまったときに復元できるようにするため、'--backup'でバックアップ用のディレクトリを指定することを推奨します。",
                file=sys.stderr,
            )
            if not self.confirm_processing("復元用のバックアップディレクトリが指定されていません。処理を続行しますか？"):
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            backup_dir = None
        else:
            backup_dir = Path(args.backup)

        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        main_obj = ChangeAnnotationEditorPropsMain(
            self.service,
            project_id=project_id,
            target_label_ids=target_label_ids,
            editor_props=editor_props,
            change_operator_to_me=args.change_operator_to_me,
            include_complete_task=args.include_complete_task,
            include_on_hold_task=args.include_on_hold_task,
            all_yes=args.yes,
            backup_dir=backup_dir,
        )
        main_obj.change_editor_props_for_task_list(task_id_list, parallelism=args.parallelism)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeAnnotationEditorProps(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    parser.add_argument(
        "--label_name",
        type=str,
        nargs="+",
        required=True,
        help="変更対象のアノテーションのラベル名（英語）を指定します。複数指定できます。``file://`` を先頭に付けると、ラベル名が記載されたファイルを指定できます。",
    )

    EXAMPLE_EDITOR_PROPS = '{"can_delete": false, "can_edit_data": false, "can_edit_additional": false}'  # noqa: N806
    parser.add_argument(
        "--editor_props",
        type=str,
        required=True,
        help=f"変更後のエディタ用プロパティをJSON形式で指定します。"
        f"指定できるキーは ``can_delete``, ``can_edit_data``, ``can_edit_additional`` です。"
        f"``file://`` を先頭に付けると、JSON形式のファイルを指定できます。(ex): ``{EXAMPLE_EDITOR_PROPS}``",
    )

    parser.add_argument(
        "--change_operator_to_me",
        action="store_true",
        help="過去に割り当てられていて現在の担当者が自分自身でない場合、タスクの担当者を自分自身に変更してからアノテーションのeditor_propsを変更します。",
    )

    parser.add_argument(
        "--include_complete_task",
        action="store_true",
        help="完了状態のタスクに含まれるアノテーションのeditor_propsも変更します。ただし、オーナーロールを持つユーザーでしか実行できません。",
    )

    parser.add_argument(
        "--include_on_hold_task",
        action="store_true",
        help="保留中状態のタスクに含まれるアノテーションのeditor_propsも変更します。",
    )

    parser.add_argument(
        "--backup",
        type=str,
        required=False,
        help="アノテーションのバックアップを保存するディレクトリを指定してください。アノテーションの復元は ``annotation restore`` コマンドで実現できます。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="並列度。指定しない場合は、逐次的に処理します。指定した場合は、``--yes`` も指定してください。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "change_editor_props"
    subcommand_help = "アノテーションのeditor_propsを変更します。"
    description = (
        "指定したラベル名のアノテーションに対して、editor_props（削除禁止などのプロパティ）を一括で変更します。ただし、作業中状態のタスクに含まれるアノテーションは変更できません。"
        "間違えてアノテーションのeditor_propsを変更したときに復元できるようにするため、 ``--backup`` でバックアップ用のディレクトリを指定することを推奨します。"
    )
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
