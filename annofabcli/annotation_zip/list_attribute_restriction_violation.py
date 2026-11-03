from __future__ import annotations

import argparse
import copy
import json
import logging
import tempfile
from collections.abc import Collection
from pathlib import Path
from typing import Any

from annofabapi.models import ProjectMemberRole
from annofabapi.util.attribute_restriction_validation import AttributeRestrictionValidator
from annofabapi.util.attribute_restrictions import Restriction
from annofabapi.util.page import create_3dpc_editor_url, create_image_editor_url, create_video_editor_url

import annofabcli.common.cli
from annofabcli.annotation_zip.annotation_name import AnnotationNameTranslator, add_use_japanese_name_argument
from annofabcli.common.annofab.annotation_editor_url import (
    ANNOTATION_EDITOR_TYPE_CHOICES,
    AnnotationEditorType,
    create_annotation_editor_url,
    get_annotation_editor_type_from_input_data_type,
)
from annofabcli.common.annofab.annotation_zip import lazy_parse_simple_annotation_by_input_data
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, ArgumentParser, CommandLineWithoutWebapi, build_annofabapi_resource_and_login, get_list_from_args
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import OutputFormat
from annofabcli.common.exceptions import AnnofabCliException
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)

COLUMNS = (
    "project_id",
    "task_id",
    "input_data_id",
    "annotation_id",
    "label_name",
    "attribute_id",
    "attribute_name",
    "attribute_value",
    "restriction_index",
    "restriction_type",
    "restriction_text",
    "restriction",
    "annotation_editor_url",
)
"""違反一覧の出力列。"""


class ListAttributeRestrictionViolationMain:
    """アノテーションZIPを入力データ単位で検証する。"""

    def __init__(self, annotation_specs: dict[str, Any], annotation_editor_type: AnnotationEditorType | None = None, *, use_japanese_name: bool = False) -> None:
        self.specs = annotation_specs
        """検証に使用するアノテーション仕様。"""
        self.validator = AttributeRestrictionValidator(annotation_specs)
        """入力データ間で再利用する検証器。"""
        self.editor_type = annotation_editor_type
        """URLに使用するエディタの種類。未指定時はアノテーションから推定する。"""
        self.name_translator = AnnotationNameTranslator(annotation_specs) if use_japanese_name else None
        """日本語名で出力する場合に使用する変換器。"""
        self.display_specs = copy.deepcopy(annotation_specs) if use_japanese_name else annotation_specs
        """制約の説明文の生成に使用するアノテーション仕様。"""
        if use_japanese_name:
            names = [label["label_name"] for label in self.display_specs["labels"]]
            for additional in self.display_specs["additionals"]:
                names.append(additional["name"])
                names.extend(choice["name"] for choice in additional.get("choices", []))
            for name in names:
                japanese_name = next((message["message"] for message in name["messages"] if message["lang"] == "ja-JP"), None)
                if japanese_name is not None:
                    for message in name["messages"]:
                        if message["lang"] == "en-US":
                            message["message"] = japanese_name

    def validate_input_data(self, annotation: dict[str, Any]) -> list[dict[str, Any]]:
        """同一入力データの全アノテーションから違反一覧を生成する。

        Args:
            annotation: Simple Annotation形式のJSONの内容。

        Returns:
            アノテーションと違反した制約の組ごとの出力行。
        """
        project_id = annotation["project_id"]
        task_id = annotation["task_id"]
        input_data_id = annotation["input_data_id"]
        violations = self.validator.validate_simple_annotation_details(annotation["details"])
        details = {detail["annotation_id"]: detail for detail in annotation["details"]}
        rows = []
        for violation in violations:
            detail = details[violation.annotation_id]
            restriction = self.specs["restrictions"][violation.restriction_index]
            try:
                restriction_text = Restriction.from_dict(restriction).to_human_readable(self.display_specs)
            except (ValueError, KeyError, TypeError, NotImplementedError):
                logger.warning(f"制約{violation.restriction_index}を説明文に変換できないため、JSONで出力します。", exc_info=True)
                restriction_text = json.dumps(restriction, ensure_ascii=False)
            # 分類アノテーションのdataはnullなので、エディタの種類からURLを生成する。
            if detail["data"] is None:
                if self.editor_type == "video":
                    url = create_video_editor_url(project_id, task_id, annotation_id=violation.annotation_id)
                else:
                    create_url = create_image_editor_url if self.editor_type in {None, "image"} else create_3dpc_editor_url
                    url = create_url(project_id, task_id, input_data_id=input_data_id, annotation_id=violation.annotation_id)
            else:
                url = create_annotation_editor_url(annotation, detail, self.editor_type)
            label_name = detail["label"]
            attribute_name = violation.attribute_name
            attribute_value = detail["attributes"].get(attribute_name)
            if self.name_translator is not None:
                if isinstance(attribute_value, str):
                    attribute_value = self.name_translator.choice_name(label_name, attribute_name, attribute_value)
                attribute_name = self.name_translator.attribute_name(label_name, attribute_name)
                label_name = self.name_translator.label_name(label_name)
            rows.append(
                {
                    "project_id": project_id,
                    "task_id": task_id,
                    "input_data_id": input_data_id,
                    "annotation_id": violation.annotation_id,
                    "label_name": label_name,
                    "attribute_id": violation.attribute_id,
                    "attribute_name": attribute_name,
                    "attribute_value": attribute_value,
                    "restriction_index": violation.restriction_index,
                    "restriction_type": restriction["condition"]["_type"],
                    "restriction_text": restriction_text,
                    "restriction": restriction,
                    "annotation_editor_url": url,
                }
            )
        return rows

    def collect(self, annotation_path: Path, target_task_ids: Collection[str] | None = None) -> tuple[list[dict[str, Any]], int]:
        """読み込み・検証に失敗しても残りの入力データを処理する。

        Args:
            annotation_path: アノテーションZIPまたは展開ディレクトリ。
            target_task_ids: 出力対象タスクID。未指定の場合は全タスク。

        Returns:
            成功した入力データの違反一覧と、読み込み・検証に失敗した件数。
        """
        rows = []
        failures = 0
        successes = 0
        skipped = 0
        task_ids = set(target_task_ids) if target_task_ids is not None else None
        for index, parser in enumerate(lazy_parse_simple_annotation_by_input_data(annotation_path), start=1):
            if task_ids is not None and parser.task_id not in task_ids:
                skipped += 1
                continue
            logger.debug(f"{index}件目: '{parser.json_file_path}'を検証します。")
            try:
                rows.extend(self.validate_input_data(parser.load_json()))
                successes += 1
            except Exception:
                logger.warning(f"'{parser.json_file_path}'の読み込みまたは検証に失敗しました。", exc_info=True)
                failures += 1
            if (successes + failures) % 100 == 0:
                logger.info(f"入力データ{successes + failures}件を処理しました。")
        logger.info(f"属性制約の検証が完了しました。入力データ成功{successes}件、スキップ{skipped}件、失敗{failures}件、違反{len(rows)}件。")
        return rows, failures


class ListAttributeRestrictionViolation(CommandLineWithoutWebapi):
    def run(self, annotation_path: Path, annotation_specs: dict[str, Any], annotation_editor_type: AnnotationEditorType | None = None) -> None:
        """指定されたアノテーションZIPを検証して結果を出力する。

        Args:
            annotation_path: アノテーションZIPまたは展開ディレクトリ。
            annotation_specs: 検証に使用するアノテーション仕様。
            annotation_editor_type: URLに使用するエディタの種類。

        Returns:
            None。
        """
        task_ids = get_list_from_args(self.args.task_id) if self.args.task_id is not None else None
        rows, failures = ListAttributeRestrictionViolationMain(annotation_specs, annotation_editor_type, use_japanese_name=self.args.use_japanese_name).collect(annotation_path, task_ids)
        if self.str_format == OutputFormat.CSV.value:
            rows = [{**row, "restriction": json.dumps(row["restriction"], ensure_ascii=False)} for row in rows]
        self.print_according_to_format(rows, csv_columns=COLUMNS)
        if failures:
            raise AnnofabCliException(f"{failures}件の読み込みまたは検証に失敗しました。出力には成功した入力データの違反のみ含まれます。")


def main(args: argparse.Namespace) -> None:
    command = ListAttributeRestrictionViolation(args)
    annotation_specs = None
    if args.annotation_specs_json_file is not None:
        with args.annotation_specs_json_file.open(encoding="utf-8") as stream:
            annotation_specs = json.load(stream)
    if args.annotation is not None:
        if annotation_specs is None:
            logger.error("--annotationを指定するときは、--annotation_specs_json_fileが必要です。")
            raise SystemExit(COMMAND_LINE_ERROR_STATUS_CODE)
        command.run(args.annotation, annotation_specs, args.annotation_editor_type)
        return

    service = build_annofabapi_resource_and_login(args)
    AnnofabApiFacade(service).require_project_access(
        args.project_id,
        project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER],
    )
    if annotation_specs is None:
        annotation_specs, _ = service.api.get_annotation_specs(args.project_id, query_params={"v": "3"})
    editor_type = args.annotation_editor_type
    if editor_type is None:
        project, _ = service.api.get_project(args.project_id)
        editor_type = get_annotation_editor_type_from_input_data_type(project["input_data_type"])
    with tempfile.TemporaryDirectory() as temporary_dir:
        download_dir = args.temp_dir if args.temp_dir is not None else Path(temporary_dir)
        download_dir.mkdir(parents=True, exist_ok=True)
        annotation_path = DownloadingFile(service).download_annotation_zip_to_dir(args.project_id, download_dir, is_latest=args.latest)
        command.run(annotation_path, annotation_specs, editor_type)


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    parser = annofabcli.common.cli.create_parser(
        subparsers,
        "list_attribute_restriction_violation",
        "アノテーションZIPを読み込み、属性制約に違反するアノテーションを出力します。",
        description="アノテーションZIPを読み込み、属性制約に違反するアノテーションを出力します。Annofab提出時の検証の完全な再現ではありません。",
        epilog="ZIPをダウンロードする場合は、オーナロールまたはアノテーションユーザロールが必要です。ローカルファイルのみの場合は認証不要です。",
    )
    argument_parser = ArgumentParser(parser)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("-p", "--project_id", help="アノテーションZIPと現在のアノテーション仕様を取得するプロジェクトID。")
    source_group.add_argument("--annotation", type=Path, help="アノテーションZIPまたは展開ディレクトリ。--annotation_specs_json_fileも指定してください。")
    parser.add_argument(
        "--annotation_specs_json_file",
        type=Path,
        help="検証に使用するアノテーション仕様JSON。annotation_specs exportの出力を指定してください。--project_id指定時は、未指定ならAPIから現在の仕様を取得します。",
    )
    argument_parser.add_task_id(required=False)
    parser.add_argument("--latest", action="store_true", help="--project_id指定時、アノテーションZIPを更新してから取得します。更新には数分かかることがあります。")
    parser.add_argument("--temp_dir", type=Path, help="--project_id指定時、アノテーションZIPのダウンロード先ディレクトリ。")
    parser.add_argument("--annotation_editor_type", choices=ANNOTATION_EDITOR_TYPE_CHOICES, help="URLに使用するエディタの種類。ローカル入力で未指定の場合はアノテーションの種類から推定します。")
    argument_parser.add_format(choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON], default=OutputFormat.CSV)
    argument_parser.add_output()
    add_use_japanese_name_argument(parser)
    parser.set_defaults(subcommand_func=main)
    return parser
