from __future__ import annotations

import argparse
import logging
import multiprocessing
import sys
from typing import Any, Optional

import annofabapi
from annofabapi.models import DefaultAnnotationType, ProjectMemberRole, TaskStatus
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor
from annofabapi.utils import can_put_annotation

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
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
        is_change_operator_to_me: bool,
        include_completed: bool,
    ) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)
        CommandLineWithConfirm.__init__(self, all_yes)

        self.project_id = project_id
        self.is_change_operator_to_me = is_change_operator_to_me
        self.include_completed = include_completed

        # アノテーション仕様を取得
        annotation_specs_v3, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        self.annotation_specs_accessor = AnnotationSpecsAccessor(annotation_specs_v3)

        my_member, _ = self.service.api.get_my_member_in_project(project_id)
        self.my_project_member_role = ProjectMemberRole(my_member["member_role"])

    def _validate_and_prepare_task(self, task_id: str) -> tuple[Optional[dict[str, Any]], bool, Optional[str]]:
        """
        タスクの検証と準備を行う

        Returns:
            tuple[0]: タスク情報（Noneの場合は処理をスキップ）
            tuple[1]: 担当者を変更したかどうか
            tuple[2]: 元の担当者ID（担当者を変更した場合）
        """
        # タスク情報を取得
        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"task_id='{task_id}'であるタスクは存在しません。")
            return None, False, None

        if task["status"] == TaskStatus.WORKING.value:
            logger.info(f"タスク'{task_id}'は作業中状態のため、全体アノテーションの作成をスキップします。")
            return None, False, None

        if not self.include_completed:  # noqa: SIM102
            if task["status"] == TaskStatus.COMPLETE.value:
                logger.info(
                    f"タスク'{task_id}'は完了状態のため、全体アノテーションの作成をスキップします。完了状態のタスクに全体アノテーションを作成するには、 ``--include_completed`` を指定してください。"
                )
                return None, False, None

        old_account_id: Optional[str] = None
        changed_operator = False

        if self.is_change_operator_to_me:
            if not can_put_annotation(task, self.service.api.account_id, project_member_role=self.my_project_member_role):
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
            if not can_put_annotation(task, self.service.api.account_id, project_member_role=self.my_project_member_role):
                logger.debug(
                    f"タスク'{task_id}'は、過去に誰かに割り当てられたタスクで、現在の担当者が自分自身でないため、全体アノテーションの作成をスキップします。"
                    f"担当者を自分自身に変更して全体アノテーションを作成する場合は `--change_task_operator_to_me` を指定してください。"
                )
                return None, False, None

        return task, changed_operator, old_account_id

    def _create_annotation_details_for_labels(
        self, task_id: str, input_data_id: str, labels: list[str], annotation_specs_accessor: AnnotationSpecsAccessor, existing_annotation_ids: set[str]
    ) -> list[dict[str, Any]]:
        """
        ラベルリストから新しいアノテーション詳細を作成する
        """
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
                logger.debug(
                    f"task_id='{task_id}', input_data_id='{input_data_id}', label_name='{label_name}' :: "
                    f"既に全体アノテーションが存在するため、label_name='{label_name}'の全体アノテーションの作成をスキップします。"
                )
                continue

            # 新しいアノテーション詳細を作成
            annotation_detail = {
                "_type": "Create",
                "label_id": label_info["label_id"],
                "annotation_id": annotation_id,
                "additional_data_list": [],
                "editor_props": {},
                "body": {"_type": "Inner", "data": {"_type": "Classification"}},
            }
            new_details.append(annotation_detail)

        return new_details

    def _put_annotations_for_input_data(self, task_id: str, input_data_id: str, new_details: list[dict[str, Any]], old_annotation: dict[str, Any]) -> int:
        """
        入力データに対してアノテーションを登録する
        """
        if len(new_details) == 0:
            return 0

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
        logger.debug(f"task_id='{task_id}', input_data_id='{input_data_id}' :: {len(new_details)} 件の全体アノテーションを作成しました。")
        return len(new_details)

    def create_classification_annotation_for_task(self, task_id: str, labels: list[str]) -> int:
        """
        1個のタスクに対して全体アノテーションを作成します。

        Args:
            task_id: タスクID
            labels: ラベル名のリスト

        Returns:
            作成した全体アノテーションの個数
        """
        # タスクの検証と準備
        task, changed_operator, old_account_id = self._validate_and_prepare_task(task_id)
        if task is None:
            return 0

        # タスクの入力データリストを取得
        input_data_id_list = task["input_data_id_list"]

        created_count = 0
        try:
            for input_data_id in input_data_id_list:
                # 既存のアノテーションを取得
                old_annotation, _ = self.service.api.get_editor_annotation(self.project_id, task_id, input_data_id, query_params={"v": "2"})

                # 既存のアノテーションIDを収集（重複チェック用）
                existing_annotation_ids = {detail["annotation_id"] for detail in old_annotation["details"]}

                # 新しいアノテーション詳細のリストを作成
                new_details = self._create_annotation_details_for_labels(task_id, input_data_id, labels, self.annotation_specs_accessor, existing_annotation_ids)

                # アノテーションを登録
                created_count += self._put_annotations_for_input_data(task_id, input_data_id, new_details, old_annotation)
        finally:
            # 担当者を元に戻す
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
        if not self.confirm_processing(f"task_id='{task_id}' に全体アノテーション（label_name={labels}）を作成しますか？"):
            return False

        logger_prefix = f"{task_index + 1!s} 件目 :: " if task_index is not None else ""
        logger.info(f"{logger_prefix}task_id='{task_id}' に対して処理します。")

        try:
            created_count = self.create_classification_annotation_for_task(task_id, labels)
            logger.info(f"{logger_prefix}task_id='{task_id}' :: {created_count} 件の全体アノテーションを作成しました。")
        except Exception:
            logger.warning(f"task_id='{task_id}' の全体アノテーション作成に失敗しました。", exc_info=True)
            return False
        else:
            return created_count > 0

    def execute_task_wrapper(
        self,
        tpl: tuple[int, str, list[str]],
    ) -> bool:
        task_index, task_id, labels = tpl
        try:
            logger_prefix = f"{task_index + 1!s} 件目 :: "
            logger.info(f"{logger_prefix}task_id='{task_id}' に対して処理します。")

            created_count = self.create_classification_annotation_for_task(task_id, labels)
            logger.info(f"{logger_prefix}task_id='{task_id}' :: {created_count} 件の全体アノテーションを作成しました。")
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"task_id='{task_id}' の全体アノテーション作成に失敗しました。", exc_info=True)
            return False
        else:
            return created_count > 0

    def main(self, task_ids: list[str], labels: list[str], parallelism: Optional[int] = None) -> None:
        """
        メイン処理

        Args:
            task_ids: タスクIDのリスト
            labels: ラベル名のリスト
            parallelism: 並列度
        """
        success_count = 0

        if parallelism is not None:
            with multiprocessing.Pool(parallelism) as pool:
                task_args = [(task_index, task_id, labels) for task_index, task_id in enumerate(task_ids)]
                result_bool_list = pool.map(self.execute_task_wrapper, task_args)
                success_count = len([e for e in result_bool_list if e])
        else:
            for task_index, task_id in enumerate(task_ids):
                result = self.execute_task(task_id, labels, task_index=task_index)
                if result:
                    success_count += 1

        logger.info(f"{success_count} / {len(task_ids)} 件のタスクに対して全体アノテーションを作成しました。")


class CreateClassificationAnnotation(CommandLine):
    """
    全体アノテーション（Classification）を作成する
    """

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace) -> None:
        super().__init__(service, facade, args)
        self.args = args

    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli annotation create_classification: error:"  # noqa: N806

        if not args.task_id:
            print(f"{COMMON_MESSAGE} argument --task_id: タスクIDを指定してください。", file=sys.stderr)  # noqa: T201
            return False

        if not args.label_name:
            print(f"{COMMON_MESSAGE} argument --label_name: ラベル名を指定してください。", file=sys.stderr)  # noqa: T201
            return False

        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、'--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id

        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])

        if args.include_completed:  # noqa: SIM102
            if not self.facade.contains_any_project_member_role(project_id, [ProjectMemberRole.OWNER]):
                print(  # noqa: T201
                    "annofabcli annotation create_classification: error: argument --include_completed : "
                    "'--include_completed' 引数を利用するにはプロジェクトのオーナーロールを持つユーザーで実行する必要があります。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        task_ids = annofabcli.common.cli.get_list_from_args(args.task_id)
        labels = annofabcli.common.cli.get_list_from_args(args.label_name)

        main_obj = CreateClassificationAnnotationMain(
            self.service,
            project_id=project_id,
            all_yes=self.all_yes,
            is_change_operator_to_me=args.change_operator_to_me,
            include_completed=args.include_completed,
        )

        main_obj.main(task_ids, labels, parallelism=args.parallelism)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CreateClassificationAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    argument_parser.add_task_id(
        required=True, help_message=("全体アノテーションの作成先であるタスクのtask_idを指定します。 ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。")
    )

    parser.add_argument(
        "--label_name",
        type=str,
        required=True,
        nargs="+",
        help="作成する全体アノテーションのラベル名（英語）を指定します。",
    )

    parser.add_argument(
        "--change_operator_to_me",
        action="store_true",
        help="タスクの担当者を自分自身にしないとアノテーションを作成できない場合（過去に担当者が割り当てられていて現在の担当者が自分自身でない場合）、タスクの担当者を自分自身に変更してから全体アノテーションを作成します。アノテーションの作成が完了したら、タスクの担当者を元に戻します。",
    )

    parser.add_argument(
        "--include_completed",
        action="store_true",
        help="完了状態のタスクにも全体アノテーションを作成します。ただし、オーナーロールを持つユーザーでしか実行できません。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="並列度。指定しない場合は、逐次的に処理します。``--parallelism`` を指定した場合は、``--yes`` も指定してください。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "create_classification"
    subcommand_help = "全体アノテーション（Classification）を作成します。"
    description = (
        "指定したラベルの全体アノテーション（Classification）を作成します。"
        "既に全体アノテーションが存在する場合はスキップします。"
        "作業中状態のタスクには作成できません。"
        "完了状態のタスクには、デフォルトでは作成できません。"
    )
    epilog = "オーナロールまたはチェッカーロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
