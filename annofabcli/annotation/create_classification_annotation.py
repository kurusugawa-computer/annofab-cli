from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

import annofabapi
from annofabapi.models import DefaultAnnotationType, ProjectMemberRole, TaskStatus
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor
from annofabapi.utils import can_put_annotation

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class CreateClassificationAnnotationMain(CommandLineWithConfirm):
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        project_id: str,
        all_yes: bool,
        is_force: bool,
    ) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)
        CommandLineWithConfirm.__init__(self, all_yes)

        self.project_id = project_id
        self.is_force = is_force

    def create_classification_annotation_for_task(self, task_id: str, labels: list[str]) -> int:
        """
        1個のタスクに対して全体アノテーションを作成します。

        Args:
            task_id: タスクID
            labels: ラベル名のリスト

        Returns:
            作成した全体アノテーションの個数
        """
        # タスク情報を取得
        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"task_id='{task_id}'であるタスクは存在しません。")
            return 0

        if task["status"] in [TaskStatus.WORKING.value, TaskStatus.COMPLETE.value]:
            logger.info(f"タスク'{task_id}'は作業中または受入完了状態のため、作成をスキップします。 status={task['status']}")
            return 0

        old_account_id: Optional[str] = None
        changed_operator = False
        if self.is_force:
            if not can_put_annotation(task, self.service.api.account_id):
                logger.debug(f"タスク'{task_id}' の担当者を自分自身に変更します。")
                old_account_id = task["account_id"]
                task = self.service.wrapper.change_task_operator(
                    self.project_id,
                    task_id,
                    operator_account_id=self.service.api.account_id,
                    last_updated_datetime=task["updated_datetime"],
                )
                changed_operator = True

        else:  # noqa: PLR5501
            if not can_put_annotation(task, self.service.api.account_id):
                logger.debug(
                    f"タスク'{task_id}'は、過去に誰かに割り当てられたタスクで、現在の担当者が自分自身でないため、全体アノテーションの作成をスキップします。"
                    f"担当者を自分自身に変更して全体アノテーションを作成する場合は `--force` を指定してください。"
                )
                return 0

        # アノテーション仕様を取得
        annotation_specs_v3, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        annotation_specs_accessor = AnnotationSpecsAccessor(annotation_specs_v3)

        # タスクの入力データリストを取得
        input_data_list = self.service.wrapper.get_input_data_list(self.project_id, query_params={"task_id": task_id})

        created_count = 0
        for input_data in input_data_list:
            input_data_id = input_data["input_data_id"]

            # 既存のアノテーションを取得
            old_annotation, _ = self.service.api.get_editor_annotation(self.project_id, task_id, input_data_id, query_params={"v": "2"})

            # 既存のアノテーションIDを収集（重複チェック用）
            existing_annotation_ids = {detail["annotation_id"] for detail in old_annotation["details"]}

            # 新しいアノテーション詳細のリストを作成
            new_details = []
            for label_name in labels:
                try:
                    label_info = annotation_specs_accessor.get_label(label_name=label_name)
                except ValueError:
                    logger.warning(f"アノテーション仕様にラベル名(英語)が'{label_name}'であるラベル情報が存在しないか、または複数存在します。 :: task_id='{task_id}', input_data_id='{input_data_id}'")
                    continue

                # 全体アノテーション（Classification）かどうかチェック
                if label_info["annotation_type"] != DefaultAnnotationType.CLASSIFICATION.value:
                    logger.warning(f"ラベル'{label_name}'は全体アノテーション（Classification）ではありません。 :: task_id='{task_id}', input_data_id='{input_data_id}'")
                    continue

                # 全体アノテーションのannotation_idはlabel_idと同じ
                annotation_id = label_info["label_id"]

                # すでに同じannotation_idのアノテーションが存在するかチェック
                if annotation_id in existing_annotation_ids:
                    logger.debug(f"task_id='{task_id}', input_data_id='{input_data_id}', label_name='{label_name}' :: 既に全体アノテーションが存在するため、作成をスキップします。")
                    continue

                # 新しいアノテーション詳細を作成
                annotation_detail = {
                    "_type": "Create",
                    "label_id": label_info["label_id"],
                    "annotation_id": annotation_id,
                    "additional_data_list": [],
                    "editor_props": {},
                    "body": {
                        "_type": "Inner",
                        "data": {}
                    }
                }
                new_details.append(annotation_detail)

            # 新しいアノテーションがある場合のみ登録
            if len(new_details) > 0:
                # 既存のアノテーションを更新モードに変更
                for detail in old_annotation["details"]:
                    detail["_type"] = "Update"
                    detail["body"] = None

                # リクエストボディを作成
                request_body = {
                    "project_id": self.project_id,
                    "task_id": task_id,
                    "input_data_id": input_data_id,
                    "details": old_annotation["details"] + new_details,
                    "updated_datetime": old_annotation["updated_datetime"],
                    "format_version": "2.0.0",
                }

                # アノテーションを登録
                self.service.api.put_annotation(self.project_id, task_id, input_data_id, request_body=request_body, query_params={"v": "2"})
                created_count += len(new_details)
                logger.debug(f"task_id='{task_id}', input_data_id='{input_data_id}' :: {len(new_details)} 件の全体アノテーションを作成しました。")

        if changed_operator:
            logger.debug(f"タスク'{task_id}' の担当者を元に戻します。")
            self.service.wrapper.change_task_operator(
                self.project_id,
                task_id,
                operator_account_id=old_account_id,
                last_updated_datetime=task["updated_datetime"],
            )

        return created_count

    def execute_task(self, task_id: str, labels: list[str], task_index: Optional[int] = None) -> bool:
        """
        1個のタスクに対して全体アノテーションを作成する。

        Args:
            task_id: タスクID
            labels: ラベル名のリスト
            task_index: タスクのインデックス

        Returns:
            1個以上の全体アノテーションを作成したか
        """
        if not self.confirm_processing(f"task_id='{task_id}' に全体アノテーション（ラベル: {', '.join(labels)}）を作成しますか？"):
            return False

        logger_prefix = f"{task_index + 1!s} 件目: " if task_index is not None else ""
        logger.info(f"{logger_prefix}task_id='{task_id}' に対して処理します。")

        try:
            created_count = self.create_classification_annotation_for_task(task_id, labels)
            logger.info(f"{logger_prefix}task_id='{task_id}' :: {created_count} 件の全体アノテーションを作成しました。")
            return created_count > 0
        except Exception:
            logger.warning(f"task_id='{task_id}' の全体アノテーション作成に失敗しました。", exc_info=True)
            return False

    def main(self, task_ids: list[str], labels: list[str]) -> None:
        """
        メイン処理

        Args:
            task_ids: タスクIDのリスト
            labels: ラベル名のリスト
        """
        success_count = 0

        for task_index, task_id in enumerate(task_ids):
            result = self.execute_task(task_id, labels, task_index=task_index)
            if result:
                success_count += 1

        logger.info(f"{success_count} / {len(task_ids)} 件のタスクに対して全体アノテーションを作成しました。")


class CreateClassificationAnnotation(CommandLineWithConfirm):
    """
    全体アノテーション（Classification）を作成する
    """

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace) -> None:
        super().__init__(args.yes)
        self.service = service
        self.facade = facade
        self.args = args

    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli annotation create_classification: error:"  # noqa: N806

        if not args.task_id:
            print(f"{COMMON_MESSAGE} argument --task_id: タスクIDを指定してください。", file=sys.stderr)  # noqa: T201
            return False

        if not args.label:
            print(f"{COMMON_MESSAGE} argument --label: ラベル名を指定してください。", file=sys.stderr)  # noqa: T201
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id

        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        task_ids = annofabcli.common.cli.get_list_from_args(args.task_id)
        labels = annofabcli.common.cli.get_list_from_args(args.label)

        main_obj = CreateClassificationAnnotationMain(
            self.service,
            project_id=project_id,
            all_yes=self.all_yes,
            is_force=args.force,
        )

        main_obj.main(task_ids, labels)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CreateClassificationAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    argument_parser.add_task_id(required=True, help_message="対象のタスクIDを指定してください。")

    parser.add_argument(
        "--label",
        type=str,
        required=True,
        nargs="+",
        help="作成する全体アノテーションのラベル名（英語）を指定してください。",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="過去に割り当てられていて現在の担当者が自分自身でない場合、タスクの担当者を自分自身に変更してから全体アノテーションを作成します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "create_classification"
    subcommand_help = "全体アノテーション（Classification）を作成します。"
    description = "指定したラベルの全体アノテーション（Classification）を作成します。既に存在する全体アノテーションは作成されません。作業中/完了状態のタスクには作成できません。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
