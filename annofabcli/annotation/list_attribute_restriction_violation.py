from __future__ import annotations

import argparse
import json
import logging
from typing import Any

import annofabapi
from annofabapi.util.attribute_restriction_validation import AttributeRestrictionValidator
from annofabapi.util.attribute_restrictions import Restriction
from annofabapi.util.page import create_3dpc_editor_url, create_image_editor_url, create_video_editor_url

import annofabcli.common.cli
from annofabcli.common.annofab.annotation_editor_url import create_annotation_editor_url, get_annotation_editor_type_from_input_data_type
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login, get_list_from_args
from annofabcli.common.enums import OutputFormat
from annofabcli.common.exceptions import AnnofabCliException
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)

COLUMNS = (
    "project_id",
    "task_id",
    "input_data_id",
    "annotation_id",
    "label_name_en",
    "attribute_id",
    "attribute_name_en",
    "attribute_value",
    "restriction_index",
    "restriction_type",
    "restriction_text",
    "restriction",
    "annotation_editor_url",
)
"""違反一覧の出力列。"""


class ListAttributeRestrictionViolationMain:
    """APIから取得したアノテーションを入力データ単位で検証する。"""

    def __init__(self, service: annofabapi.Resource, project_id: str) -> None:
        self.service = service
        self.project_id = project_id
        self.specs, _ = service.api.get_annotation_specs(project_id, query_params={"v": "3"})
        self.validator = AttributeRestrictionValidator(self.specs)
        project, _ = service.api.get_project(project_id)
        self.editor_type = get_annotation_editor_type_from_input_data_type(project["input_data_type"])

    def validate_input_data(self, task_id: str, input_data_id: str) -> list[dict[str, Any]]:
        """同一入力データの全アノテーションから違反一覧を生成する。

        Args:
            task_id: タスクID。
            input_data_id: 入力データID。

        Returns:
            アノテーションと違反した制約の組ごとの出力行。
        """
        annotation, _ = self.service.api.get_annotation(self.project_id, task_id, input_data_id)
        violations = self.validator.validate_simple_annotation_details(annotation["details"])
        details = {detail["annotation_id"]: detail for detail in annotation["details"]}
        rows = []
        for violation in violations:
            detail = details[violation.annotation_id]
            restriction = self.specs["restrictions"][violation.restriction_index]
            # 分類アノテーションのdataはnullなので、エディタの種類からURLを生成する。
            if detail["data"] is None:
                if self.editor_type == "video":
                    url = create_video_editor_url(self.project_id, task_id, annotation_id=violation.annotation_id)
                else:
                    create_url = create_image_editor_url if self.editor_type == "image" else create_3dpc_editor_url
                    url = create_url(self.project_id, task_id, input_data_id=input_data_id, annotation_id=violation.annotation_id)
            else:
                url = create_annotation_editor_url(annotation, detail, self.editor_type)
            rows.append(
                {
                    "project_id": self.project_id,
                    "task_id": task_id,
                    "input_data_id": input_data_id,
                    "annotation_id": violation.annotation_id,
                    "label_name_en": detail["label"],
                    "attribute_id": violation.attribute_id,
                    "attribute_name_en": violation.attribute_name,
                    "attribute_value": detail["attributes"].get(violation.attribute_name),
                    "restriction_index": violation.restriction_index,
                    "restriction_type": restriction["condition"]["_type"],
                    "restriction_text": Restriction.from_dict(restriction).to_human_readable(self.specs),
                    "restriction": restriction,
                    "annotation_editor_url": url,
                }
            )
        return rows

    def get_all_task_ids(self) -> list[str]:
        """全タスクのIDをページ単位で取得する。

        Args:
            なし。

        Returns:
            全タスクID。取得上限を超えた場合は例外を送出する。
        """
        result: list[str] = []
        page = 1
        while True:
            content, _ = self.service.api.get_tasks(self.project_id, query_params={"page": page, "limit": 200})
            if content["over_limit"]:
                raise AnnofabCliException("全タスクを取得できません。--task_idで対象を絞り込んでください。")
            result.extend(task["task_id"] for task in content["list"])
            if content["page_no"] >= content["total_page_no"]:
                return result
            page = content["page_no"] + 1

    def collect(self, task_ids: list[str]) -> tuple[list[dict[str, Any]], int]:
        """取得・検証に失敗しても残りの入力データを処理する。

        Args:
            task_ids: 対象タスクID一覧。

        Returns:
            成功した入力データの違反一覧と、取得・検証に失敗した件数。
        """
        rows = []
        failures = 0
        successes = 0
        for index, task_id in enumerate(dict.fromkeys(task_ids), start=1):
            logger.info(f"{index}件目: タスク'{task_id}'を検証します。")
            try:
                task, _ = self.service.api.get_task(self.project_id, task_id)
            except Exception:
                logger.warning(f"タスク'{task_id}'の取得に失敗しました。", exc_info=True)
                failures += 1
                continue
            for input_index, input_data_id in enumerate(task["input_data_id_list"], start=1):
                try:
                    rows.extend(self.validate_input_data(task_id, input_data_id))
                    successes += 1
                except Exception:
                    logger.warning(f"task_id='{task_id}', input_data_id='{input_data_id}'の取得または検証に失敗しました。", exc_info=True)
                    failures += 1
                if input_index % 100 == 0:
                    logger.info(f"タスク'{task_id}': 入力データ{input_index}件を処理しました。")
        logger.info(f"属性制約の検証が完了しました。入力データ成功{successes}件、取得・検証失敗{failures}件、違反{len(rows)}件。")
        return rows, failures


class ListAttributeRestrictionViolation(CommandLine):
    def main(self) -> None:
        args = self.args
        self.require_project_access(args.project_id, project_member_roles=None)
        main_obj = ListAttributeRestrictionViolationMain(self.service, args.project_id)
        task_ids = main_obj.get_all_task_ids() if args.all_tasks else get_list_from_args(args.task_id)
        rows, failures = main_obj.collect(task_ids)
        if self.str_format == OutputFormat.CSV.value:
            rows = [{**row, "restriction": json.dumps(row["restriction"], ensure_ascii=False)} for row in rows]
        self.print_according_to_format(rows, csv_columns=COLUMNS)
        if failures:
            raise AnnofabCliException(f"{failures}件の取得または検証に失敗しました。出力には成功した入力データの違反のみ含まれます。")


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    ListAttributeRestrictionViolation(service, AnnofabApiFacade(service), args).main()


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    parser = annofabcli.common.cli.create_parser(
        subparsers,
        "list_attribute_restriction_violation",
        "アノテーション仕様の属性制約に違反するアノテーションを出力します。",
        description="属性間制約と読取専用属性を含めて検証します。CanInputは対象外です。Annofab提出時の検証の完全な再現ではありません。",
        epilog="すべてのプロジェクトメンバーロールで実行できます。",
    )
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    argument_parser.add_task_id_or_all_tasks()
    argument_parser.add_format(choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON], default=OutputFormat.CSV)
    argument_parser.add_output()
    parser.set_defaults(subcommand_func=main)
    return parser
