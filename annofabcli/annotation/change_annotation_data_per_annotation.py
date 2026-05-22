from __future__ import annotations

import argparse
import copy
import json
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import annofabapi
import pandas
from annofabapi.models import ProjectMemberRole
from annofabapi.pydantic_models.task_status import TaskStatus
from pydantic import BaseModel

import annofabcli.common.cli
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


UNSUPPORTED_DATA_TYPES = {"Segmentation", "SegmentationV2", "Outer"}
"""このコマンドで変更できないアノテーションデータの種類。"""


class TargetAnnotationData(BaseModel):
    """変更対象アノテーションと変更後のdata。"""

    task_id: str
    input_data_id: str
    annotation_id: str
    data: dict[str, Any]


@dataclass(frozen=True)
class ChangeAnnotationDataCount:
    """アノテーションdata変更件数。"""

    success: int
    """変更に成功したアノテーション数。"""

    failed: int
    """変更に失敗またはスキップしたアノテーション数。"""


@dataclass(frozen=True)
class ChangeAnnotationDataRequest:
    """アノテーションdata変更用のリクエスト情報。"""

    request_body: dict[str, Any]
    """`put_annotation` APIに渡すリクエストボディ。"""

    count: ChangeAnnotationDataCount
    """アノテーションdata変更件数。"""


def get_annotation_data_list_per_task_id_input_data_id(anno_list: list[TargetAnnotationData]) -> dict[str, dict[str, list[TargetAnnotationData]]]:
    """タスクIDと入力データIDごとにアノテーションをグループ化する。

    Args:
        anno_list: アノテーションdata変更内容のリスト

    Returns:
        タスクIDと入力データIDをキーとしたアノテーションの辞書
    """
    grouped: dict[str, dict[str, list[TargetAnnotationData]]] = defaultdict(lambda: defaultdict(list))

    for annotation in anno_list:
        grouped[annotation.task_id][annotation.input_data_id].append(annotation)
    return grouped


def create_request_body_for_change_data(editor_annotation: dict[str, Any], anno_list: list[TargetAnnotationData]) -> ChangeAnnotationDataRequest:
    """`put_annotation` に渡すリクエストボディを作成する。

    Args:
        editor_annotation: `get_editor_annotation` のレスポンス
        anno_list: アノテーションdata変更内容のリスト

    Returns:
        リクエスト情報
    """
    details_map = {detail["annotation_id"]: detail for detail in editor_annotation["details"]}

    data_by_annotation_id: dict[str, dict[str, Any]] = {}
    failed_count = 0
    for anno in anno_list:
        if anno.annotation_id not in details_map:
            logger.warning(
                f"task_id='{anno.task_id}', input_data_id='{anno.input_data_id}' :: "
                f"annotation_id='{anno.annotation_id}'であるアノテーションが存在しないため、このアノテーションのdataの変更をスキップします。"
            )
            failed_count += 1
            continue

        detail = details_map[anno.annotation_id]
        if detail["body"]["_type"] == "Outer":
            logger.warning(
                f"task_id='{anno.task_id}', input_data_id='{anno.input_data_id}', annotation_id='{anno.annotation_id}' :: "
                "外部ファイルが必要なアノテーションのため、このアノテーションのdataの変更をスキップします。"
            )
            failed_count += 1
            continue

        src_data_type = detail["body"]["data"]["_type"]
        dest_data_type = anno.data["_type"]
        if src_data_type != dest_data_type:
            logger.warning(
                f"task_id='{anno.task_id}', input_data_id='{anno.input_data_id}', annotation_id='{anno.annotation_id}' :: "
                f"既存アノテーションのdata._type='{src_data_type}' と変更後のdata._type='{dest_data_type}' が異なるため、このアノテーションのdataの変更をスキップします。"
            )
            failed_count += 1
            continue

        data_by_annotation_id[anno.annotation_id] = anno.data

    request_details: list[dict[str, Any]] = []
    for detail in editor_annotation["details"]:
        new_detail = copy.deepcopy(detail)
        new_detail["_type"] = "Update"
        if detail["annotation_id"] in data_by_annotation_id:
            new_detail["body"] = {"_type": "Inner", "data": data_by_annotation_id[detail["annotation_id"]]}
        else:
            # 既存アノテーションは変更しない。`body=None` を指定すると、putAnnotationでbodyが維持される。
            new_detail["body"] = None

        request_details.append(new_detail)

    request_body = {
        "project_id": editor_annotation["project_id"],
        "task_id": editor_annotation["task_id"],
        "input_data_id": editor_annotation["input_data_id"],
        "details": request_details,
        "updated_datetime": editor_annotation["updated_datetime"],
        "format_version": "2.0.0",
    }

    return ChangeAnnotationDataRequest(
        request_body=request_body,
        count=ChangeAnnotationDataCount(success=len(data_by_annotation_id), failed=failed_count),
    )


class ChangeAnnotationDataPerAnnotationMain(CommandLineWithConfirm):
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        project_id: str,
        include_complete_task: bool,
        include_on_hold_task: bool,
        all_yes: bool,
        backup_dir: Path | None = None,
    ) -> None:
        self.service = service
        self.project_id = project_id
        self.include_complete_task = include_complete_task
        self.include_on_hold_task = include_on_hold_task
        self.backup_dir = backup_dir
        self.dump_annotation_obj = DumpAnnotationMain(service, project_id)
        super().__init__(all_yes)

    def change_annotation_data_by_frame(self, task_id: str, input_data_id: str, anno_list: list[TargetAnnotationData]) -> ChangeAnnotationDataCount:
        """フレームごとにアノテーションdataを変更する。"""
        editor_annotation, _ = self.service.api.get_editor_annotation(self.project_id, task_id=task_id, input_data_id=input_data_id, query_params={"v": "2"})

        if self.backup_dir is not None:
            (self.backup_dir / task_id).mkdir(exist_ok=True, parents=True)
            self.dump_annotation_obj.dump_editor_annotation(editor_annotation, json_path=self.backup_dir / task_id / f"{input_data_id}.json")

        request = create_request_body_for_change_data(editor_annotation, anno_list)

        if request.count.success > 0:
            self.service.api.put_annotation(self.project_id, task_id, input_data_id, request_body=request.request_body, query_params={"v": "2"})
        else:
            logger.debug(f"task_id='{task_id}', input_data_id='{input_data_id}' :: 変更対象のアノテーションがありませんでした。")

        logger.debug(
            f"task_id='{task_id}', input_data_id='{input_data_id}' :: {request.count.success}/{len(anno_list)}件のdataを変更しました。{request.count.failed}件のアノテーションは変更できませんでした。"
        )
        return request.count

    def change_annotation_data_for_task(self, task_id: str, annotation_list_per_input_data_id: dict[str, list[TargetAnnotationData]]) -> tuple[bool, ChangeAnnotationDataCount]:
        """1個のタスクに含まれるアノテーションdataを変更する。"""
        annotation_count = sum(len(v) for v in annotation_list_per_input_data_id.values())
        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)

        if task is None:
            logger.warning(f"task_id='{task_id}' :: タスクが存在しないため、{annotation_count} 件のアノテーションのdata変更をスキップします。")
            return False, ChangeAnnotationDataCount(success=0, failed=annotation_count)

        if task["status"] == TaskStatus.WORKING.value:
            logger.info(f"task_id='{task_id}' :: タスクが作業中状態のため、{annotation_count} 件のアノテーションのdata変更をスキップします。")
            return False, ChangeAnnotationDataCount(success=0, failed=annotation_count)

        if not self.include_on_hold_task and task["status"] == TaskStatus.ON_HOLD.value:
            logger.info(
                f"task_id='{task_id}' :: タスクが保留中状態のため、{annotation_count} 件のアノテーションのdata変更をスキップします。"
                "保留中状態のタスクのアノテーションも変更するには、`--include_on_hold_task` オプションを指定してください。"
            )
            return False, ChangeAnnotationDataCount(success=0, failed=annotation_count)

        if not self.include_complete_task:  # noqa: SIM102
            if task["status"] == TaskStatus.COMPLETE.value:
                logger.info(
                    f"task_id='{task_id}' :: タスクが完了状態のため、{annotation_count} 件のアノテーションのdata変更をスキップします。"
                    "完了状態のタスクのアノテーションも変更するには、`--include_complete_task` オプションを指定してください。"
                )
                return False, ChangeAnnotationDataCount(success=0, failed=annotation_count)

        if not self.confirm_processing(f"task_id='{task_id}'に含まれるアノテーション{annotation_count}件のdataを変更しますか？"):
            return False, ChangeAnnotationDataCount(success=0, failed=annotation_count)

        success_count = 0
        failed_count = 0
        for input_data_id, sub_anno_list in annotation_list_per_input_data_id.items():
            try:
                count = self.change_annotation_data_by_frame(task_id, input_data_id, sub_anno_list)
                success_count += count.success
                failed_count += count.failed
            except Exception:
                logger.warning(f"task_id='{task_id}', input_data_id='{input_data_id}' :: アノテーションのdata変更に失敗しました。", exc_info=True)
                failed_count += len(sub_anno_list)
                continue

        return True, ChangeAnnotationDataCount(success=success_count, failed=failed_count)

    def change_annotation_data(self, anno_list: list[TargetAnnotationData]) -> None:
        """アノテーションごとにdataを変更する。"""
        changed_task_count = 0
        total_failed_count = 0
        total_success_count = 0
        annotation_list_per_task_id_input_data_id = get_annotation_data_list_per_task_id_input_data_id(anno_list)

        total_task_count = len(annotation_list_per_task_id_input_data_id)
        total_annotation_count = len(anno_list)

        for task_id, input_data_dict in annotation_list_per_task_id_input_data_id.items():
            is_changeable_task, count = self.change_annotation_data_for_task(task_id, input_data_dict)
            total_success_count += count.success
            total_failed_count += count.failed

            if is_changeable_task:
                changed_task_count += 1

        logger.info(
            f"{total_success_count}/{total_annotation_count} 件のアノテーションのdataを変更しました。 :: "
            f"アノテーションが変更されたタスク数は {changed_task_count}/{total_task_count} 件です。"
            f"{total_failed_count} 件のアノテーションは変更できませんでした。"
        )


class ChangeDataPerAnnotation(CommandLine):
    """アノテーションごとにdataを個別変更。"""

    COMMON_MESSAGE = "annofabcli annotation change_data_per_annotation: error:"

    def main(self) -> None:
        args = self.args

        if args.json is not None:
            annotation_items = get_json_from_args(args.json)
            if not isinstance(annotation_items, list):
                print(f"{self.COMMON_MESSAGE} argument --json: JSON形式が不正です。オブジェクトの配列を指定してください。", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

            target_annotation_list = [TargetAnnotationData.model_validate(anno) for anno in annotation_items]

        elif args.csv is not None:
            df_input = pandas.read_csv(args.csv, dtype={"task_id": "string", "input_data_id": "string", "annotation_id": "string", "data": "string"})
            target_annotation_list = [
                TargetAnnotationData(task_id=e["task_id"], input_data_id=e["input_data_id"], annotation_id=e["annotation_id"], data=json.loads(e["data"])) for e in df_input.to_dict(orient="records")
            ]
        else:
            print(f"{self.COMMON_MESSAGE} argument '--json' または '--csv' のいずれかを指定してください。", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id

        if args.backup is None:
            print(  # noqa: T201
                "間違えてアノテーションを変更してしまったときに復元できるようにするため、'--backup'でバックアップ用のディレクトリを指定することを推奨します。",
                file=sys.stderr,
            )
            if not self.confirm_processing("復元用のバックアップディレクトリが指定されていません。処理を続行しますか？"):
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            backup_dir = None
        else:
            backup_dir = Path(args.backup)

        if args.include_complete_task:  # noqa: SIM102
            if not self.facade.contains_any_project_member_role(project_id, [ProjectMemberRole.OWNER]):
                print(  # noqa: T201
                    f"{self.COMMON_MESSAGE} argument --include_complete_task : '--include_complete_task' 引数を利用するにはプロジェクトのオーナーロールを持つユーザーで実行する必要があります。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])

        main_obj = ChangeAnnotationDataPerAnnotationMain(
            self.service,
            project_id=project_id,
            all_yes=args.yes,
            include_complete_task=args.include_complete_task,
            include_on_hold_task=args.include_on_hold_task,
            backup_dir=backup_dir,
        )
        main_obj.change_annotation_data(target_annotation_list)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeDataPerAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    sample_json_obj = [
        {
            "task_id": "t1",
            "input_data_id": "i1",
            "annotation_id": "a1",
            "data": {"_type": "Range", "begin": 1000, "end": 5000},
        }
    ]
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
        "* `task_id`, `input_data_id`, `annotation_id`, `data` の4つのカラムが必要です。\n"
        f"`data` カラムには、変更後のアノテーションdataを '{json.dumps({'_type': 'Range', 'begin': 1000, 'end': 5000})}' のようにJSON形式で指定します。\n",
    )

    parser.add_argument(
        "--include_complete_task",
        action="store_true",
        help="指定した場合は、完了状態のタスクのアノテーションもdataを変更します。ただし、完了状態のタスクのアノテーションを変更するには、オーナーロールを持つユーザーが実行する必要があります。",
    )
    parser.add_argument(
        "--include_on_hold_task",
        action="store_true",
        help="指定した場合は、保留中状態のタスクのアノテーションもdataを変更します。指定しない場合、保留中状態のタスクはスキップされます。",
    )

    parser.add_argument(
        "--backup",
        type=Path,
        required=False,
        help="アノテーションのバックアップを保存するディレクトリのパス。アノテーションの復元は ``annotation restore`` コマンドで実現できます。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "change_data_per_annotation"
    subcommand_help = "各アノテーションの座標情報・形状情報を変更します。"
    epilog = "オーナロールまたはチェッカーロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
