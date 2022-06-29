from __future__ import annotations

import argparse
import dataclasses
import functools
import logging
import multiprocessing
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import annofabapi
from annofabapi.dataclass.task import Task
from annofabapi.models import ProjectMemberRole, TaskStatus

import annofabcli
from annofabcli.annotation.annotation_query import (
    AdditionalData,
    AnnotationQueryForAPI,
    AnnotationQueryForCLI,
    convert_attributes_from_cli_to_api,
)
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


class ChangeBy(Enum):
    TASK = "task"
    INPUT_DATA = "input_data"


class ChangeAnnotationAttributesMain(AbstractCommandLineWithConfirmInterface):
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        project_id: str,
        is_force: bool,
        all_yes: bool,
    ):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        AbstractCommandLineWithConfirmInterface.__init__(self, all_yes)

        self.project_id = project_id
        self.is_force = is_force

        self.dump_annotation_obj = DumpAnnotationMain(service, project_id)

    def change_annotation_attributes(
        self, annotation_list: List[Dict[str, Any]], attributes: List[AdditionalData]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        アノテーション属性値を変更する。

        Args:
            annotation_list: 変更対象のアノテーション一覧
            attributes: 変更後の属性値

        Returns:
            `batch_update_annotations`メソッドのレスポンス

        """

        def _to_request_body_elm(annotation: Dict[str, Any]) -> Dict[str, Any]:
            detail = annotation["detail"]
            return {
                "data": {
                    "project_id": annotation["project_id"],
                    "task_id": annotation["task_id"],
                    "input_data_id": annotation["input_data_id"],
                    "updated_datetime": annotation["updated_datetime"],
                    "annotation_id": detail["annotation_id"],
                    "label_id": detail["label_id"],
                    "additional_data_list": attributes_for_dict,
                },
                "_type": "Put",
            }

        attributes_for_dict: List[Dict[str, Any]] = [dataclasses.asdict(e) for e in attributes]
        request_body = [_to_request_body_elm(annotation) for annotation in annotation_list]
        return self.service.api.batch_update_annotations(self.project_id, request_body)[0]

    def get_annotation_list_for_task(
        self, task_id: str, annotation_query: AnnotationQueryForAPI
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
        dict_query = annotation_query.to_dict()
        dict_query.update({"task_id": task_id, "exact_match_task_id": True})
        annotation_list = self.service.wrapper.get_all_annotation_list(
            self.project_id, query_params={"query": dict_query}
        )
        return annotation_list

    def change_attributes_for_task(
        self,
        task_id: str,
        annotation_query: AnnotationQueryForAPI,
        attributes: List[AdditionalData],
        backup_dir: Optional[Path] = None,
        task_index: Optional[int] = None,
    ) -> bool:
        """
        タスクに対してアノテーション属性を変更する。

        Args:
            project_id:
            task_id:
            annotation_query: 変更対象のアノテーションの検索条件
            attributes: 変更後のアノテーション属性
            force: タスクのステータスによらず更新する
            backup_dir: アノテーションをバックアップとして保存するディレクトリ。指定しない場合は、バックアップを取得しない。

        Returns:
            アノテーションの属性を変更するAPI ``change_annotation_attributes`` を実行したか否か
        """
        logger_prefix = f"{str(task_index+1)} 件目: " if task_index is not None else ""
        dict_task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if dict_task is None:
            logger.warning(f"task_id = '{task_id}' は存在しません。")
            return False

        task: Task = Task.from_dict(dict_task)
        if task.status == TaskStatus.WORKING:
            logger.warning(f"task_id={task_id}: タスクが作業中状態のため、スキップします。")
            return False

        if not self.is_force:
            if task.status == TaskStatus.COMPLETE:
                logger.warning(f"task_id={task_id}: タスクが完了状態のため、スキップします。")
                return False

        annotation_list = self.get_annotation_list_for_task(task_id, annotation_query)
        logger.info(
            f"{logger_prefix}task_id='{task_id}'の変更対象アノテーション数：{len(annotation_list)}, phase={task.phase.value}, status={task.status.value}, updated_datetime={task.updated_datetime}"  # noqa: E501
        )
        if len(annotation_list) == 0:
            logger.info(f"{logger_prefix}task_id='{task_id}'には変更対象のアノテーションが存在しないので、スキップします。")
            return False

        if not self.confirm_processing(f"task_id='{task_id}' のアノテーション属性を変更しますか？"):
            return False

        if backup_dir is not None:
            self.dump_annotation_obj.dump_annotation_for_task(task_id, output_dir=backup_dir)

        self.change_annotation_attributes(annotation_list, attributes)
        logger.info(f"{logger_prefix}task_id={task_id}: アノテーション属性を変更しました。")
        return True

    def change_attributes_for_task_wrapper(
        self,
        tpl: tuple[int, str],
        annotation_query: AnnotationQueryForAPI,
        attributes: List[AdditionalData],
        backup_dir: Optional[Path] = None,
    ) -> bool:
        task_index, task_id = tpl
        try:
            return self.change_attributes_for_task(
                task_id,
                annotation_query=annotation_query,
                attributes=attributes,
                backup_dir=backup_dir,
                task_index=task_index,
            )
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"タスク'{task_id}'のアノテーションの属性の変更に失敗しました。", exc_info=True)
            return False

    def change_annotation_attributes_for_task_list(
        self,
        task_id_list: List[str],
        annotation_query: AnnotationQueryForAPI,
        attributes: List[AdditionalData],
        backup_dir: Optional[Path] = None,
        parallelism: Optional[int] = None,
    ):
        project_title = self.facade.get_project_title(self.project_id)
        logger.info(f"プロジェクト'{project_title}'に対して、タスク{len(task_id_list)} 件のアノテーションの属性を変更します。")

        if backup_dir is not None:
            backup_dir.mkdir(exist_ok=True, parents=True)

        success_count = 0
        if parallelism is not None:
            func = functools.partial(
                self.change_attributes_for_task_wrapper,
                annotation_query=annotation_query,
                attributes=attributes,
                backup_dir=backup_dir,
            )
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(func, enumerate(task_id_list))
                success_count = len([e for e in result_bool_list if e])

        else:

            for task_index, task_id in enumerate(task_id_list):

                try:
                    result = self.change_attributes_for_task(
                        task_id,
                        annotation_query=annotation_query,
                        attributes=attributes,
                        backup_dir=backup_dir,
                        task_index=task_index,
                    )
                    if result:
                        success_count += 1
                except Exception:
                    logger.warning(f"タスク'{task_id}'のアノテーションの属性の変更に失敗しました。", exc_info=True)
                    continue

        logger.info(f"{success_count} / {len(task_id_list)} 件のタスクに対してアノテーションの属性を変更しました。")


class ChangeAttributesOfAnnotation(AbstractCommandLineInterface):
    """
    アノテーション属性を変更
    """

    COMMON_MESSAGE = "annofabcli annotation change_attributes: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、'--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    @classmethod
    def get_annotation_query_for_api(
        cls, str_annotation_query: str, annotation_specs: dict[str, Any]
    ) -> AnnotationQueryForAPI:
        """
        CLIから受け取った`--annotation_query`の値から、APIに渡すクエリー情報を返す。
        """
        dict_annotation_query = get_json_from_args(str_annotation_query)
        annotation_query_for_cli = AnnotationQueryForCLI.from_dict(dict_annotation_query)
        return annotation_query_for_cli.to_query_for_api(annotation_specs)

    @classmethod
    def get_attributes_for_api(
        cls, str_attributes: str, annotation_specs: dict[str, Any], label_id: str
    ) -> list[AdditionalData]:
        """
        CLIから受け取った`--attributes`の値から、APIに渡す属性情報を返す。
        """
        dict_attributes = get_json_from_args(str_attributes)
        return convert_attributes_from_cli_to_api(dict_attributes, annotation_specs, label_id=label_id)

    def main(self):
        args = self.args

        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

        annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params={"v": "2"})

        try:
            annotation_query = self.get_annotation_query_for_api(args.annotation_query, annotation_specs)
        except ValueError as e:
            print(f"{self.COMMON_MESSAGE} argument '--annotation_query' の値が不正です。 :: {e}", file=sys.stderr)
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        try:
            attributes = self.get_attributes_for_api(
                args.attributes, annotation_specs, label_id=annotation_query.label_id
            )
        except ValueError as e:
            print(f"{self.COMMON_MESSAGE} argument '--attributes' の値が不正です。 :: {e}", file=sys.stderr)
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        if args.backup is None:
            print("間違えてアノテーションを変更してしまっときに復元できるようにするため、'--backup'でバックアップ用のディレクトリを指定することを推奨します。", file=sys.stderr)
            if not self.confirm_processing("復元用のバックアップディレクトリが指定されていません。処理を続行しますか？"):
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            backup_dir = None
        else:
            backup_dir = Path(args.backup)

        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        main_obj = ChangeAnnotationAttributesMain(
            self.service, project_id=project_id, is_force=args.force, all_yes=args.yes
        )
        main_obj.change_annotation_attributes_for_task_list(
            task_id_list,
            annotation_query=annotation_query,
            attributes=attributes,
            backup_dir=backup_dir,
            parallelism=args.parallelism,
        )


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeAttributesOfAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    EXAMPLE_ANNOTATION_QUERY = '{"label": "car", "attributes":{"occluded" true} }'
    parser.add_argument(
        "-aq",
        "--annotation_query",
        type=str,
        required=True,
        help="変更対象のアノテーションを検索する条件をJSON形式で指定します。"
        "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        f"(ex): ``{EXAMPLE_ANNOTATION_QUERY}``",
    )

    EXAMPLE_ATTRIBUTES = '{"occluded": false}'
    parser.add_argument(
        "--attributes",
        type=str,
        required=True,
        help="変更後の属性をJSON形式で指定します。" "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。" f"(ex): ``{EXAMPLE_ATTRIBUTES}``",
    )

    parser.add_argument("--force", action="store_true", help="完了状態のタスクのアノテーション属性も変更します。")

    parser.add_argument(
        "--backup",
        type=str,
        required=False,
        help="アノテーションのバックアップを保存するディレクトリを指定してください。アノテーションの復元は ``annotation restore`` コマンドで実現できます。",
    )
    parser.add_argument(
        "--parallelism",
        type=int,
        help="並列度。指定しない場合は、逐次的に処理します。指定した場合は、``--yes`` も指定してください。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "change_attributes"
    subcommand_help = "アノテーションの属性を変更します。"
    description = (
        "アノテーションの属性を一括で変更します。ただし、作業中状態のタスクのアノテーションの属性は変更できません。"
        "間違えてアノテーション属性を変更したときに復元できるようにするため、 ``--backup`` でバックアップ用のディレクトリを指定することを推奨します。"
    )
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
