import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import annofabapi
import requests
from annofabapi.dataclass.task import Task
from annofabapi.models import ProjectMemberRole, TaskStatus

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.annotation.dump_annotation import DumpAnnotation
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_json_from_args,
)
from annofabcli.common.facade import AdditionalData, AdditionalDataForCli, AnnotationQuery, AnnotationQueryForCli

logger = logging.getLogger(__name__)


class ChangeAttributesOfAnnotation(AbstractCommandLineInterface):
    """
    アノテーション属性を変更
    """

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.dump_annotation_obj = DumpAnnotation(service, facade, args)

    def change_attributes_for_task(
        self,
        project_id: str,
        task_id: str,
        annotation_query: AnnotationQuery,
        attributes: List[AdditionalData],
        force: bool = False,
        backup_dir: Optional[Path] = None,
    ) -> None:
        """
        タスクに対してアノテーション属性を変更する。

        Args:
            project_id:
            task_id:
            annotation_query: 変更対象のアノテーションの検索条件
            attributes: 変更後のアノテーション属性
            force: タスクのステータスによらず更新する
            backup_dir: アノテーションをバックアップとして保存するディレクトリ。指定しない場合は、バックアップを取得しない。

        """
        dict_task = self.service.wrapper.get_task_or_none(project_id, task_id)
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

        if not force:
            if task.status == TaskStatus.COMPLETE:
                logger.warning(f"task_id={task_id}: タスクが完了状態のため、スキップします。")
                return

        annotation_list = self.facade.get_annotation_list_for_task(project_id, task_id, query=annotation_query)
        logger.info(f"task_id='{task_id}'の変更対象アノテーション数：{len(annotation_list)}")
        if len(annotation_list) == 0:
            logger.info(f"task_id='{task_id}'には変更対象のアノテーションが存在しないので、スキップします。")
            return

        if not self.confirm_processing(f"task_id='{task_id}' のアノテーション属性を変更しますか？"):
            return

        if backup_dir is not None:
            self.dump_annotation_obj.dump_annotation_for_task(project_id, task_id, output_dir=backup_dir)

        try:
            self.facade.change_annotation_attributes(project_id, annotation_list, attributes)
            logger.info(f"task_id={task_id}: アノテーション属性を変更しました。")
        except requests.HTTPError as e:
            logger.warning(e)
            logger.warning(f"task_id={task_id}: アノテーション属性の変更に失敗しました。")

    def change_annotation_attributes(
        self,
        project_id: str,
        task_id_list: List[str],
        annotation_query: AnnotationQuery,
        attributes: List[AdditionalData],
        force: bool = False,
        backup_dir: Optional[Path] = None,
    ):
        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        project_title = self.facade.get_project_title(project_id)
        logger.info(f"プロジェクト'{project_title}'に対して、タスク{len(task_id_list)} 件のアノテーションの属性を変更します。")

        if backup_dir is not None:
            backup_dir.mkdir(exist_ok=True, parents=True)

        for task_index, task_id in enumerate(task_id_list):
            logger.info(f"{task_index+1} / {len(task_id_list)} 件目: タスク '{task_id}' のアノテーションの属性を変更します。")
            self.change_attributes_for_task(
                project_id,
                task_id,
                annotation_query=annotation_query,
                attributes=attributes,
                force=force,
                backup_dir=backup_dir,
            )

    def main(self):
        args = self.args
        project_id = args.project_id
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

        dict_annotation_query = get_json_from_args(args.annotation_query)
        annotation_query_for_cli = AnnotationQueryForCli.from_dict(dict_annotation_query)
        try:
            annotation_query = self.facade.to_annotation_query_from_cli(project_id, annotation_query_for_cli)
        except ValueError as e:
            print(f"'--annotation_queryの値が不正です。{e}", file=sys.stderr)
            return

        attributes_of_dict: List[Dict[str, Any]] = get_json_from_args(args.attributes)
        attributes_for_cli: List[AdditionalDataForCli] = [AdditionalDataForCli.from_dict(e) for e in attributes_of_dict]
        try:
            attributes = self.facade.to_attributes_from_cli(project_id, annotation_query.label_id, attributes_for_cli)
        except ValueError as e:
            print(f"'--attributesの値が不正です。{e}", file=sys.stderr)
            return

        if args.backup is None:
            print("間違えてアノテーションを変更してしまっときに復元できるようにするため、'--backup'でバックアップ用のディレクトリを指定することを推奨します。", file=sys.stderr)
            if not self.confirm_processing("復元用のバックアップディレクトリが指定されていません。処理を続行しますか？"):
                return
            backup_dir = None
        else:
            backup_dir = Path(args.backup)

        self.change_annotation_attributes(
            project_id,
            task_id_list,
            annotation_query=annotation_query,
            attributes=attributes,
            force=args.force,
            backup_dir=backup_dir,
        )


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeAttributesOfAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    EXAMPLE_ANNOTATION_QUERY = (
        '{"label_name_en": "car", "attributes":[{"additional_data_definition_name_en": "occluded", "flag": true}]}'
    )
    parser.add_argument(
        "-aq",
        "--annotation_query",
        type=str,
        required=True,
        help="変更対象のアノテーションを検索する条件をJSON形式で指定します。"
        "'label_id' または 'label_name_en'のいずれかは必ず指定してください。"
        "`file://`を先頭に付けると、JSON形式のファイルを指定できます。"
        f"(ex): `{EXAMPLE_ANNOTATION_QUERY}`",
    )

    EXAMPLE_ATTIRBUTES = '[{"additional_data_definition_name_en": "occluded", "flag": false}]'
    parser.add_argument(
        "--attributes",
        type=str,
        required=True,
        help="変更後の属性をJSON形式で指定します。" "`file://`を先頭に付けると、JSON形式のファイルを指定できます。" f"(ex): `{EXAMPLE_ATTIRBUTES}`",
    )

    parser.add_argument("--force", action="store_true", help="完了状態のタスクのアノテーション属性も変更します。")

    parser.add_argument(
        "--backup",
        type=str,
        required=False,
        help="アノテーションのバックアップを保存するディレクトリを指定してください。アノテーションの復元は'annotation restore'コマンドで実現できます。",
    )
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "change_attributes"
    subcommand_help = "アノテーションの属性を変更します。"
    description = (
        "アノテーションの属性を一括で変更します。ただし、作業中状態のタスクのアノテーションの属性は変更できません。"
        "間違えてアノテーション属性を変更したときに復元できるようにするため、'--backup'でバックアップ用のディレクトリを指定することを推奨します。"
    )
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
