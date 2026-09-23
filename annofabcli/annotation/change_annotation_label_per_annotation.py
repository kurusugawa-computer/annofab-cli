from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import annofabapi
import pandas
from annofabapi.models import ProjectMemberRole
from annofabapi.pydantic_models.task_status import TaskStatus
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor
from pydantic import BaseModel

import annofabcli.common.cli
from annofabcli.annotation.change_annotation_label import DestLabelInfo, get_label_id_from_name_or_id, is_allowed_label_change
from annofabcli.annotation.dump_annotation import DumpAnnotationMain
from annofabcli.common.annofab.editor_annotation import get_editor_annotation_dict_in_bulk
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login, get_json_from_args, get_list_from_args
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class TargetAnnotationLabelInput(BaseModel):
    """ラベル変更対象のアノテーション。"""

    task_id: str
    input_data_id: str
    annotation_id: str
    label_id: str | None = None
    label_name: str | None = None


class TargetAnnotationLabel(BaseModel):
    """変更先ラベルIDを解決済みのラベル変更対象アノテーション。"""

    task_id: str
    input_data_id: str
    annotation_id: str
    label_id: str


def filter_annotation_items_by_task_ids(items: list[TargetAnnotationLabelInput], target_task_ids: Collection[str]) -> tuple[list[TargetAnnotationLabelInput], set[str]]:
    """指定されたtask_idに一致するアノテーションだけを返す。"""
    target_task_id_set = set(target_task_ids)
    filtered_items = [item for item in items if item.task_id in target_task_id_set]
    existing_task_ids = {item.task_id for item in filtered_items}
    return filtered_items, target_task_id_set - existing_task_ids


@dataclass(frozen=True)
class ChangeAnnotationLabelCount:
    """アノテーションラベル変更件数。"""

    success: int
    """変更に成功したアノテーション数。"""

    skipped: int
    """変更をスキップしたアノテーション数。"""

    failed: int
    """変更に失敗したアノテーション数。"""


def get_annotation_list_per_task_id_input_data_id(anno_list: list[TargetAnnotationLabel]) -> dict[str, dict[str, list[TargetAnnotationLabel]]]:
    """タスクIDと入力データIDごとにアノテーションをグループ化する。"""
    grouped: dict[str, dict[str, list[TargetAnnotationLabel]]] = defaultdict(lambda: defaultdict(list))
    for annotation in anno_list:
        grouped[annotation.task_id][annotation.input_data_id].append(annotation)
    return grouped


def resolve_target_annotation_list(anno_list: list[TargetAnnotationLabelInput], annotation_specs: dict[str, Any]) -> list[TargetAnnotationLabel]:
    """入力された変更先ラベルをIDに解決し、アノテーションの重複を検証する。"""
    annotation_keys: set[tuple[str, str, str]] = set()
    result: list[TargetAnnotationLabel] = []
    for annotation in anno_list:
        if (annotation.label_id is None) == (annotation.label_name is None):
            raise ValueError("label_idまたはlabel_nameのいずれか一方を指定してください。")
        label_id = get_label_id_from_name_or_id(annotation_specs, label_id=annotation.label_id, label_name=annotation.label_name)
        annotation_key = (annotation.task_id, annotation.input_data_id, annotation.annotation_id)
        if annotation_key in annotation_keys:
            raise ValueError(f"task_id='{annotation.task_id}', input_data_id='{annotation.input_data_id}', annotation_id='{annotation.annotation_id}'が重複しています。")
        annotation_keys.add(annotation_key)
        result.append(TargetAnnotationLabel(task_id=annotation.task_id, input_data_id=annotation.input_data_id, annotation_id=annotation.annotation_id, label_id=label_id))
    return result


def parse_target_annotation_list(json_value: str | None, csv_path: str | None) -> list[TargetAnnotationLabelInput]:
    """コマンドライン引数からラベル変更対象のアノテーション一覧を取得する。"""
    if json_value is not None:
        annotation_items = get_json_from_args(json_value)
        if not isinstance(annotation_items, list):
            raise ValueError("オブジェクトの配列を指定してください。")
        return [TargetAnnotationLabelInput.model_validate(item) for item in annotation_items]

    assert csv_path is not None
    dataframe = pandas.read_csv(
        csv_path,
        dtype={"task_id": "string", "input_data_id": "string", "annotation_id": "string", "label_id": "string", "label_name": "string"},
    )
    return [TargetAnnotationLabelInput.model_validate(item) for item in dataframe.to_dict(orient="records")]


class ChangeAnnotationLabelPerAnnotationMain(CommandLineWithConfirm):
    """アノテーションごとにラベルを変更する。"""

    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        project_id: str,
        include_complete_task: bool,
        all_yes: bool,
        backup_dir: Path | None = None,
    ) -> None:
        self.service = service
        self.project_id = project_id
        self.include_complete_task = include_complete_task
        self.backup_dir = backup_dir
        self.annotation_specs, _ = service.api.get_annotation_specs(project_id, query_params={"v": "3"})
        self.annotation_specs_accessor = AnnotationSpecsAccessor(self.annotation_specs)
        self.dump_annotation_obj = DumpAnnotationMain(service, project_id)
        super().__init__(all_yes)

    def get_dest_label_info(self, label_id: str) -> DestLabelInfo:
        """変更先ラベル情報を返す。"""
        label = dict(self.annotation_specs_accessor.get_label(label_id=label_id))
        return DestLabelInfo(
            label_id=label_id,
            annotation_type=cast(str, label["annotation_type"]),
            additional_data_definition_ids=set(cast(list[str], label["additional_data_definitions"])),
        )

    def change_annotation_label_by_frame(self, task_id: str, input_data_id: str, anno_list: list[TargetAnnotationLabel], editor_annotation: dict[str, Any] | None = None) -> ChangeAnnotationLabelCount:
        """フレームごとにアノテーションラベルを変更する。"""
        if editor_annotation is None:
            editor_annotation, _ = self.service.api.get_editor_annotation(self.project_id, task_id=task_id, input_data_id=input_data_id, query_params={"v": "2"})

        if self.backup_dir is not None:
            (self.backup_dir / task_id).mkdir(exist_ok=True, parents=True)
            self.dump_annotation_obj.dump_editor_annotation(editor_annotation, json_path=self.backup_dir / task_id / f"{input_data_id}.json")

        details_by_annotation_id = {detail["annotation_id"]: detail for detail in editor_annotation["details"]}
        request_body = []
        skipped_count = 0
        for annotation in anno_list:
            detail = details_by_annotation_id.get(annotation.annotation_id)
            if detail is None:
                logger.warning(f"task_id='{task_id}', input_data_id='{input_data_id}' :: annotation_id='{annotation.annotation_id}'であるアノテーションが存在しないため、ラベル変更をスキップします。")
                skipped_count += 1
                continue

            dest_label_info = self.get_dest_label_info(annotation.label_id)
            src_label = dict(self.annotation_specs_accessor.get_label(label_id=detail["label_id"]))
            src_annotation_type = cast(str, src_label["annotation_type"])
            if not is_allowed_label_change(src_annotation_type, dest_label_info.annotation_type):
                logger.warning(
                    f"task_id='{task_id}', input_data_id='{input_data_id}', annotation_id='{annotation.annotation_id}' :: "
                    f"変更前ラベル種類から変更後ラベル種類へは変更できないため、ラベル変更をスキップします。変更前='{src_annotation_type}', 変更後='{dest_label_info.annotation_type}'"
                )
                skipped_count += 1
                continue

            if detail["label_id"] == annotation.label_id:
                logger.debug(f"task_id='{task_id}', input_data_id='{input_data_id}', annotation_id='{annotation.annotation_id}' :: 変更後ラベルが現在のラベルと同じため、ラベル変更をスキップします。")
                skipped_count += 1
                continue

            additional_data_list = [data for data in detail["additional_data_list"] if data["definition_id"] in dest_label_info.additional_data_definition_ids]
            request_body.append(
                {
                    "data": {
                        "project_id": editor_annotation["project_id"],
                        "task_id": editor_annotation["task_id"],
                        "input_data_id": editor_annotation["input_data_id"],
                        "updated_datetime": editor_annotation["updated_datetime"],
                        "annotation_id": annotation.annotation_id,
                        "label_id": annotation.label_id,
                        "additional_data_list": additional_data_list,
                    },
                    "_type": "PutV2",
                }
            )

        if request_body:
            self.service.api.batch_update_annotations(self.project_id, request_body=request_body)
        logger.debug(f"task_id='{task_id}', input_data_id='{input_data_id}' :: {len(request_body)}/{len(anno_list)}件のアノテーションラベルを変更しました。")
        return ChangeAnnotationLabelCount(success=len(request_body), skipped=skipped_count, failed=0)

    def change_annotation_label_for_task(self, task_id: str, annotations_by_input_data_id: dict[str, list[TargetAnnotationLabel]]) -> tuple[bool, ChangeAnnotationLabelCount]:
        """1個のタスクに含まれるアノテーションラベルを変更する。"""
        annotation_count = sum(len(annotations) for annotations in annotations_by_input_data_id.values())
        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"task_id='{task_id}' :: タスクが存在しないため、{annotation_count}件のアノテーションラベル変更をスキップします。")
            return False, ChangeAnnotationLabelCount(success=0, skipped=annotation_count, failed=0)
        if task["status"] == TaskStatus.WORKING.value:
            logger.info(f"task_id='{task_id}' :: タスクが作業中状態のため、{annotation_count}件のアノテーションラベル変更をスキップします。")
            return False, ChangeAnnotationLabelCount(success=0, skipped=annotation_count, failed=0)
        if task["status"] == TaskStatus.COMPLETE.value and not self.include_complete_task:
            logger.info(
                f"task_id='{task_id}' :: タスクが完了状態のため、{annotation_count}件のアノテーションラベル変更をスキップします。"
                "完了状態のタスクのアノテーションも変更するには、`--include_complete_task` オプションを指定してください。"
            )
            return False, ChangeAnnotationLabelCount(success=0, skipped=annotation_count, failed=0)
        if not self.confirm_processing(f"task_id='{task_id}'に含まれるアノテーション{annotation_count}件のラベルを変更しますか？"):
            return False, ChangeAnnotationLabelCount(success=0, skipped=annotation_count, failed=0)

        succeeded = 0
        skipped = 0
        failed = 0
        annotation_dict = get_editor_annotation_dict_in_bulk(self.service, self.project_id, task_id, annotations_by_input_data_id)
        for input_data_id, target_annotations in annotations_by_input_data_id.items():
            try:
                count = self.change_annotation_label_by_frame(task_id, input_data_id, target_annotations, annotation_dict[input_data_id])
                succeeded += count.success
                skipped += count.skipped
                failed += count.failed
            except Exception:
                logger.warning(f"task_id='{task_id}', input_data_id='{input_data_id}' :: アノテーションラベルの変更に失敗しました。", exc_info=True)
                failed += len(target_annotations)
        return True, ChangeAnnotationLabelCount(success=succeeded, skipped=skipped, failed=failed)

    def change_annotation_label(self, anno_list: list[TargetAnnotationLabel]) -> None:
        """アノテーションごとにラベルを変更する。"""
        annotations_by_task_id = get_annotation_list_per_task_id_input_data_id(anno_list)
        success = 0
        skipped = 0
        failed = 0
        changed_task_count = 0
        for task_index, (task_id, annotations_by_input_data_id) in enumerate(annotations_by_task_id.items(), start=1):
            logger.info(f"{task_index} / {len(annotations_by_task_id)}件目 :: task_id='{task_id}' のアノテーションラベルを変更します。")
            is_changeable, count = self.change_annotation_label_for_task(task_id, annotations_by_input_data_id)
            success += count.success
            skipped += count.skipped
            failed += count.failed
            if is_changeable:
                changed_task_count += 1
        logger.info(
            f"{success}/{len(anno_list)}件のアノテーションラベルを変更しました。 :: "
            f"アノテーションが変更されたタスク数は{changed_task_count}/{len(annotations_by_task_id)}件です。"
            f"スキップしたアノテーション数は{skipped}件、失敗したアノテーション数は{failed}件です。"
        )


class ChangeLabelPerAnnotation(CommandLine):
    """アノテーションごとにラベルを個別変更する。"""

    COMMON_MESSAGE = "annofabcli annotation change_label_per_annotation: error:"

    def main(self) -> None:
        args = self.args
        try:
            input_annotation_list = parse_target_annotation_list(args.json, args.csv)
        except Exception as e:
            print(f"{self.COMMON_MESSAGE} argument '--json' または '--csv' の値が不正です。 :: {e}", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        if args.task_id is not None:
            input_annotation_list, not_existing_task_ids = filter_annotation_items_by_task_ids(input_annotation_list, get_list_from_args(args.task_id))
            if not_existing_task_ids:
                logger.warning(f"'--task_id'で指定したタスクの内 {len(not_existing_task_ids)} 件は、変更対象データに含まれていません。 :: {sorted(not_existing_task_ids)}")

        project_id = args.project_id
        if args.backup is None:
            print("間違えてアノテーションを変更してしまったときに復元できるようにするため、'--backup'でバックアップ用のディレクトリを指定することを推奨します。", file=sys.stderr)  # noqa: T201
            if not self.confirm_processing("復元用のバックアップディレクトリが指定されていません。処理を続行しますか？"):
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            backup_dir = None
        else:
            backup_dir = args.backup

        if args.include_complete_task and not self.facade.contains_any_project_member_role(project_id, [ProjectMemberRole.OWNER]):
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --include_complete_task : '--include_complete_task' 引数を利用するにはプロジェクトのオーナーロールを持つユーザーで実行する必要があります。",
                file=sys.stderr,
            )
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])

        main_obj = ChangeAnnotationLabelPerAnnotationMain(self.service, project_id=project_id, include_complete_task=args.include_complete_task, all_yes=args.yes, backup_dir=backup_dir)
        try:
            target_annotation_list = resolve_target_annotation_list(input_annotation_list, main_obj.annotation_specs)
        except ValueError as e:
            print(f"{self.COMMON_MESSAGE} argument '--json' または '--csv' の値が不正です。 :: {e}", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
        main_obj.change_annotation_label(target_annotation_list)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeLabelPerAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    sample_json_obj = [{"task_id": "t1", "input_data_id": "i1", "annotation_id": "a1", "label_name": "car"}]
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--json",
        type=str,
        help="各アノテーションごとに変更内容を記載したJSONリストを指定します。``file://`` を先頭に付けるとJSON形式のファイルを指定できます。\n"
        f"(例) '{json.dumps(sample_json_obj, ensure_ascii=False)}'",
    )
    input_group.add_argument(
        "--csv",
        type=str,
        help=(
            "各アノテーションごとに変更内容を記載したCSVファイルを指定します。\n"
            "* ``task_id``, ``input_data_id``, ``annotation_id`` と、 ``label_id`` または ``label_name`` のいずれかのカラムが必要です。"
        ),
    )
    argument_parser.add_task_id(required=False, help_message="変更対象のアノテーションをtask_idで絞り込みます。 ``--json`` や ``--csv`` で指定したデータのうち、一致したtask_idのみを処理します。")
    parser.add_argument(
        "--include_complete_task", action="store_true", help="指定した場合は、完了状態のタスクのアノテーションラベルも変更します。ただし、オーナーロールを持つユーザーでしか実行できません。"
    )
    parser.add_argument("--backup", type=Path, required=False, help="アノテーションのバックアップを保存するディレクトリのパス。アノテーションの復元は ``annotation restore`` コマンドで実現できます。")
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "change_label_per_annotation"
    subcommand_help = "各アノテーションのラベルを変更します。"
    epilog = "オーナロールまたはチェッカーロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
