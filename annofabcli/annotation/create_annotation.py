from __future__ import annotations

import argparse
import copy
import json
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import annofabapi
import pandas
import pydantic
from annofabapi.models import ProjectMemberRole
from annofabapi.pydantic_models.task_status import TaskStatus
from pydantic import BaseModel

import annofabcli.common.cli
from annofabcli.annotation.annotation_query import AttributeValue
from annofabcli.annotation.dump_annotation import DumpAnnotationMain
from annofabcli.annotation.editor_props import validate_editor_props_for_cli
from annofabcli.annotation.import_annotation import AnnotationConverter, ImportedSimpleAnnotationDetail
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
    get_json_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class CreateAnnotationItem(BaseModel):
    """新規作成するアノテーション。"""

    task_id: str
    """タスクID。"""

    input_data_id: str
    """入力データID。"""

    label: str
    """アノテーション仕様のラベル名(英語)。"""

    data: dict[str, Any]
    """アノテーションのdata。"""

    annotation_id: str | None = None
    """アノテーションID。省略時は自動採番する。"""

    attributes: dict[str, AttributeValue] | None = None
    """属性情報。"""

    editor_props: dict[str, Any] | None = None
    """アノテーションエディタ用のプロパティ。"""


@dataclass(frozen=True)
class CreateAnnotationCount:
    """アノテーション作成件数。"""

    success: int
    """作成に成功した件数。"""

    failed: int
    """作成に失敗またはスキップした件数。"""


@dataclass(frozen=True)
class CreateAnnotationRequest:
    """アノテーション作成用のリクエスト情報。"""

    request_body: dict[str, Any]
    """`put_annotation` APIに渡すリクエストボディ。"""

    count: CreateAnnotationCount
    """作成件数。"""


def group_annotation_items(items: list[CreateAnnotationItem]) -> dict[str, dict[str, list[CreateAnnotationItem]]]:
    """アノテーションをタスクIDと入力データIDごとにグループ化する。"""
    result: dict[str, dict[str, list[CreateAnnotationItem]]] = defaultdict(lambda: defaultdict(list))
    for item in items:
        result[item.task_id][item.input_data_id].append(item)
    return result


def create_request_body(
    editor_annotation: dict[str, Any],
    items: list[CreateAnnotationItem],
    *,
    converter: AnnotationConverter,
) -> CreateAnnotationRequest:
    """既存アノテーションを変更せず、新規アノテーションを追加するリクエストを作成する。"""
    request_details: list[dict[str, Any]] = []
    annotation_ids = set()
    for detail in editor_annotation["details"]:
        old_detail = copy.deepcopy(detail)
        old_detail["_type"] = "Update"
        old_detail["body"] = None
        request_details.append(old_detail)
        annotation_ids.add(detail["annotation_id"])

    failed_count = 0
    for item in items:
        try:
            editor_props = validate_editor_props_for_cli(item.editor_props)
            request_detail = converter.convert_annotation_detail(
                None,
                ImportedSimpleAnnotationDetail(
                    label=item.label,
                    data=item.data,
                    attributes=item.attributes,
                    annotation_id=item.annotation_id,
                    editor_props=editor_props,
                ),
                log_message_suffix=f"task_id='{item.task_id}', input_data_id='{item.input_data_id}', annotation_id='{item.annotation_id}'",
            )
        except Exception as e:
            logger.warning(
                f"task_id='{item.task_id}', input_data_id='{item.input_data_id}', annotation_id='{item.annotation_id}' :: アノテーションを作成できません。 :: {e}",
                exc_info=True,
            )
            failed_count += 1
            continue

        annotation_id = request_detail["annotation_id"]
        if annotation_id in annotation_ids:
            logger.warning(
                f"task_id='{item.task_id}', input_data_id='{item.input_data_id}', annotation_id='{annotation_id}' :: 同じannotation_idのアノテーションが既に存在するため、作成をスキップします。"
            )
            failed_count += 1
            continue

        annotation_ids.add(annotation_id)
        request_details.append(request_detail)

    request_body = {
        "project_id": editor_annotation["project_id"],
        "task_id": editor_annotation["task_id"],
        "input_data_id": editor_annotation["input_data_id"],
        "details": request_details,
        "updated_datetime": editor_annotation["updated_datetime"],
        "format_version": "2.0.0",
    }
    return CreateAnnotationRequest(
        request_body=request_body,
        count=CreateAnnotationCount(success=len(request_details) - len(editor_annotation["details"]), failed=failed_count),
    )


class CreateAnnotationMain(CommandLineWithConfirm):
    """アノテーションを新規作成する。"""

    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        project_id: str,
        include_complete_task: bool,
        include_on_hold_task: bool,
        all_yes: bool,
        converter: AnnotationConverter,
        backup_dir: Path | None,
    ) -> None:
        super().__init__(all_yes)
        self.service = service
        self.project_id = project_id
        self.include_complete_task = include_complete_task
        self.include_on_hold_task = include_on_hold_task
        self.converter = converter
        self.backup_dir = backup_dir
        self.dump_annotation_obj = DumpAnnotationMain(service, project_id)

    def create_for_input_data(self, task_id: str, input_data_id: str, items: list[CreateAnnotationItem]) -> CreateAnnotationCount:
        """1個の入力データにアノテーションを作成する。"""
        editor_annotation, _ = self.service.api.get_editor_annotation(self.project_id, task_id, input_data_id, query_params={"v": "2"})
        request = create_request_body(editor_annotation, items, converter=self.converter)
        if request.count.success == 0:
            return request.count

        if self.backup_dir is not None:
            backup_path = self.backup_dir / task_id / f"{input_data_id}.json"
            backup_path.parent.mkdir(exist_ok=True, parents=True)
            self.dump_annotation_obj.dump_editor_annotation(editor_annotation, json_path=backup_path)

        self.service.api.put_annotation(self.project_id, task_id, input_data_id, request_body=request.request_body, query_params={"v": "2"})
        return request.count

    def create_for_task(self, task_id: str, items_by_input_data_id: dict[str, list[CreateAnnotationItem]]) -> CreateAnnotationCount:
        """1個のタスクに含まれるアノテーションを作成する。"""
        total_count = sum(len(items) for items in items_by_input_data_id.values())
        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None or task["status"] == TaskStatus.WORKING.value:
            logger.info(f"task_id='{task_id}' :: タスクが存在しない、または作業中状態のため、アノテーション{total_count}件の作成をスキップします。")
            return CreateAnnotationCount(success=0, failed=total_count)
        if task["status"] == TaskStatus.COMPLETE.value and not self.include_complete_task:
            logger.info(f"task_id='{task_id}' :: タスクが完了状態のため、アノテーション{total_count}件の作成をスキップします。")
            return CreateAnnotationCount(success=0, failed=total_count)
        if task["status"] == TaskStatus.ON_HOLD.value and not self.include_on_hold_task:
            logger.info(f"task_id='{task_id}' :: タスクが保留中状態のため、アノテーション{total_count}件の作成をスキップします。")
            return CreateAnnotationCount(success=0, failed=total_count)
        if not self.confirm_processing(f"task_id='{task_id}'に含まれるアノテーション{total_count}件を作成しますか？"):
            return CreateAnnotationCount(success=0, failed=total_count)

        success_count = 0
        failed_count = 0
        for input_data_id, input_items in items_by_input_data_id.items():
            try:
                count = self.create_for_input_data(task_id, input_data_id, input_items)
                success_count += count.success
                failed_count += count.failed
            except Exception:
                logger.warning(f"task_id='{task_id}', input_data_id='{input_data_id}' :: アノテーションの作成に失敗しました。", exc_info=True)
                failed_count += len(input_items)
        return CreateAnnotationCount(success=success_count, failed=failed_count)

    def create(self, items: list[CreateAnnotationItem]) -> None:
        """アノテーションを作成する。"""
        grouped_items = group_annotation_items(items)
        success_count = 0
        failed_count = 0
        for task_id, items_by_input_data_id in grouped_items.items():
            count = self.create_for_task(task_id, items_by_input_data_id)
            success_count += count.success
            failed_count += count.failed
        logger.info(f"{success_count}/{len(items)} 件のアノテーションを作成しました。{failed_count}件のアノテーションは作成できませんでした。")


class CreateAnnotation(CommandLine):
    """アノテーションを新規作成する。"""

    COMMON_MESSAGE = "annofabcli annotation create: error:"

    def main(self) -> None:
        args = self.args
        if args.json is not None:
            input_items = get_json_from_args(args.json)
            if not isinstance(input_items, list):
                print(f"{self.COMMON_MESSAGE} argument --json: JSON形式が不正です。オブジェクトの配列を指定してください。", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            items = [CreateAnnotationItem.model_validate(item) for item in input_items]
        else:
            dataframe = pandas.read_csv(args.csv, dtype="string")
            items = [
                CreateAnnotationItem(
                    task_id=item["task_id"],
                    input_data_id=item["input_data_id"],
                    label=item["label"],
                    data=json.loads(item["data"]),
                    annotation_id=item.get("annotation_id"),
                    attributes=json.loads(item["attributes"]) if item.get("attributes") is not None else None,
                    editor_props=json.loads(item["editor_props"]) if item.get("editor_props") is not None else None,
                )
                for item in dataframe.to_dict(orient="records")
            ]

        if args.backup is None:
            print("間違えてアノテーションを作成したときに復元できるようにするため、'--backup'でバックアップ用のディレクトリを指定することを推奨します。", file=sys.stderr)  # noqa: T201
            if not self.confirm_processing("復元用のバックアップディレクトリが指定されていません。処理を続行しますか？"):
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
        if args.include_complete_task and not self.facade.contains_any_project_member_role(args.project_id, [ProjectMemberRole.OWNER]):
            print(f"{self.COMMON_MESSAGE} argument --include_complete_task: オーナーロールを持つユーザーで実行する必要があります。", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        try:
            default_editor_props = validate_editor_props_for_cli(get_json_from_args(args.editor_props))
        except (json.JSONDecodeError, pydantic.ValidationError) as e:
            print(f"{self.COMMON_MESSAGE} argument --editor_props の値が不正です。{e}", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        super().validate_project(args.project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])
        annotation_specs, _ = self.service.api.get_annotation_specs(args.project_id, query_params={"v": "3"})
        project, _ = self.service.api.get_project(args.project_id)
        converter = AnnotationConverter(project, annotation_specs, service=self.service, is_strict=True, default_editor_props=default_editor_props)
        CreateAnnotationMain(
            self.service,
            project_id=args.project_id,
            include_complete_task=args.include_complete_task,
            include_on_hold_task=args.include_on_hold_task,
            all_yes=args.yes,
            converter=converter,
            backup_dir=Path(args.backup) if args.backup is not None else None,
        ).create(items)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CreateAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--json", type=str, help="各アノテーションの作成内容を記載したJSONリストを指定します。``file://`` を先頭に付けるとJSON形式のファイルを指定できます。")
    input_group.add_argument("--csv", type=str, help="各アノテーションの作成内容を記載したCSVファイルを指定します。`task_id`, `input_data_id`, `label`, `data` カラムが必要です。")
    parser.add_argument("--editor_props", type=str, help="作成する全アノテーションに付与するエディタ用プロパティをJSON形式で指定します。``file://`` を先頭に付けるとJSON形式のファイルを指定できます。")
    parser.add_argument("--include_complete_task", action="store_true", help="完了状態のタスクにもアノテーションを作成します。オーナーロールが必要です。")
    parser.add_argument("--include_on_hold_task", action="store_true", help="保留中状態のタスクにもアノテーションを作成します。")
    parser.add_argument("--backup", type=Path, help="アノテーションのバックアップを保存するディレクトリのパス。アノテーションの復元は ``annotation restore`` コマンドで実現できます。")
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    parser = annofabcli.common.cli.add_parser(
        subparsers,
        "create",
        "各アノテーションを新規作成します。",
        "各アノテーションを新規作成します。既存アノテーションは更新または削除しません。既存のannotation_idと一致する場合、そのアノテーションは作成せずにスキップします。",
        epilog="オーナーロールまたはチェッカーロールを持つユーザーで実行してください。",
    )
    parse_args(parser)
    return parser
