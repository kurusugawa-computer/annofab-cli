from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, List, Optional

import annofabapi
import requests
from annofabapi.dataclass.task import Task
from annofabapi.models import ProjectMemberRole, TaskStatus

import annofabcli
from annofabcli.annotation.annotation_query import AnnotationQueryForAPI, AnnotationQueryForCLI
from annofabcli.annotation.dump_annotation import DumpAnnotationMain
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    AbstractCommandLineWithConfirmInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_json_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class DeleteAnnotationMain(AbstractCommandLineWithConfirmInterface):
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
    ):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.is_force = is_force
        AbstractCommandLineWithConfirmInterface.__init__(self, all_yes)
        self.project_id = project_id
        self.dump_annotation_obj = DumpAnnotationMain(service, project_id)

    def delete_annotation_list(self, annotation_list: list[dict[str, Any]]):
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
        self.service.api.batch_update_annotations(self.project_id, request_body)

    def get_annotation_list_for_task(
        self, task_id: str, annotation_query: Optional[AnnotationQueryForAPI]
    ) -> list[dict[str, Any]]:
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

        annotation_list = self.service.wrapper.get_all_annotation_list(
            self.project_id, query_params={"query": dict_query}
        )
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
            logger.warning(f"task_id = '{task_id}' は存在しません。")
            return

        task: Task = Task.from_dict(dict_task)
        logger.info(
            f"task_id={task.task_id}, phase={task.phase.value}, status={task.status.value}, "
            f"updated_datetime={task.updated_datetime}"
        )

        if task.status == TaskStatus.WORKING:
            logger.warning(f"task_id={task_id}: タスクが作業中状態のため、スキップします。")
            return

        if not self.is_force:
            if task.status == TaskStatus.COMPLETE:
                logger.warning(f"task_id={task_id}: タスクが完了状態のため、スキップします。")
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
            logger.info(f"task_id={task_id}: アノテーションを削除しました。")
        except requests.HTTPError:
            logger.warning(f"task_id={task_id}: アノテーションの削除に失敗しました。", exc_info=True)

    def delete_annotation_for_task_list(
        self,
        task_id_list: List[str],
        annotation_query: Optional[AnnotationQueryForAPI] = None,
        backup_dir: Optional[Path] = None,
    ):
        project_title = self.facade.get_project_title(self.project_id)
        logger.info(f"プロジェクト'{project_title}'に対して、タスク{len(task_id_list)} 件のアノテーションを削除します。")

        if backup_dir is not None:
            backup_dir.mkdir(exist_ok=True, parents=True)

        for task_index, task_id in enumerate(task_id_list):
            logger.info(f"{task_index+1} / {len(task_id_list)} 件目: タスク '{task_id}' を削除します。")
            self.delete_annotation_for_task(
                task_id,
                annotation_query=annotation_query,
                backup_dir=backup_dir,
            )


class DeleteAnnotation(AbstractCommandLineInterface):
    """
    アノテーションを削除する
    """

    COMMON_MESSAGE = "annofabcli annotation delete: error:"

    def main(self):
        args = self.args
        project_id = args.project_id
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

        if args.annotation_query is not None:
            annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params={"v": "2"})
            try:
                dict_annotation_query = get_json_from_args(args.annotation_query)
                annotation_query_for_cli = AnnotationQueryForCLI.from_dict(dict_annotation_query)
                annotation_query = annotation_query_for_cli.to_query_for_api(annotation_specs)
            except ValueError as e:
                print(f"{self.COMMON_MESSAGE} argument '--annotation_query' の値が不正です。{e}", file=sys.stderr)
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
        else:
            annotation_query = None

        if args.backup is None:
            print("間違えてアノテーションを削除してしまっときに復元できるようにするため、'--backup'でバックアップ用のディレクトリを指定することを推奨します。", file=sys.stderr)
            if not self.confirm_processing("復元用のバックアップディレクトリが指定されていません。処理を続行しますか？"):
                return
            backup_dir = None
        else:
            backup_dir = Path(args.backup)

        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        main_obj = DeleteAnnotationMain(self.service, project_id, all_yes=args.yes, is_force=args.force)
        main_obj.delete_annotation_for_task_list(task_id_list, annotation_query=annotation_query, backup_dir=backup_dir)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    EXAMPLE_ANNOTATION_QUERY = '{"label": "car", "attributes":{"occluded" true} }'

    parser.add_argument(
        "-aq",
        "--annotation_query",
        type=str,
        required=False,
        help="削除対象のアノテーションを検索する条件をJSON形式で指定します。"
        "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        f"(ex): ``{EXAMPLE_ANNOTATION_QUERY}``",
    )

    parser.add_argument("--force", action="store_true", help="完了状態のタスクのアノテーションを削除します。")
    parser.add_argument(
        "--backup",
        type=str,
        required=False,
        help="アノテーションのバックアップを保存するディレクトリを指定してください。アノテーションの復元は ``annotation restore`` コマンドで実現できます。",
    )
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "delete"
    subcommand_help = "アノテーションを削除します。"
    description = (
        "タスク配下のアノテーションを削除します。" + "ただし、作業中状態のタスクのアノテーションは削除できません。"
        "間違えてアノテーションを削除したときに復元できるようにするため、 ``--backup`` でバックアップ用のディレクトリを指定することを推奨します。"
    )
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
