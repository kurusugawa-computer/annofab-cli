from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional, Union

import annofabapi
import pandas
from annofabapi.models import ProjectMemberRole
from annofabapi.pydantic_models.task_status import TaskStatus
from pydantic import BaseModel

import annofabcli
from annofabcli.annotation.annotation_query import convert_attributes_from_cli_to_additional_data_list_v2
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


Attributes = dict[str, Optional[Union[str, int, bool]]]
"""属性情報"""


class TargetAnnotation(BaseModel):
    task_id: str
    input_data_id: str
    annotation_id: str
    attributes: Attributes


def get_annotation_list_per_task_id_input_data_id(anno_list: list[TargetAnnotation]) -> dict[str, dict[str, list[TargetAnnotation]]]:
    """
    タスクIDと入力データIDごとにアノテーションをグループ化する。

    Args:
        anno_list: アノテーションのリスト

    Returns:
        タスクIDと入力データIDをキーとしたアノテーションの辞書
    """
    grouped: dict[str, dict[str, list[TargetAnnotation]]] = defaultdict(lambda: defaultdict(list))

    for annotation in anno_list:
        grouped[annotation.task_id][annotation.input_data_id].append(annotation)
    return grouped


class ChangeAnnotationAttributesPerAnnotationMain(CommandLineWithConfirm):
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        project_id: str,
        is_force: bool,
        all_yes: bool,
        backup_dir: Optional[Path] = None,
    ) -> None:
        self.service = service
        self.project_id = project_id
        self.is_force = is_force
        self.backup_dir = backup_dir
        self.annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params={"v": "3"})
        self.dump_annotation_obj = DumpAnnotationMain(service, project_id)
        super().__init__(all_yes)

    def change_annotation_attributes_by_frame(self, task_id: str, input_data_id: str, anno_list: list[TargetAnnotation]) -> bool:
        """
        フレームごとにアノテーション属性値を変更する。

        Args:
            task_id: タスクID
            input_data_id: 入力データID
            additional_data_list: 変更後の属性値(`AdditionalDataListV2`スキーマ)

        """
        editor_annotation, _ = self.service.api.get_editor_annotation(self.project_id, task_id=task_id, input_data_id=input_data_id, query_params={"v": "2"})

        if self.backup_dir is not None:
            (self.backup_dir / task_id).mkdir(exist_ok=True, parents=True)
            self.dump_annotation_obj.dump_editor_annotation(editor_annotation, json_path=self.backup_dir / task_id / f"{input_data_id}.json")

        details_map = {detail["annotation_id"]: detail for detail in editor_annotation["details"]}

        def _to_request_body_elm(anno: TargetAnnotation) -> dict[str, Any]:
            additional_data_list = convert_attributes_from_cli_to_additional_data_list_v2(anno.attributes, annotation_specs=self.annotation_specs)
            return {
                "data": {
                    "project_id": editor_annotation["project_id"],
                    "task_id": editor_annotation["task_id"],
                    "input_data_id": editor_annotation["input_data_id"],
                    "updated_datetime": editor_annotation["updated_datetime"],
                    "annotation_id": anno.annotation_id,
                    "label_id": details_map[anno.annotation_id]["label_id"],
                    "additional_data_list": additional_data_list,
                },
                "_type": "PutV2",
            }

        request_body = [_to_request_body_elm(annotation) for annotation in anno_list]

        self.service.api.batch_update_annotations(self.project_id, request_body=request_body)
        logger.debug(f"task_id='{task_id}', input_data_id='{input_data_id}' :: {len(request_body)}件の属性値を変更しました。")
        return True

    def change_annotation_attributes_for_task(self, task_id: str, annotation_list_per_input_data_id: dict[str, list[TargetAnnotation]]) -> tuple[bool, int, int]:
        """
        1個のタスクに含まれるアノテーションの属性値を変更する。

        Args:
            task_id: タスクID
            annotation_list_per_input_data_id: 入力データIDごとのアノテーションリスト

        Returns:
            tuple:
                [0]: 属性値の変更可能なタスクかどうか
                [1]: 属性値の変更に成功したアノテーション数
                [2]: 属性値を変更できなかったアノテーション数

        """
        annotation_count = sum(len(v) for v in annotation_list_per_input_data_id.values())
        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)

        succeed_to_change_annotation_count = 0
        failed_to_change_annotation_count = 0

        if task is None:
            logger.warning(f"task_id='{task_id}' :: タスクが存在しないため、{annotation_count} 件のアノテーションの属性値の変更をスキップします。")
            return False, 0, annotation_count

        if task["status"] == TaskStatus.WORKING.value:
            logger.info(f"task_id='{task_id}' :: タスクが作業中状態のため、{annotation_count} 件のアノテーションの属性値の変更をスキップします。")
            failed_to_change_annotation_count += annotation_count
            return False, 0, annotation_count

        if not self.is_force:  # noqa: SIM102
            if task["status"] == TaskStatus.COMPLETE.value:
                logger.info(
                    f"task_id='{task_id}' :: タスクが完了状態のため、アノテーション {annotation_count} 件のアノテーションの属性値の変更をスキップします。"
                    f"完了状態のタスクのアノテーションを削除するには、`--force`オプションを指定してください。"
                )
                failed_to_change_annotation_count += annotation_count
                return False, 0, annotation_count

        if not self.confirm_processing(f"task_id='{task_id}'に含まれるアノテーション{annotation_count}件の属性値を変更しますか？"):
            return False, 0, annotation_count

        for input_data_id, sub_anno_list in annotation_list_per_input_data_id.items():
            try:
                if self.change_annotation_attributes_by_frame(task_id, input_data_id, sub_anno_list):
                    succeed_to_change_annotation_count += len(sub_anno_list)
                else:
                    failed_to_change_annotation_count += len(sub_anno_list)
            except Exception:
                logger.warning(f"task_id='{task_id}', input_data_id='{input_data_id}' :: アノテーションの属性値変更に失敗しました。", exc_info=True)
                failed_to_change_annotation_count += len(sub_anno_list)
                continue

        return True, succeed_to_change_annotation_count, failed_to_change_annotation_count

    def change_annotation_attributes(self, anno_list: list[TargetAnnotation]) -> None:
        """
        アノテーションごとに属性値を変更する。

        Args:
            anno_list: 各アノテーションの変更内容リスト
        """
        changed_task_count = 0
        total_failed_to_change_annotation_count = 0
        total_succeed_to_change_annotation_count = 0
        annotation_list_per_task_id_input_data_id = get_annotation_list_per_task_id_input_data_id(anno_list)

        total_task_count = len(annotation_list_per_task_id_input_data_id)
        total_annotation_count = len(anno_list)

        for task_id, input_data_dict in annotation_list_per_task_id_input_data_id.items():
            is_changeable_task, succeed_to_change_annotation_count, failed_to_change_annotation_count = self.change_annotation_attributes_for_task(task_id, input_data_dict)
            total_succeed_to_change_annotation_count += succeed_to_change_annotation_count
            total_failed_to_change_annotation_count += failed_to_change_annotation_count

            if is_changeable_task:
                changed_task_count += 1

        logger.info(
            f"{total_succeed_to_change_annotation_count}/{total_annotation_count} 件のアノテーションの属性値を変更しました。 :: "
            f"アノテーションが変更されたタスク数は {changed_task_count}/{total_task_count} 件です。"
            f"{total_failed_to_change_annotation_count} 件のアノテーションは変更できませんでした。"
        )


class ChangeAttributesPerAnnotation(CommandLine):
    """
    アノテーションごとに属性値を個別変更
    """

    COMMON_MESSAGE = "annofabcli annotation change_attributes_per_annotation: error:"

    def main(self) -> None:
        args = self.args

        if args.json is not None:
            annotation_items = get_json_from_args(args.json)
            if not isinstance(annotation_items, list):
                print(f"{self.COMMON_MESSAGE} argument --json: JSON形式が不正です。オブジェクトの配列を指定してください。", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

            target_annotation_list = [TargetAnnotation.model_validate(anno) for anno in annotation_items]

        elif args.csv is not None:
            df_input = pandas.read_csv(args.csv)
            target_annotation_list = [
                TargetAnnotation(task_id=e["task_id"], input_data_id=e["input_data_id"], annotation_id=e["annotation_id"], attributes=json.loads(e["attributes"]))
                for e in df_input.to_dict(orient="records")
            ]
        else:
            print(f"{self.COMMON_MESSAGE} argument '--json' または '--csv' のいずれかを指定してください。", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id

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

        # プロジェクト権限チェック
        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])

        main_obj = ChangeAnnotationAttributesPerAnnotationMain(self.service, project_id=project_id, all_yes=args.yes, is_force=args.force, backup_dir=backup_dir)
        main_obj.change_annotation_attributes(target_annotation_list)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeAttributesPerAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    sample_json_obj = [{"task_id": "t1", "input_data_id": "i1", "annotation_id": "a1", "attributes": {"occluded": True}}]
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--json",
        type=str,
        help="各アノテーションごとに変更内容を記載したJSONリストを指定します。 ``file://`` を先頭に付けるとJSON形式のファイルを指定できます。\n"
        f"(例) '{json.dumps(sample_json_obj, ensure_ascii=False)}'",
    )
    input_group.add_argument(
        "--csv",
        type=str,
        help="各アノテーションごとに変更内容を記載したCSVファイルを指定します。 \n"
        "* `task_id`, `input_data_id`, `annotation_id`, `attributes` の4つのカラムが必要です。\n"
        f"`attributes` カラムには、属性名と値を '{json.dumps({'occluded': True})}' のようにJSON形式で指定します。\n",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="指定した場合は、完了状態のタスクのアノテーションも属性値を変更します。ただし、完了状態のタスクのアノテーションを変更するには、オーナーロールを持つユーザーが実行する必要があります。",
    )

    parser.add_argument(
        "--backup",
        type=Path,
        required=False,
        help="アノテーションのバックアップを保存するディレクトリのパス。アノテーションの復元は ``annotation restore`` コマンドで実現できます。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "change_attributes_per_annotation"
    subcommand_help = "各アノテーションの属性値を変更します。"
    epilog = "オーナロールまたはチェッカーロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
