from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import annofabapi
import pandas
import requests
from annofabapi.dataclass.task import Task
from annofabapi.models import ProjectMemberRole, TaskStatus

import annofabcli
from annofabcli.annotation.annotation_query import AnnotationQueryForAPI, AnnotationQueryForCLI
from annofabcli.annotation.dump_annotation import DumpAnnotationMain
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


@dataclass(frozen=True)
class DeletedAnnotationInfo:
    """
    削除対象のアノテーション情報
    """

    task_id: str
    input_data_id: str
    annotation_id: str


class DeleteAnnotationMain(CommandLineWithConfirm):
    """アノテーション削除処理用のクラス

    Args:
        is_force: 完了状態のタスクを削除するかどうか
    """

    def __init__(
        self,
        service: annofabapi.Resource,
        project_id: str,
        *,
        is_force: bool,
        all_yes: bool,
    ) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.is_force = is_force
        CommandLineWithConfirm.__init__(self, all_yes)
        self.project_id = project_id
        self.dump_annotation_obj = DumpAnnotationMain(service, project_id)

    def delete_annotation_list(self, annotation_list: list[dict[str, Any]]) -> None:
        """
        アノテーション一覧を削除する。

        Args:
            annotation_list: アノテーション一覧

        """

        def _to_request_body_elm(annotation: dict[str, Any]) -> dict[str, Any]:
            detail = annotation["detail"]
            return {
                "project_id": annotation["project_id"],
                "task_id": annotation["task_id"],
                "input_data_id": annotation["input_data_id"],
                "updated_datetime": annotation["updated_datetime"],
                "annotation_id": detail["annotation_id"],
                "_type": "Delete",
            }

        request_body = [_to_request_body_elm(annotation) for annotation in annotation_list]
        self.service.api.batch_update_annotations(self.project_id, request_body=request_body)

    def get_annotation_list_for_task(self, task_id: str, annotation_query: Optional[AnnotationQueryForAPI]) -> list[dict[str, Any]]:
        """
        タスク内のアノテーション一覧を取得する。

        Args:
            project_id:
            task_id:
            annotation_query: アノテーションの検索条件

        Returns:
            アノテーション一覧
        """
        dict_query = {"task_id": task_id, "exact_match_task_id": True}
        if annotation_query is not None:
            dict_query.update(annotation_query.to_dict())

        annotation_list = self.service.wrapper.get_all_annotation_list(self.project_id, query_params={"query": dict_query})
        return annotation_list

    def delete_annotation_for_task(
        self,
        task_id: str,
        annotation_query: Optional[AnnotationQueryForAPI] = None,
        backup_dir: Optional[Path] = None,
    ) -> None:
        """
        タスクに対してアノテーションを削除する

        Args:
            task_id:
            annotation_query: 削除対象のアノテーションの検索条件
            backup_dir: 削除対象のアノテーションをバックアップとして保存するディレクトリ。指定しない場合は、バックアップを取得しない。

        """
        dict_task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if dict_task is None:
            logger.warning(f"task_id='{task_id}'であるタスクは存在しません。")
            return

        task: Task = Task.from_dict(dict_task)
        logger.info(f"task_id='{task.task_id}', phase='{task.phase.value}', status='{task.status.value}', updated_datetime='{task.updated_datetime}'")

        if task.status == TaskStatus.WORKING:
            logger.info(f"task_id='{task_id}' :: タスクが作業中状態のため、スキップします。")
            return

        if not self.is_force:  # noqa: SIM102
            if task.status == TaskStatus.COMPLETE:
                logger.info(f"task_id='{task_id}' :: タスクが完了状態のため、スキップします。完了状態のタスクのアノテーションを削除するには、`--force`オプションを指定してください。")
                return

        annotation_list = self.get_annotation_list_for_task(task_id, annotation_query=annotation_query)
        logger.info(f"task_id='{task_id}'の削除対象アノテーション数：{len(annotation_list)}")
        if len(annotation_list) == 0:
            logger.info(f"task_id='{task_id}'には削除対象のアノテーションが存在しないので、スキップします。")
            return

        if not self.confirm_processing(f"task_id='{task_id}' のアノテーションを削除しますか？"):
            return

        if backup_dir is not None:
            self.dump_annotation_obj.dump_annotation_for_task(task_id, output_dir=backup_dir)

        try:
            self.delete_annotation_list(annotation_list=annotation_list)
            logger.info(f"task_id='{task_id}' :: アノテーションを削除しました。")
        except requests.HTTPError:
            logger.warning(f"task_id='{task_id}' :: アノテーションの削除に失敗しました。", exc_info=True)

    def delete_annotation_for_task_list(
        self,
        task_id_list: list[str],
        annotation_query: Optional[AnnotationQueryForAPI] = None,
        backup_dir: Optional[Path] = None,
    ) -> None:
        project_title = self.facade.get_project_title(self.project_id)
        logger.info(f"プロジェクト'{project_title}'に対して、タスク{len(task_id_list)} 件のアノテーションを削除します。")

        if backup_dir is not None:
            backup_dir.mkdir(exist_ok=True, parents=True)

        for task_index, task_id in enumerate(task_id_list):
            logger.info(f"{task_index + 1} / {len(task_id_list)} 件目: タスク '{task_id}' を削除します。")
            self.delete_annotation_for_task(
                task_id,
                annotation_query=annotation_query,
                backup_dir=backup_dir,
            )

    def delete_annotation_by_annotation_ids(
        self,
        editor_annotation: dict[str, Any],
        annotation_ids: set[str],
    ) -> tuple[int, int]:
        """
        指定してフレームに対して、annotation_idのリストで指定されたアノテーションを削除する。

        Returns:
            削除したアノテーションの件数
            削除しなかったアノテーションの件数
        """
        if not annotation_ids:
            raise ValueError("`annotation_ids` に少なくとも1件のIDを指定してください。")

        task_id = editor_annotation["task_id"]
        input_data_id = editor_annotation["input_data_id"]
        if len(editor_annotation["details"]) == 0:
            logger.warning(f"task_id='{task_id}', input_data_id='{input_data_id}' にはアノテーションが存在しません。以下のアノテーションの削除をスキップします。 :: annotation_ids={annotation_ids}")
            return 0, len(annotation_ids)

        # annotation_idでフィルタ
        filtered_details = [e for e in editor_annotation["details"] if e["annotation_id"] in annotation_ids]
        existent_annotation_ids = {detail["annotation_id"] for detail in filtered_details}
        nonexistent_annotation_ids = annotation_ids - existent_annotation_ids

        if len(nonexistent_annotation_ids) > 0:
            logger.warning(f"次のアノテーションは存在しないので、削除できません。 :: task_id='{task_id}', input_data_id='{input_data_id}', annotation_id='{nonexistent_annotation_ids}'")

        if len(filtered_details) == 0:
            logger.info(f"task_id='{task_id}', input_data_id='{input_data_id}' には削除対象のアノテーションが存在しないので、スキップします。")
            return 0, len(annotation_ids)

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

            return len(filtered_details), len(nonexistent_annotation_ids)

        except requests.HTTPError:
            logger.warning(f"task_id='{task_id}', input_data_id='{input_data_id}' :: アノテーションの削除に失敗しました。", exc_info=True)
            # `batchUpdateAnnotations` APIでエラーになった場合、途中までは削除されるので、`len(annotation_ids)` 件削除に失敗したとは限らない。
            # そのため、再度アノテーション情報を取得して、削除できたアノテーション数と削除できなかったアノテーション数を取得する。
            new_editor_annotation, _ = self.service.api.get_editor_annotation(self.project_id, task_id=task_id, input_data_id=input_data_id, query_params={"v": "2"})
            new_annotation_ids = {e["annotation_id"] for e in new_editor_annotation["details"]}
            deleted_annotation_count = len(existent_annotation_ids - new_annotation_ids)
            failed_to_delete_annotation_count = len(existent_annotation_ids) - deleted_annotation_count
            return deleted_annotation_count, failed_to_delete_annotation_count + len(nonexistent_annotation_ids)

    def delete_annotation_by_id_list(
        self,
        annotation_list: list[DeletedAnnotationInfo],
        backup_dir: Optional[Path] = None,
    ) -> None:
        """
        task_id, input_data_id, annotation_id のリストで指定されたアノテーションのみ削除する

        Args:
            annotation_list: 削除対象のアノテーションlist
            backup_dir: バックアップディレクトリ
        """

        # task_id, input_data_idごとにまとめる
        grouped: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        for item in annotation_list:
            grouped[item.task_id][item.input_data_id].append(item.annotation_id)

        total = len(annotation_list)

        deleted_annotation_count = 0
        failed_to_delete_annotation_count = 0

        task_count = len(grouped)
        deleted_task_count = 0

        logger.info(f"{task_count} 件のタスクに含まれるアノテーションを削除します。")

        for task_id, sub_grouped in grouped.items():
            annotation_count = sum(len(v) for v in sub_grouped.values())
            task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
            if task is None:
                logger.warning(f"task_id='{task_id}' :: タスクが存在しないため、アノテーション {annotation_count} 件の削除をスキップします。")
                failed_to_delete_annotation_count += annotation_count
                continue

            if task["status"] == TaskStatus.WORKING.value:
                logger.info(f"task_id='{task_id}' :: タスクが作業中状態のため、アノテーション {annotation_count} 件の削除をスキップします。")
                failed_to_delete_annotation_count += annotation_count
                continue

            if not self.is_force:  # noqa: SIM102
                if task["status"] == TaskStatus.COMPLETE.value:
                    logger.info(
                        f"task_id='{task_id}' :: タスクが完了状態のため、アノテーション {annotation_count} 件の削除をスキップします。"
                        f"完了状態のタスクのアノテーションを削除するには、`--force`オプションを指定してください。"
                    )
                    failed_to_delete_annotation_count += annotation_count
                    continue

            if not self.confirm_processing(f"task_id='{task_id}'のタスクに含まれるアノテーション {annotation_count} 件を削除しますか？"):
                failed_to_delete_annotation_count += annotation_count
                continue

            deleted_task_count += 1
            for input_data_id, annotation_ids in sub_grouped.items():
                # 指定input_data_idの全annotationを取得
                # TODO どこかのタイミングで、"v=2"のアノテーションを取得するようにする
                editor_annotation = self.service.wrapper.get_editor_annotation_or_none(self.project_id, task_id=task_id, input_data_id=input_data_id, query_params={"v": "1"})
                if editor_annotation is None:
                    logger.warning(
                        f"task_id='{task_id}'のタスクに、input_data_id='{input_data_id}'の入力データが含まれていません。 アノテーションの削除をスキップします。 :: annotation_ids={annotation_ids}"
                    )
                    failed_to_delete_annotation_count += len(annotation_ids)
                    continue

                if backup_dir is not None:
                    (backup_dir / task_id).mkdir(exist_ok=True, parents=True)
                    self.dump_annotation_obj.dump_editor_annotation(editor_annotation, json_path=backup_dir / task_id / f"{input_data_id}.json")

                sub_deleted_annotation_count, sub_failed_to_delete_annotation_count = self.delete_annotation_by_annotation_ids(editor_annotation, set(annotation_ids))
                deleted_annotation_count += sub_deleted_annotation_count
                failed_to_delete_annotation_count += sub_failed_to_delete_annotation_count

        logger.info(
            f"{deleted_task_count}/{task_count} 件のタスクに含まれている {deleted_annotation_count}/{total} 件のアノテーションを削除しました。"
            f"{failed_to_delete_annotation_count} 件のアノテーションは削除できませんでした。"
        )


class DeleteAnnotation(CommandLine):
    """
    アノテーションを削除する
    """

    COMMON_MESSAGE = "annofabcli annotation delete: error:"

    def main(self) -> None:  # noqa: PLR0912
        args = self.args
        project_id = args.project_id

        if args.backup is None:
            print(  # noqa: T201
                "間違えてアノテーションを削除してしまっときに復元できるようにするため、'--backup'でバックアップ用のディレクトリを指定することを推奨します。",
                file=sys.stderr,
            )
            if not self.confirm_processing("復元用のバックアップディレクトリが指定されていません。処理を続行しますか？"):
                return
            backup_dir = None
        else:
            backup_dir = Path(args.backup)

        if args.force:
            # --forceオプションが指定されている場合は、完了状態のタスクも削除する
            # 完了状態のタスクを削除するには、オーナーロールである必要があるため、`args.force`で条件を分岐する
            super().validate_project(project_id, [ProjectMemberRole.OWNER])
        else:
            super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])

        main_obj = DeleteAnnotationMain(self.service, project_id, all_yes=args.yes, is_force=args.force)

        if args.json is not None:
            dict_annotation_list = get_json_from_args(args.json)
            if not isinstance(dict_annotation_list, list):
                print(f"{self.COMMON_MESSAGE} argument --json: JSON形式が不正です。オブジェクトの配列を指定してください。", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

            try:
                annotation_list = [DeletedAnnotationInfo(**eml) for eml in dict_annotation_list]
            except TypeError as e:
                print(f"{self.COMMON_MESSAGE} argument --json: 無効なオブジェクト形式です。{e}", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            main_obj.delete_annotation_by_id_list(annotation_list, backup_dir=backup_dir)

        elif args.csv is not None:
            csv_path = Path(args.csv)
            if not csv_path.exists():
                print(f"{self.COMMON_MESSAGE} argument --csv: ファイルパスが存在しません。 '{args.csv}'", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

            df: pandas.DataFrame = pandas.read_csv(
                args.csv,
                dtype={"task_id": "string", "input_data_id": "string", "annotation_id": "string"},
            )
            required_cols = {"task_id", "input_data_id", "annotation_id"}
            if not required_cols.issubset(df.columns):
                print(f"{self.COMMON_MESSAGE} argument --csv: CSVに必須列がありません。{required_cols}", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

            annotation_list = [DeletedAnnotationInfo(**eml) for eml in df.to_dict(orient="records")]
            main_obj.delete_annotation_by_id_list(annotation_list, backup_dir=backup_dir)

        elif args.task_id is not None:
            task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

            if args.annotation_query is not None:
                annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params={"v": "2"})
                try:
                    dict_annotation_query = get_json_from_args(args.annotation_query)
                    annotation_query_for_cli = AnnotationQueryForCLI.from_dict(dict_annotation_query)
                    annotation_query = annotation_query_for_cli.to_query_for_api(annotation_specs)
                except ValueError as e:
                    print(f"{self.COMMON_MESSAGE} argument '--annotation_query' の値が不正です。{e}", file=sys.stderr)  # noqa: T201
                    sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            else:
                annotation_query = None

            main_obj.delete_annotation_for_task_list(task_id_list, annotation_query=annotation_query, backup_dir=backup_dir)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-t",
        "--task_id",
        type=str,
        nargs="+",
        help="削除対象のタスクのtask_idを指定します。 ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )

    example_json = [{"task_id": "t1", "input_data_id": "i1", "annotation_id": "a1"}]
    group.add_argument(
        "--json",
        type=str,
        help=f"削除対象のアノテーションをJSON配列で指定します。例: ``{json.dumps(example_json)}``",
    )
    group.add_argument(
        "--csv",
        type=str,
        help="削除対象のアノテーションを記載したCSVファイルを指定します。例: task_id,input_data_id,annotation_id",
    )

    EXAMPLE_ANNOTATION_QUERY = {"label": "car", "attributes": {"occluded": True}}  # noqa: N806
    parser.add_argument(
        "-aq",
        "--annotation_query",
        type=str,
        required=False,
        help="削除対象のアノテーションを検索する条件をJSON形式で指定します。"
        "``--csv`` または ``--json`` を指定した場合は、このオプションは無視されます。"
        "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        f"(ex): ``{json.dumps(EXAMPLE_ANNOTATION_QUERY)}``",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="指定した場合は、完了状態のタスクのアノテーションも削除します。ただし、完了状態のタスクを削除するには、オーナーロールを持つユーザーが実行する必要があります。",
    )
    parser.add_argument(
        "--backup",
        type=str,
        required=False,
        help="アノテーションのバックアップを保存するディレクトリを指定してください。アノテーションの復元は ``annotation restore`` コマンドで実現できます。",
    )
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "delete"
    subcommand_help = "アノテーションを削除します。"
    description = (
        "タスク配下のアノテーションを削除します。ただし、作業中状態のタスクのアノテーションは削除できません。"
        "間違えてアノテーションを削除したときに復元できるようにするため、 ``--backup`` でバックアップ用のディレクトリを指定することを推奨します。"
    )
    epilog = "オーナーまたはチェッカーロールを持つユーザで実行してください。ただし``--force``オプションを指定した場合は、オーナーロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
