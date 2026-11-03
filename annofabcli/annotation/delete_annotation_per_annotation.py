from __future__ import annotations

import argparse
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import annofabapi
import pandas
import requests
from annofabapi.models import ProjectMemberRole, TaskStatus
from pydantic import BaseModel, Field, ValidationError

import annofabcli.common.cli
from annofabcli.annotation.dump_annotation import DumpAnnotationMain
from annofabcli.common.cli import PARALLELISM_CHOICES, ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login, get_json_from_args
from annofabcli.common.exceptions import AnnofabCliException
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class DeletedAnnotationInfo(BaseModel):
    """削除対象のアノテーションを特定するID。"""

    task_id: str = Field(min_length=1)
    input_data_id: str = Field(min_length=1)
    annotation_id: str = Field(min_length=1)


@dataclass(frozen=True)
class DeleteResult:
    """アノテーションの削除結果。"""

    deleted: int = 0
    failed: int = 0
    task_failed: bool = False


class DeleteAnnotationPerAnnotationMain(CommandLineWithConfirm):
    """ID一覧で指定されたアノテーションを削除する。"""

    def __init__(self, service: annofabapi.Resource, project_id: str, *, include_complete_task: bool, all_yes: bool) -> None:
        super().__init__(all_yes)
        self.service = service
        self.project_id = project_id
        self.include_complete_task = include_complete_task
        self.dump_annotation_obj = DumpAnnotationMain(service, project_id)

    def delete_annotation_by_annotation_ids(
        self,
        editor_annotation: dict[str, Any],
        annotation_ids: set[str],
    ) -> DeleteResult:
        """
        入力データ内の指定されたアノテーションを削除する。

        Args:
            editor_annotation: 削除前のアノテーション情報。
            annotation_ids: 削除対象のアノテーションID。

        Returns:
            削除件数と削除できなかった件数。
        """
        if not annotation_ids:
            raise ValueError("`annotation_ids` に少なくとも1件のIDを指定してください。")

        task_id = editor_annotation["task_id"]
        input_data_id = editor_annotation["input_data_id"]
        if len(editor_annotation["details"]) == 0:
            logger.warning(f"task_id='{task_id}', input_data_id='{input_data_id}' にはアノテーションが存在しません。以下のアノテーションの削除をスキップします。 :: annotation_ids={annotation_ids}")
            return DeleteResult(deleted=0, failed=len(annotation_ids))

        # annotation_idでフィルタ
        filtered_details = [e for e in editor_annotation["details"] if e["annotation_id"] in annotation_ids]
        existent_annotation_ids = {detail["annotation_id"] for detail in filtered_details}
        nonexistent_annotation_ids = annotation_ids - existent_annotation_ids

        if len(nonexistent_annotation_ids) > 0:
            logger.warning(f"次のアノテーションは存在しないので、削除できません。 :: task_id='{task_id}', input_data_id='{input_data_id}', annotation_id='{nonexistent_annotation_ids}'")

        if len(filtered_details) == 0:
            logger.info(f"task_id='{task_id}', input_data_id='{input_data_id}' には削除対象のアノテーションが存在しないので、スキップします。")
            return DeleteResult(deleted=0, failed=len(annotation_ids))

        try:

            def _to_request_body_elm(detail: dict[str, Any]) -> dict[str, Any]:
                return {
                    "project_id": self.project_id,
                    "task_id": task_id,
                    "input_data_id": input_data_id,
                    "updated_datetime": editor_annotation["updated_datetime"],
                    "annotation_id": detail["annotation_id"],
                    "_type": "Delete",
                }

            request_body = [_to_request_body_elm(detail) for detail in filtered_details]
            # APIを呼び出してアノテーションを削除
            self.service.api.batch_update_annotations(self.project_id, request_body=request_body, query_params={"v": "2"})

            logger.info(f"task_id='{task_id}', input_data_id='{input_data_id}' に含まれるアノテーション {len(filtered_details)} 件を削除しました。")

            return DeleteResult(deleted=len(filtered_details), failed=len(nonexistent_annotation_ids))

        except requests.HTTPError:
            logger.warning(f"task_id='{task_id}', input_data_id='{input_data_id}' :: アノテーションの削除に失敗しました。", exc_info=True)
            # `batchUpdateAnnotations` APIでエラーになった場合、途中までは削除されるので、`len(annotation_ids)` 件削除に失敗したとは限らない。
            # そのため、再度アノテーション情報を取得して、削除できたアノテーション数と削除できなかったアノテーション数を取得する。
            new_editor_annotation, _ = self.service.api.get_editor_annotation(self.project_id, task_id=task_id, input_data_id=input_data_id, query_params={"v": "2"})
            new_annotation_ids = {e["annotation_id"] for e in new_editor_annotation["details"]}
            deleted_annotation_count = len(existent_annotation_ids - new_annotation_ids)
            failed_to_delete_annotation_count = len(existent_annotation_ids) - deleted_annotation_count
            return DeleteResult(deleted=deleted_annotation_count, failed=failed_to_delete_annotation_count + len(nonexistent_annotation_ids), task_failed=True)

    def delete_annotations_for_task(self, task_id: str, annotation_ids_by_input: dict[str, set[str]], backup_dir: Path | None) -> DeleteResult:
        """タスク内の入力データを順番に処理する。

        Args:
            task_id: 対象タスクのID。
            annotation_ids_by_input: 入力データIDごとの削除対象ID。
            backup_dir: 削除前のバックアップ先。

        Returns:
            タスク全体の削除結果。
        """
        annotation_count = sum(len(ids) for ids in annotation_ids_by_input.values())
        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"task_id='{task_id}' :: タスクが存在しないため、アノテーション {annotation_count} 件の削除をスキップします。")
            return DeleteResult(failed=annotation_count)
        if task["status"] == TaskStatus.WORKING.value:
            logger.info(f"task_id='{task_id}' :: タスクが作業中状態のため、削除をスキップします。")
            return DeleteResult(failed=annotation_count)
        if not self.include_complete_task and task["status"] == TaskStatus.COMPLETE.value:
            logger.info(f"task_id='{task_id}' :: タスクが完了状態のため、削除をスキップします。完了状態のタスクも削除するには、`--include_complete_task`を指定してください。")
            return DeleteResult(failed=annotation_count)
        if not self.confirm_processing(f"task_id='{task_id}'のタスクに含まれるアノテーション {annotation_count} 件を削除しますか？"):
            return DeleteResult(failed=annotation_count)

        deleted = 0
        failed = 0
        task_failed = False
        for input_data_id, annotation_ids in annotation_ids_by_input.items():
            try:
                editor_annotation = self.service.wrapper.get_editor_annotation_or_none(self.project_id, task_id=task_id, input_data_id=input_data_id, query_params={"v": "2"})
                if editor_annotation is None:
                    logger.warning(f"task_id='{task_id}', input_data_id='{input_data_id}' :: アノテーション情報が存在しないため、削除をスキップします。")
                    failed += len(annotation_ids)
                    continue
                if backup_dir is not None:
                    backup_path = backup_dir / task_id / f"{input_data_id}.json"
                    backup_path.parent.mkdir(exist_ok=True, parents=True)
                    self.dump_annotation_obj.dump_editor_annotation(editor_annotation, json_path=backup_path)
                result = self.delete_annotation_by_annotation_ids(editor_annotation, annotation_ids)
                deleted += result.deleted
                failed += result.failed
                task_failed |= result.task_failed
            except Exception:
                logger.warning(f"task_id='{task_id}', input_data_id='{input_data_id}' :: アノテーションの削除に失敗しました。", exc_info=True)
                failed += len(annotation_ids)
                task_failed = True
        return DeleteResult(deleted=deleted, failed=failed, task_failed=task_failed)

    def delete_annotation_by_id_list(self, annotation_list: list[DeletedAnnotationInfo], backup_dir: Path | None = None, *, parallelism: int | None = None) -> None:
        """指定されたアノテーションをタスク単位で削除する。

        Args:
            annotation_list: 削除対象のアノテーション一覧。
            backup_dir: 削除前のバックアップ先。
            parallelism: 同時に処理するタスク数。

        Returns:
            None。
        """
        grouped: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        for item in annotation_list:
            grouped[item.task_id][item.input_data_id].add(item.annotation_id)
        total = sum(len(ids) for inputs in grouped.values() for ids in inputs.values())
        logger.info(f"{len(grouped)} 件のタスクに含まれるアノテーション {total} 件を削除します。")

        def process_task(item: tuple[int, tuple[str, dict[str, set[str]]]]) -> DeleteResult:
            task_index, (task_id, inputs) = item
            logger.info(f"{task_index} / {len(grouped)} 件目 :: task_id='{task_id}' のアノテーションを削除します。")
            try:
                return self.delete_annotations_for_task(task_id, inputs, backup_dir)
            except Exception:
                logger.warning(f"task_id='{task_id}' :: タスクの処理に失敗しました。", exc_info=True)
                return DeleteResult(failed=sum(len(ids) for ids in inputs.values()), task_failed=True)

        task_items = enumerate(grouped.items(), start=1)
        if parallelism is None:
            results = [process_task(item) for item in task_items]
        else:
            with ThreadPoolExecutor(max_workers=parallelism) as executor:
                results = list(executor.map(process_task, task_items))
        deleted = sum(result.deleted for result in results)
        failed = sum(result.failed for result in results)
        logger.info(f"{deleted}/{total} 件のアノテーションを削除しました。{failed} 件のアノテーションは削除できませんでした。")
        failed_tasks = sum(result.task_failed for result in results)
        if failed_tasks:
            raise AnnofabCliException(f"{failed_tasks} 件のタスクの処理に失敗しました。")


class DeleteAnnotationPerAnnotation(CommandLine):
    """ID一覧を読み込み、指定されたアノテーションを削除する。"""

    def main(self) -> None:
        args = self.args
        if args.parallelism is not None and not args.yes:
            raise AnnofabCliException("`--parallelism`を指定するときは、`--yes`も指定してください。")
        if args.json is not None:
            values = get_json_from_args(args.json)
            if not isinstance(values, list):
                raise AnnofabCliException("`--json`にはオブジェクトの配列を指定してください。")
        else:
            df = pandas.read_csv(args.csv, dtype={"task_id": "string", "input_data_id": "string", "annotation_id": "string"})
            columns = ["task_id", "input_data_id", "annotation_id"]
            if not set(columns).issubset(df.columns):
                raise AnnofabCliException("CSVにはtask_id、input_data_id、annotation_id列が必要です。")
            values = df[columns].to_dict(orient="records")
        try:
            annotation_list = [DeletedAnnotationInfo.model_validate(value) for value in values]
        except ValidationError as e:
            raise AnnofabCliException(f"削除対象の指定が不正です。{e}") from e

        if args.backup is None:
            logger.warning("復元用のバックアップを保存するには、`--backup`を指定してください。")
            if not args.yes and not annofabcli.common.cli.prompt_yesno("復元用のバックアップディレクトリが指定されていません。処理を続行しますか？"):
                return
        roles = [ProjectMemberRole.OWNER] if args.include_complete_task else [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER]
        self.require_project_access(args.project_id, roles)
        command = DeleteAnnotationPerAnnotationMain(self.service, args.project_id, all_yes=args.yes, include_complete_task=args.include_complete_task)
        command.delete_annotation_by_id_list(annotation_list, backup_dir=args.backup, parallelism=args.parallelism)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteAnnotationPerAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--json", type=str, help="削除対象をtask_id、input_data_id、annotation_idを持つJSONオブジェクトの配列で指定します。先頭に ``file://`` を付けるとJSONファイルを指定できます。")
    group.add_argument("--csv", type=Path, help="削除対象をCSVファイルで指定します。task_id、input_data_id、annotation_id列が必要です。")
    parser.add_argument("--include_complete_task", action="store_true", help="完了状態のタスクに含まれるアノテーションも削除します。オーナーロールが必要です。")
    parser.add_argument("--backup", type=Path, help="削除前のアノテーションを保存するディレクトリ。復元には ``annotation restore`` を使用してください。")
    parser.add_argument("--parallelism", type=int, choices=PARALLELISM_CHOICES, help="並列に処理するタスク数。指定する場合は ``--yes`` も指定してください。")
    parser.set_defaults(subcommand_func=main)


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "delete_per_annotation"
    description = "ID一覧で指定されたアノテーションを削除します。作業中状態のタスクは削除できません。復元用に ``--backup`` の指定を推奨します。"
    epilog = "オーナーまたはチェッカーロールを持つユーザーで実行してください。``--include_complete_task`` を指定する場合は、オーナーロールが必要です。"
    parser = annofabcli.common.cli.create_parser(subparsers, subcommand_name, "ID一覧で指定されたアノテーションを削除します。", description, epilog=epilog)
    parse_args(parser)
    return parser
