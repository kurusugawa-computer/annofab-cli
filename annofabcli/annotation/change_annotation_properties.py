import argparse
import logging
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import annofabapi
import requests
from annofabapi.dataclass.annotation import AnnotationDetail
from annofabapi.dataclass.task import Task
from annofabapi.models import ProjectMemberRole, SingleAnnotation, TaskStatus

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
from dataclasses_json import DataClassJsonMixin

logger = logging.getLogger(__name__)


@dataclass
class AnnotationDetailForCli(DataClassJsonMixin):
    is_protected: Optional[bool] = None


class ChangeBy(Enum):
    TASK = "task"
    INPUT_DATA = "input_data"


def change_annotation_properties(
        self, annotation_list: List[SingleAnnotation], properties: AnnotationDetailForCli
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

    def to_properties_from_cli(
        annotation_list: List[SingleAnnotation], properties: AnnotationDetailForCli
    ) -> List[AnnotationDetail]:
        api_properties = []
        for annotation in annotation_list:
            annotation, _ = self.service.api.get_editor_annotation(
                annotation["project_id"], annotation["task_id"], annotation["input_data_id"]
            )
            detail = annotation["details"][0]
            api_properties.append(
                AnnotationDetail(
                    annotation_id=properties.annotation_id if properties.annotation_id is not None
                    else detail["annotation_id"],
                    account_id=properties.account_id if properties.account_id is not None
                    else detail["account_id"],
                    label_id=properties.label_id if properties.label_id is not None
                    else detail["label_id"],
                    is_protected=properties.is_protected if properties.is_protected is not None
                    else detail["is_protected"],
                    data_holding_type=properties.data_holding_type if properties.data_holding_type is not None
                    else detail["data_holding_type"],
                    additional_data_list=properties.additional_data_list
                    if properties.additional_data_list is not None
                    else detail["additional_data_list"],
                    data=properties.data if properties.data is not None
                    else detail["data"],
                    path=properties.path,
                    etag=None,
                    url=None,
                    created_datetime=properties.created_datetime,
                    updated_datetime=properties.updated_datetime,
                )
            )
        return api_properties

    def _to_request_body_elm(annotation: Dict[str, Any]):
        return(
            self.service.api.put_annotation(
                annotation["project_id"], annotation["task_id"], annotation["input_data_id"],
                {
                    "project_id": annotation["project_id"],
                    "task_id": annotation["task_id"],
                    "input_data_id": annotation["input_data_id"],
                    "details": details_for_dict,
                    "updated_datetime": annotation["updated_datetime"],
                }
            )
        )

    details = to_properties_from_cli(annotation_list, properties)
    for idx, annotation in enumerate(annotation_list):
        details_for_dict = [asdict(details[idx])]
        _to_request_body_elm(annotation)
    return True


class ChangePropertiesOfAnnotation(AbstractCommandLineInterface):
    """
    アノテーションのプロパティを変更
    """

    COMMON_MESSAGE = "annofabcli annotation change_properties: error:"

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.dump_annotation_obj = DumpAnnotation(service, facade, args)

    def change_properties_for_task(
        self,
        project_id: str,
        task_id: str,
        annotation_query: AnnotationQuery,
        properties: AnnotationDetailForCli,
        change_by: ChangeBy,
        force: bool = False,
        backup_dir: Optional[Path] = None,
    ) -> None:
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

        if not self.confirm_processing(f"task_id='{task_id}' のアノテーションのプロパティを変更しますか？"):
            return

        if backup_dir is not None:
            self.dump_annotation_obj.dump_annotation_for_task(project_id, task_id, output_dir=backup_dir)

        try:
            if change_by == ChangeBy.INPUT_DATA:
                dict_annotation_list_by_input_data = defaultdict(list)
                for annotation in annotation_list:
                    dict_annotation_list_by_input_data[annotation["input_data_id"]].append(annotation)

                for input_data_id, annotation_list_by_input_data in dict_annotation_list_by_input_data.items():
                    logger.debug(
                        f"task_id={task_id}, input_data_id={input_data_id}: "
                        f"{len(annotation_list_by_input_data)}個のアノテーションのプロパティを変更しました。"
                    )
                    self.facade.change_annotation_properties(annotation_list_by_input_data, properties)
            else:
                self.facade.change_annotation_properties(annotation_list, properties)

            logger.info(f"task_id={task_id}: アノテーションのプロパティを変更しました。")
        except requests.HTTPError as e:
            logger.warning(e)
            logger.warning(f"task_id={task_id}: アノテーションのプロパティの変更に失敗しました。")

    def change_annotation_properties(
        self,
        project_id: str,
        task_id_list: List[str],
        annotation_query: AnnotationQuery,
        properties: AnnotationDetailForCli,
        change_by: ChangeBy = ChangeBy.TASK,
        force: bool = False,
        backup_dir: Optional[Path] = None,
    ):
        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        project_title = self.facade.get_project_title(project_id)
        logger.info(f"プロジェクト'{project_title}'に対して、タスク{len(task_id_list)} 件のアノテーションのプロパティを変更します。")

        if backup_dir is not None:
            backup_dir.mkdir(exist_ok=True, parents=True)

        for task_index, task_id in enumerate(task_id_list):
            logger.info(f"{task_index+1} / {len(task_id_list)} 件目: タスク '{task_id}' のアノテーションのプロパティを変更します。")
            self.change_properties_for_task(
                project_id,
                task_id,
                annotation_query=annotation_query,
                properties=properties,
                force=force,
                change_by=change_by,
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
            print(f"{self.COMMON_MESSAGE} argument '--annotation_query' の値が不正です。{e}", file=sys.stderr)
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

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
            annotation_query=annotation_query,
            properties=properties_for_cli,
            force=args.force,
            change_by=ChangeBy(args.change_by),
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
        required=True,
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
        help="変更後のプロパティをJSON形式で指定します。" "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。" f"(ex): ``{EXAMPLE_PROPERTIES}``",
    )

    parser.add_argument("--force", action="store_true", help="完了状態のタスクのアノテーションのプロパティも変更します。")

    parser.add_argument(
        "--change_by",
        type=str,
        choices=[ChangeBy.TASK.value, ChangeBy.INPUT_DATA.value],
        default=ChangeBy.TASK.value,
        help="アノテーションプロパティの変更単位を指定してください。[Deprecated] 廃止される可能性があります。",
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
