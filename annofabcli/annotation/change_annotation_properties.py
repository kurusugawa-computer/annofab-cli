from __future__ import annotations

import argparse
import functools
import json
import logging
import multiprocessing
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import annofabapi
from annofabapi.models import ProjectMemberRole, SingleAnnotation, TaskStatus
from annofabapi.utils import can_put_annotation, str_now
from dataclasses_json import DataClassJsonMixin

import annofabcli
from annofabcli.annotation.annotation_query import AnnotationQueryForAPI, AnnotationQueryForCLI
from annofabcli.annotation.dump_annotation import DumpAnnotationMain
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
    get_json_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


@dataclass
class AnnotationDetailForCli(DataClassJsonMixin):
    is_protected: Optional[bool] = None


class ChangePropertiesOfAnnotationMain(CommandLineWithConfirm):
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

    def change_annotation_properties(  # noqa: ANN201
        self,
        task_id: str,
        annotation_list: list[SingleAnnotation],
        properties: AnnotationDetailForCli,
    ):
        """
        アノテーションのプロパティを変更する。

        Args:
            annotation_list: 変更対象のアノテーション一覧
            properties: 変更後のプロパティ

        """

        now_datetime = str_now()

        def to_properties_from_cli(annotation_list: list[SingleAnnotation], properties: AnnotationDetailForCli) -> list[dict[str, Any]]:
            annotations_for_api = []
            annotation_details_by_input_data: dict[str, list[dict[str, Any]]] = {}

            # input_data_idごとにannotation_listを分ける
            for annotation in annotation_list:
                input_data_id = annotation["input_data_id"]
                if input_data_id not in annotation_details_by_input_data:
                    annotation_details_by_input_data[input_data_id] = []
                annotation_details_by_input_data[input_data_id].append(annotation["detail"])

            for input_data_id, annotation_details in annotation_details_by_input_data.items():
                annotations, _ = self.service.api.get_editor_annotation(self.project_id, task_id, input_data_id)
                for detail in annotations["details"]:
                    # "url"が存在するとエラーになるため、取り除く
                    detail.pop("url", None)
                    for annotation_detail in annotation_details:
                        if annotation_detail["annotation_id"] != detail["annotation_id"]:
                            continue
                        detail["is_protected"] = properties.is_protected
                        # 更新日時も一緒に変更する
                        detail["updated_datetime"] = now_datetime
                annotations_for_api.append(annotations)
            return annotations_for_api

        def _to_request_body_elm(annotation: dict[str, Any]):  # noqa: ANN202
            return self.service.api.put_annotation(
                annotation["project_id"],
                annotation["task_id"],
                annotation["input_data_id"],
                request_body={
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

    def change_properties_for_task(  # pylint: disable=too-many-return-statements  # noqa: PLR0911
        self,
        task_id: str,
        properties: AnnotationDetailForCli,
        annotation_query: Optional[AnnotationQueryForAPI] = None,
        backup_dir: Optional[Path] = None,
        task_index: Optional[int] = None,
    ) -> bool:
        """
        タスクに対してアノテーションのプロパティを変更する。

        Args:
            task_id:
            annotation_query: 変更対象のアノテーションの検索条件
            properties: 変更後のアノテーションのプロパティ
            backup_dir: アノテーションをバックアップとして保存するディレクトリ。指定しない場合は、バックアップを取得しない。

        """
        logger_prefix = f"{task_index + 1!s} 件目: " if task_index is not None else ""
        dict_task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if dict_task is None:
            logger.warning(f"task_id = '{task_id}' は存在しません。")
            return False

        logger.debug(f"{logger_prefix}task_id='{task_id}', phase={dict_task['phase']}, status={dict_task['status']}, updated_datetime={dict_task['updated_datetime']}")

        if dict_task["status"] in [TaskStatus.WORKING.value, TaskStatus.COMPLETE.value]:
            logger.info(f"タスク'{task_id}'は作業中または受入完了状態のため、アノテーションプロパティの変更をスキップします。 status={dict_task['status']}")
            return False

        old_account_id: Optional[str] = dict_task["account_id"]
        changed_operator = False

        if self.is_force:
            if not can_put_annotation(dict_task, self.service.api.account_id):
                logger.debug(f"タスク'{task_id}' の担当者を自分自身に変更します。")
                dict_task = self.service.wrapper.change_task_operator(
                    self.project_id,
                    task_id,
                    operator_account_id=self.service.api.account_id,
                    last_updated_datetime=dict_task["updated_datetime"],
                )
                changed_operator = True

        else:  # noqa: PLR5501
            if not can_put_annotation(dict_task, self.service.api.account_id):
                logger.debug(
                    f"タスク'{task_id}'は、過去に誰かに割り当てられたタスクで、現在の担当者が自分自身でないため、アノテーションのプロパティの変更をスキップします。"
                    f"担当者を自分自身に変更してアノテーションのプロパティを変更する場合は `--force` を指定してください。"
                )
                return False

        annotation_list = self.get_annotation_list_for_task(task_id, annotation_query=annotation_query)
        logger.info(f"{logger_prefix}task_id='{task_id}'の変更対象アノテーション数：{len(annotation_list)}")
        if len(annotation_list) == 0:
            logger.info(f"task_id='{task_id}'には変更対象のアノテーションが存在しないので、スキップします。")
            return False

        if not self.confirm_processing(f"task_id='{task_id}' のアノテーションのプロパティを変更しますか？"):
            return False

        if backup_dir is not None:
            self.dump_annotation_obj.dump_annotation_for_task(task_id, output_dir=backup_dir)

        try:
            self.change_annotation_properties(task_id, annotation_list, properties)
            logger.info(f"{logger_prefix}task_id='{task_id}' :: アノテーションのプロパティを変更しました。")
            return True  # noqa: TRY300
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"task_id='{task_id}' :: アノテーションのプロパティの変更に失敗しました。", exc_info=True)
            return False
        finally:
            if changed_operator:
                logger.debug(f"タスク'{task_id}' の担当者を元に戻します。")
                self.service.wrapper.change_task_operator(
                    self.project_id,
                    task_id,
                    operator_account_id=old_account_id,
                    last_updated_datetime=dict_task["updated_datetime"],
                )

    def change_properties_for_task_wrapper(
        self,
        tpl: tuple[int, str],
        properties: AnnotationDetailForCli,
        annotation_query: Optional[AnnotationQueryForAPI] = None,
        backup_dir: Optional[Path] = None,
    ) -> bool:
        task_index, task_id = tpl
        try:
            return self.change_properties_for_task(
                task_id,
                properties=properties,
                annotation_query=annotation_query,
                backup_dir=backup_dir,
                task_index=task_index,
            )
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"task_id='{task_id}' :: アノテーションのプロパティの変更に失敗しました。", exc_info=True)
            return False

    def change_annotation_properties_task_list(  # noqa: ANN201
        self,
        task_id_list: list[str],
        properties: AnnotationDetailForCli,
        annotation_query: Optional[AnnotationQueryForAPI] = None,
        backup_dir: Optional[Path] = None,
        parallelism: Optional[int] = None,
    ):
        project_title = self.facade.get_project_title(self.project_id)
        logger.info(f"プロジェクト'{project_title}'に対して、タスク{len(task_id_list)} 件のアノテーションのプロパティを変更します")

        if backup_dir is not None:
            backup_dir.mkdir(exist_ok=True, parents=True)

        success_count = 0
        if parallelism is not None:
            func = functools.partial(
                self.change_properties_for_task_wrapper,
                properties=properties,
                annotation_query=annotation_query,
                backup_dir=backup_dir,
            )
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(func, enumerate(task_id_list))
                success_count = len([e for e in result_bool_list if e])

        else:
            for task_index, task_id in enumerate(task_id_list):
                logger.debug(f"{task_index + 1} / {len(task_id_list)} 件目: タスク '{task_id}' のアノテーションのプロパティを変更します。")

                try:
                    result = self.change_properties_for_task(
                        task_id,
                        properties=properties,
                        annotation_query=annotation_query,
                        backup_dir=backup_dir,
                    )
                    if result:
                        success_count += 1
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"task_id='{task_id}' :: アノテーションのプロパティの変更に失敗しました。", exc_info=True)
                    continue

        logger.info(f"{success_count} / {len(task_id_list)} 件のタスクに対してアノテーションのプロパティを変更しました。")


class ChangePropertiesOfAnnotation(CommandLine):
    """
    アノテーションのプロパティを変更
    """

    COMMON_MESSAGE = "annofabcli annotation change_properties: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、'--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args

        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id
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

        properties_of_dict = get_json_from_args(args.properties)
        properties_for_cli = AnnotationDetailForCli.from_dict(properties_of_dict)

        if args.backup is None:
            print(  # noqa: T201
                "間違えてアノテーションを変更してしまっときに復元できるようにするため、'--backup'でバックアップ用のディレクトリを指定することを推奨します。",
                file=sys.stderr,
            )
            if not self.confirm_processing("復元用のバックアップディレクトリが指定されていません。処理を続行しますか？"):
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            backup_dir = None
        else:
            backup_dir = Path(args.backup)

        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        main_obj = ChangePropertiesOfAnnotationMain(self.service, project_id=project_id, is_force=args.force, all_yes=args.yes)
        main_obj.change_annotation_properties_task_list(
            task_id_list,
            properties=properties_for_cli,
            annotation_query=annotation_query,
            backup_dir=backup_dir,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangePropertiesOfAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    EXAMPLE_ANNOTATION_QUERY = {"label": "car", "attributes": {"occluded": True}}  # noqa: N806

    parser.add_argument(
        "-aq",
        "--annotation_query",
        type=str,
        required=False,
        help=f"変更対象のアノテーションを検索する条件をJSON形式で指定します。(ex): ``{json.dumps(EXAMPLE_ANNOTATION_QUERY)}``",
    )

    EXAMPLE_PROPERTIES = '{"is_protected": true}'  # noqa: N806
    parser.add_argument(
        "--properties",
        type=str,
        required=True,
        help=f"変更後のプロパティをJSON形式で指定します。変更可能なキーは ``is_protected`` です。``file://`` を先頭に付けると、JSON形式のファイルを指定できます。(ex): ``{EXAMPLE_PROPERTIES}``",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="過去に割り当てられていて現在の担当者が自分自身でない場合、タスクの担当者を自分自身に変更してからアノテーションプロパティを変更します。",
    )

    parser.add_argument(
        "--backup",
        type=str,
        required=False,
        help="アノテーションのバックアップを保存するディレクトリを指定してください。アノテーションの復元は ``annotation restore`` コマンドで実現できます。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="並列度。指定しない場合は、逐次的に処理します。指定した場合は、``--yes`` も指定してください。",
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
