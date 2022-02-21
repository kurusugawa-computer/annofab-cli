import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import annofabapi
from annofabapi.models import ProjectMemberRole, SingleAnnotation, TaskStatus
from annofabapi.utils import can_put_annotation, str_now
from dataclasses_json import DataClassJsonMixin

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.annotation.dump_annotation import DumpAnnotation
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_json_from_args,
)
from annofabcli.common.facade import AnnotationQuery, AnnotationQueryForCli

logger = logging.getLogger(__name__)


@dataclass
class AnnotationDetailForCli(DataClassJsonMixin):
    is_protected: Optional[bool] = None


class ChangePropertiesOfAnnotation(AbstractCommandLineInterface):
    """
    アノテーションのプロパティを変更
    """

    COMMON_MESSAGE = "annofabcli annotation change_properties: error:"

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.dump_annotation_obj = DumpAnnotation(service, facade, args)

    def change_properties_for_task(  # pylint: disable=too-many-return-statements
        self,
        project_id: str,
        task_id: str,
        properties: AnnotationDetailForCli,
        annotation_query: Optional[AnnotationQuery] = None,
        force: bool = False,
        backup_dir: Optional[Path] = None,
    ) -> bool:
        """
        タスクに対してアノテーションのプロパティを変更する。

        Args:
            project_id:
            task_id:
            annotation_query: 変更対象のアノテーションの検索条件
            properties: 変更後のアノテーションのプロパティ
            force: タスクのステータスによらず更新する
            backup_dir: アノテーションをバックアップとして保存するディレクトリ。指定しない場合は、バックアップを取得しない。

        """

        def change_annotation_properties(
            self,
            project_id: str,
            task_id: str,
            annotation_list: List[SingleAnnotation],
            properties: AnnotationDetailForCli,
        ):
            """
            アノテーションのプロパティを変更する。

            【注意】取扱注意

            Args:
                annotation_list: 変更対象のアノテーション一覧
                properties: 変更後のプロパティ

            Returns:
                ``メソッドのレスポンス

            """

            now_datetime = str_now()

            def to_properties_from_cli(
                annotation_list: List[SingleAnnotation], properties: AnnotationDetailForCli
            ) -> List[Dict[str, Any]]:
                annotations_for_api = []
                annotation_details_by_input_data: Dict[str, List[Dict[str, Any]]] = {}

                for annotation in annotation_list:
                    input_data_id = annotation["input_data_id"]
                    if input_data_id not in annotation_details_by_input_data:
                        annotation_details_by_input_data[input_data_id] = []
                    annotation_details_by_input_data[input_data_id].append(annotation["detail"])

                for input_data_id, annotation_details in annotation_details_by_input_data.items():
                    annotations, _ = self.service.api.get_editor_annotation(project_id, task_id, input_data_id)
                    for single_annotation in annotations["details"]:
                        for annotation_detail in annotation_details:
                            if annotation_detail["annotation_id"] != single_annotation["annotation_id"]:
                                continue
                            single_annotation["is_protected"] = properties.is_protected
                            # 更新日時も一緒に変更する
                            single_annotation["updated_datetime"] = now_datetime
                    annotations_for_api.append(annotations)
                return annotations_for_api

            def _to_request_body_elm(annotation: Dict[str, Any]):
                return self.service.api.put_annotation(
                    annotation["project_id"],
                    annotation["task_id"],
                    annotation["input_data_id"],
                    {
                        "project_id": annotation["project_id"],
                        "task_id": annotation["task_id"],
                        "input_data_id": annotation["input_data_id"],
                        "details": annotation["details"],
                        "updated_datetime": annotation["updated_datetime"],
                    },
                )

            annotations = to_properties_from_cli(annotation_list, properties)
            for annotation in annotations:
                _to_request_body_elm(annotation)

        dict_task = self.service.wrapper.get_task_or_none(project_id, task_id)
        if dict_task is None:
            logger.warning(f"task_id = '{task_id}' は存在しません。")
            return False

        logger.debug(
            f"task_id={task_id}, phase={dict_task['phase']}, status={dict_task['status']}, "
            f"updated_datetime={dict_task['updated_datetime']}"
        )

        if dict_task["status"] in [TaskStatus.WORKING.value, TaskStatus.COMPLETE.value]:
            logger.info(f"タスク'{task_id}'は作業中または受入完了状態のため、アノテーションプロパティの変更をスキップします。 status={dict_task['status']}")
            return False

        old_account_id: Optional[str] = None
        changed_operator = False

        if force:
            if not can_put_annotation(dict_task, self.service.api.account_id):
                logger.debug(f"タスク'{task_id}' の担当者を自分自身に変更します。")
                self.service.wrapper.change_task_operator(
                    project_id, task_id, operator_account_id=self.service.api.account_id
                )
                changed_operator = True
                old_account_id = dict_task["account_id"]

        else:
            if not can_put_annotation(dict_task, self.service.api.account_id):
                logger.debug(
                    f"タスク'{task_id}'は、過去に誰かに割り当てられたタスクで、現在の担当者が自分自身でないため、アノテーションのプロパティの変更をスキップします。"
                    f"担当者を自分自身に変更してアノテーションのプロパティを変更する場合は `--force` を指定してください。"
                )
                return False

        annotation_list = self.facade.get_annotation_list_for_task(project_id, task_id, query=annotation_query)
        logger.info(f"task_id='{task_id}'の変更対象アノテーション数：{len(annotation_list)}")
        if len(annotation_list) == 0:
            logger.info(f"task_id='{task_id}'には変更対象のアノテーションが存在しないので、スキップします。")
            return False

        if not self.confirm_processing(f"task_id='{task_id}' のアノテーションのプロパティを変更しますか？"):
            return False

        if backup_dir is not None:
            self.dump_annotation_obj.dump_annotation_for_task(project_id, task_id, output_dir=backup_dir)

        try:
            change_annotation_properties(self, project_id, task_id, annotation_list, properties)
            logger.info(f"task_id={task_id}: アノテーションのプロパティを変更しました。")
            return True
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"task_id={task_id}: アノテーションのプロパティの変更に失敗しました。", exc_info=True)
            return False
        finally:
            if changed_operator:
                logger.debug(f"タスク'{task_id}' の担当者を元に戻します。")
                old_account_id = dict_task["account_id"]
                self.service.wrapper.change_task_operator(project_id, task_id, operator_account_id=old_account_id)

    def change_annotation_properties(
        self,
        project_id: str,
        task_id_list: List[str],
        properties: AnnotationDetailForCli,
        annotation_query: Optional[AnnotationQuery] = None,
        force: bool = False,
        backup_dir: Optional[Path] = None,
    ):
        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        project_title = self.facade.get_project_title(project_id)
        logger.info(f"プロジェクト'{project_title}'に対して、タスク{len(task_id_list)} 件のアノテーションのプロパティを変更します。")

        if backup_dir is not None:
            backup_dir.mkdir(exist_ok=True, parents=True)

        for task_index, task_id in enumerate(task_id_list):
            logger.debug(f"{task_index+1} / {len(task_id_list)} 件目: タスク '{task_id}' のアノテーションのプロパティを変更します。")

            try:
                self.change_properties_for_task(
                    project_id,
                    task_id,
                    properties=properties,
                    annotation_query=annotation_query,
                    force=force,
                    backup_dir=backup_dir,
                )
            except Exception:  # pylint: disable=broad-except
                logger.warning(f"task_id={task_id}: アノテーションのプロパティの変更に失敗しました。", exc_info=True)

    def main(self):
        args = self.args
        project_id = args.project_id
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

        dict_annotation_query = get_json_from_args(args.annotation_query)
        if dict_annotation_query is not None:
            annotation_query_for_cli = AnnotationQueryForCli.from_dict(dict_annotation_query)
            try:
                annotation_query = self.facade.to_annotation_query_from_cli(project_id, annotation_query_for_cli)
            except ValueError as e:
                print(f"{self.COMMON_MESSAGE} argument '--annotation_query' の値が不正です。{e}", file=sys.stderr)
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
        else:
            annotation_query = None

        properties_of_dict = get_json_from_args(args.properties)
        properties_for_cli = AnnotationDetailForCli.from_dict(properties_of_dict)

        if args.backup is None:
            print("間違えてアノテーションを変更してしまっときに復元できるようにするため、'--backup'でバックアップ用のディレクトリを指定することを推奨します。", file=sys.stderr)
            if not self.confirm_processing("復元用のバックアップディレクトリが指定されていません。処理を続行しますか？"):
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            backup_dir = None
        else:
            backup_dir = Path(args.backup)

        self.change_annotation_properties(
            project_id,
            task_id_list,
            properties=properties_for_cli,
            annotation_query=annotation_query,
            force=args.force,
            backup_dir=backup_dir,
        )


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangePropertiesOfAnnotation(service, facade, args).main()


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
        required=False,
        help="変更対象のアノテーションを検索する条件をJSON形式で指定します。"
        "``label_id`` または ``label_name_en`` のいずれかは必ず指定してください。"
        "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        f"(ex): ``{EXAMPLE_ANNOTATION_QUERY}``",
    )

    EXAMPLE_PROPERTIES = '{"is_protected": true}'
    parser.add_argument(
        "--properties",
        type=str,
        required=True,
        help="変更後のプロパティをJSON形式で指定します。変更可能なキーは ``is_protected`` です。"
        "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        f"(ex): ``{EXAMPLE_PROPERTIES}``",
    )

    parser.add_argument(
        "--force", action="store_true", help="過去に割り当てられていて現在の担当者が自分自身でない場合、タスクの担当者を自分自身に変更してからアノテーションプロパティを変更します。"
    )

    parser.add_argument(
        "--backup",
        type=str,
        required=False,
        help="アノテーションのバックアップを保存するディレクトリを指定してください。アノテーションの復元は ``annotation restore`` コマンドで実現できます。",
    )
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "change_properties"
    subcommand_help = "アノテーションのプロパティを変更します。"
    description = (
        "アノテーションのプロパティを一括で変更します。ただし、作業中状態のタスクのアノテーションのプロパティは変更できません。"
        "間違えてアノテーションのプロパティを変更したときに復元できるようにするため、 ``--backup`` でバックアップ用のディレクトリを指定することを推奨します。"
    )
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
