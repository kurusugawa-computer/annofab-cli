from __future__ import annotations

import argparse
import copy
import logging
import multiprocessing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import annofabapi
from annofabapi.models import ProjectMemberRole, TaskStatus
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor

import annofabcli.common.cli
from annofabcli.annotation.dump_annotation import DumpAnnotationMain
from annofabcli.common.annofab.editor_annotation import get_editor_annotation_dict_in_bulk
from annofabcli.common.cli import PARALLELISM_CHOICES, ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login
from annofabcli.common.exceptions import AnnofabCliException
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)

SUPPORTED_CONVERSIONS = {
    ("Choice", "select"): "Select",
    ("Select", "choice"): "Choice",
    ("Text", "comment"): "Comment",
    ("Comment", "text"): "Text",
    ("Text", "integer"): "Integer",
    ("Comment", "integer"): "Integer",
    ("Integer", "text"): "Text",
}
"""保存型と現在のアノテーション仕様の型をキーとする、対応する変換。"""


@dataclass
class NormalizeResult:
    """属性値の型の変更と、入力データ・タスクごとの処理失敗の集計結果。"""

    changed: int = 0
    """正規化した属性値数。dry-runでは正規化予定数。"""
    skipped: int = 0
    """不整合を修復できず保持した属性値数。"""
    failed_input_data: int = 0
    """処理に失敗した入力データ数。"""
    failed_tasks: int = 0
    """処理に失敗したタスク数。"""


def normalize_attribute_value(value: dict[str, Any], attribute: dict[str, Any]) -> dict[str, Any]:
    """保存値を現在のアノテーション仕様の型に変換する。一致している値はそのまま返す。

    Args:
        value: Editor形式の保存値。
        attribute: 現在のアノテーション仕様の属性定義。

    Returns:
        変換後の保存値。

    Raises:
        ValueError: 未対応の変換、値の不正、選択肢の不存在。
    """
    source_type = value["_type"]
    target_type = attribute["type"]
    if source_type.lower() == target_type:
        return value
    converted_type = SUPPORTED_CONVERSIONS.get((source_type, target_type))
    if converted_type is None:
        raise ValueError(f"未対応の変換です: {source_type} → {target_type}")

    result = copy.deepcopy(value)
    if source_type in {"Choice", "Select"}:
        if value.get("choice_id") not in {choice["choice_id"] for choice in attribute["choices"]}:
            raise ValueError("保存されている選択肢IDが現在のアノテーション仕様に存在しません。")
    elif source_type == "Integer":
        if type(value.get("value")) is not int:
            raise ValueError("Integerの保存値が整数ではありません。")
        result["value"] = str(value["value"])
    else:
        if not isinstance(value.get("value"), str):
            raise ValueError("文字列属性の保存値が文字列ではありません。")
        if target_type == "integer":
            result["value"] = int(value["value"])
        elif target_type == "text" and ("\n" in value["value"] or "\r" in value["value"]):
            raise ValueError("改行を含むため、1行の自由記述には変換しません。")
    result["_type"] = converted_type
    return result


def create_normalized_request(editor_annotation: dict[str, Any], annotation_specs: dict[str, Any], *, attribute_ids: set[str] | None = None) -> tuple[list[dict[str, Any]], NormalizeResult]:
    """形状と対象外の属性値を保持して、入力データ単位の更新リクエストを作成する。

    Args:
        editor_annotation: Editor形式のアノテーション。
        annotation_specs: 現行のアノテーション仕様。
        attribute_ids: 対象属性ID。Noneの場合は全属性。

    Returns:
        batch_update_annotations用リクエストと集計結果。
    """
    definitions = {attribute["additional_data_definition_id"]: attribute for attribute in annotation_specs["additionals"]}
    allowed = {label["label_id"]: set(label["additional_data_definitions"]) for label in annotation_specs["labels"]}
    result = NormalizeResult()
    request = []
    for detail in editor_annotation["details"]:
        changes = []
        for additional in detail["additional_data_list"]:
            attribute_id = additional["definition_id"]
            value = additional["value"]
            if value is None or (attribute_ids is not None and attribute_id not in attribute_ids):
                continue
            try:
                if attribute_id not in definitions or attribute_id not in allowed.get(detail["label_id"], set()):
                    result.skipped += 1
                    logger.warning(f"annotation_id='{detail['annotation_id']}', attribute_id='{attribute_id}' :: 属性が現在のアノテーション仕様のラベルに存在しないため、スキップします。")
                    continue
                converted = normalize_attribute_value(value, definitions[attribute_id])
            except ValueError as e:
                result.skipped += 1
                logger.warning(
                    f"task_id='{editor_annotation['task_id']}', input_data_id='{editor_annotation['input_data_id']}', "
                    f"annotation_id='{detail['annotation_id']}', attribute_id='{attribute_id}' :: {e} スキップします。"
                )
                continue
            if converted != value:
                changes.append({"definition_id": attribute_id, "value": converted})
                result.changed += 1
                logger.debug(f"annotation_id='{detail['annotation_id']}', attribute_id='{attribute_id}' :: {value['_type']} → {converted['_type']}")
        if changes:
            data = {key: editor_annotation[key] for key in ("project_id", "task_id", "input_data_id", "updated_datetime")}
            data.update(annotation_id=detail["annotation_id"], label_id=detail["label_id"], additional_data_list=changes)
            request.append({"_type": "PutV2", "data": data})
    return request, result


class NormalizeAttributeTypeMain(CommandLineWithConfirm):
    """属性の保存型を現在のアノテーション仕様にそろえる処理。"""

    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        project_id: str,
        annotation_specs: dict[str, Any],
        attribute_ids: set[str] | None = None,
        include_complete_task: bool = False,
        include_on_hold_task: bool = False,
        dry_run: bool = False,
        backup_dir: Path | None = None,
        all_yes: bool = False,
    ) -> None:
        self.service = service
        self.project_id = project_id
        self.annotation_specs = annotation_specs
        self.attribute_ids = attribute_ids
        self.include_complete_task = include_complete_task
        self.include_on_hold_task = include_on_hold_task
        self.dry_run = dry_run
        self.backup_dir = backup_dir
        super().__init__(all_yes)

    def normalize_for_task(self, item: tuple[int, str]) -> NormalizeResult:
        """タスクの属性型を正規化する。失敗した入力データ以外は処理を継続する。

        Args:
            item: 処理番号とタスクID。

        Returns:
            タスクの集計結果。
        """
        index, task_id = item
        total = NormalizeResult()
        logger.info(f"{index + 1} 件目 :: task_id='{task_id}' の属性型を確認します。")
        try:
            task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
            if task is None:
                logger.warning(f"task_id='{task_id}' :: タスクが存在しないため、スキップします。")
                return total
            status = task["status"]
            if status == TaskStatus.WORKING.value or (status == TaskStatus.COMPLETE.value and not self.include_complete_task) or (status == TaskStatus.ON_HOLD.value and not self.include_on_hold_task):
                logger.info(f"task_id='{task_id}' :: タスクの状態が'{status}'のため、スキップします。")
                return total
            if not self.dry_run and not self.confirm_processing(f"task_id='{task_id}' の属性の保存型を現在のアノテーション仕様にそろえますか？"):
                return total
            annotations = get_editor_annotation_dict_in_bulk(self.service, self.project_id, task_id, task["input_data_id_list"])
            for input_data_id in task["input_data_id_list"]:
                try:
                    annotation = annotations[input_data_id]
                    request, result = create_normalized_request(annotation, self.annotation_specs, attribute_ids=self.attribute_ids)
                    total.skipped += result.skipped
                    if result.changed > 0 and not self.dry_run:
                        if self.backup_dir is not None:
                            directory = self.backup_dir / task_id
                            directory.mkdir(parents=True, exist_ok=True)
                            DumpAnnotationMain(self.service, self.project_id).dump_editor_annotation(annotation, directory / f"{input_data_id}.json")
                        self.service.api.batch_update_annotations(self.project_id, request_body=request)
                    total.changed += result.changed
                except Exception:
                    total.failed_input_data += 1
                    logger.warning(f"task_id='{task_id}', input_data_id='{input_data_id}' :: 属性型の正規化に失敗しました。", exc_info=True)
        except Exception:
            total.failed_tasks += 1
            logger.warning(f"task_id='{task_id}' :: 属性型の正規化に失敗しました。", exc_info=True)
        logger.info(
            f"task_id='{task_id}' :: 属性値の型を{total.changed}件変更{'する予定です' if self.dry_run else 'しました'}。"
            f"変換できず保持した属性値: {total.skipped}件、"
            f"処理に失敗した入力データ: {total.failed_input_data}件、処理に失敗したタスク: {total.failed_tasks}件。"
        )
        return total


class NormalizeAttributeType(CommandLine):
    """正規化コマンドの引数を解決して実行する。"""

    def main(self) -> None:
        """正規化コマンドを実行する。

        Args:
            なし。

        Returns:
            None。
        """
        args = self.args
        self.require_project_access(args.project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])
        if args.include_complete_task and not self.facade.contains_any_project_member_role(args.project_id, [ProjectMemberRole.OWNER]):
            raise AnnofabCliException("--include_complete_task を利用するにはオーナーロールが必要です。")
        if args.parallelism is not None and not args.yes and not args.dry_run:
            raise AnnofabCliException("--parallelism を指定するときは --yes も指定してください。")
        specs, _ = self.service.api.get_annotation_specs(args.project_id, query_params={"v": "3"})
        attribute_ids = None
        if args.attribute_id is not None or args.attribute_name_en is not None:
            accessor = AnnotationSpecsAccessor(specs)
            if args.attribute_id is not None:
                attribute_ids = {accessor.get_attribute(attribute_id=value)["additional_data_definition_id"] for value in annofabcli.common.cli.get_list_from_args(args.attribute_id)}
            else:
                attribute_ids = {accessor.get_attribute(attribute_name=value)["additional_data_definition_id"] for value in annofabcli.common.cli.get_list_from_args(args.attribute_name_en)}
        if args.task_id is not None:
            task_ids = annofabcli.common.cli.get_list_from_args(args.task_id)
        else:
            tasks = self.service.wrapper.get_all_tasks(args.project_id)
            if len(tasks) >= 10_000:
                raise AnnofabCliException("タスク一覧が取得上限に達したため中断します。--task_id を指定してください。")
            task_ids = [task["task_id"] for task in tasks]
        main_obj = NormalizeAttributeTypeMain(
            self.service,
            project_id=args.project_id,
            annotation_specs=specs,
            attribute_ids=attribute_ids,
            include_complete_task=args.include_complete_task,
            include_on_hold_task=args.include_on_hold_task,
            dry_run=args.dry_run,
            backup_dir=Path(args.backup) if args.backup is not None else None,
            all_yes=args.yes,
        )
        logger.info(f"{len(task_ids)} 件のタスクの属性型を正規化します。dry_run={args.dry_run}")
        if args.parallelism is not None:
            with multiprocessing.Pool(args.parallelism) as pool:
                results = pool.map(main_obj.normalize_for_task, enumerate(dict.fromkeys(task_ids)))
        else:
            results = [main_obj.normalize_for_task(item) for item in enumerate(dict.fromkeys(task_ids))]
        failed_input_data = sum(result.failed_input_data for result in results)
        failed_tasks = sum(result.failed_tasks for result in results)
        logger.info(
            f"全体の処理結果 :: 属性値の型の変更{'予定' if args.dry_run else ''}: {sum(result.changed for result in results)}件、"
            f"変換できず保持した属性値: {sum(result.skipped for result in results)}件、"
            f"処理に失敗した入力データ: {failed_input_data}件、処理に失敗したタスク: {failed_tasks}件。"
        )
        if failed_input_data or failed_tasks:
            raise AnnofabCliException(f"入力データ{failed_input_data}件、タスク{failed_tasks}件の処理に失敗しました。")


def main(args: argparse.Namespace) -> None:
    """認証してコマンドを実行する。

    Args:
        args: コマンドライン引数。

    Returns:
        None。
    """
    service = build_annofabapi_resource_and_login(args)
    NormalizeAttributeType(service, AnnofabApiFacade(service), args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    """コマンドの引数を登録する。

    Args:
        parser: 登録先のパーサー。

    Returns:
        None。
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    argument_parser.add_task_id_or_all_tasks()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--attribute_id", nargs="+", help="対象の属性ID。file://形式で一覧ファイルも指定できます。省略時は全属性を対象にします。")
    group.add_argument("--attribute_name_en", nargs="+", help="対象の属性名（英語）。file://形式で一覧ファイルも指定できます。")
    parser.add_argument("--dry_run", action="store_true", help="更新せず、正規化予定数とスキップ理由を確認します。バックアップも作成しません。")
    parser.add_argument("--include_complete_task", action="store_true", help="完了状態のタスクも処理します。オーナーロールが必要です。")
    parser.add_argument("--include_on_hold_task", action="store_true", help="保留中状態のタスクも処理します。")
    parser.add_argument("--backup", help="復元用バックアップの保存先ディレクトリ。復元には ``annotation restore`` を使用してください。")
    parser.add_argument("--parallelism", type=int, choices=PARALLELISM_CHOICES, help="並列度。更新する場合は ``--yes`` も指定してください。")
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """サブコマンドを登録する。

    Args:
        subparsers: 登録先。Noneの場合は単独のパーサーを作成する。

    Returns:
        登録したパーサー。
    """
    parser = annofabcli.common.cli.add_parser(
        subparsers,
        command_name="normalize_attribute_type",
        command_help="アノテーションの属性値の型を、現在のアノテーション仕様に合わせます。",
        description=(
            "アノテーションの属性値の型を、現在のアノテーション仕様に合わせます。"
            "たとえば、アノテーション仕様で属性の種類を自由記述1行（ ``text`` ）から自由記述複数行（ ``comment`` ）に変更した直後は、"
            "属性値の型がアノテーション仕様と一致していないため、"
            "アノテーションエディタ画面やダウンロードしたアノテーションZIPでは、属性値が空欄になっている可能性があります。"
            "そのようなアノテーションの属性値を修正します。"
        ),
        epilog="オーナーロールまたはチェッカーロールを持つユーザーで実行してください。",
    )
    parse_args(parser)
    return parser
