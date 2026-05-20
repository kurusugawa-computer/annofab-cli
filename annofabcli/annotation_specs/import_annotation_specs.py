from __future__ import annotations

import argparse
import copy
import functools
import json
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import annofabapi

import annofabcli.common.cli
from annofabcli.annotation_specs.diff_compare import create_annotation_specs_diff
from annofabcli.annotation_specs.diff_models import AnnotationSpecsDiff
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProtectedImportChanges:
    """既存アノテーションで使われているため、importを中止する変更一覧。"""

    removed_label_ids: list[str] = field(default_factory=list)
    """削除対象のうち、アノテーションで使われているラベルID一覧。"""

    changed_annotation_type_label_ids: list[str] = field(default_factory=list)
    """種類変更対象のうち、アノテーションで使われているラベルID一覧。"""

    changed_type_attribute_ids: list[str] = field(default_factory=list)
    """種類変更対象のうち、アノテーションで使われている属性ID一覧。"""

    removed_label_attribute_relations: list[tuple[str, str]] = field(default_factory=list)
    """ラベルから削除される属性のうち、アノテーションで使われている一覧。要素は(label_id, attribute_id)。"""

    removed_choices: list[tuple[str, str]] = field(default_factory=list)
    """削除対象のうち、アノテーションで使われている選択肢一覧。要素は(attribute_id, choice_id)。"""

    def has_changes(self) -> bool:
        """importを中止すべき変更があるかどうかを返す。"""
        return any(
            [
                self.removed_label_ids,
                self.changed_annotation_type_label_ids,
                self.changed_type_attribute_ids,
                self.removed_label_attribute_relations,
                self.removed_choices,
            ]
        )


def create_comment_for_import_annotation_specs() -> str:
    """import時のデフォルトコメントを生成する。"""
    return "annofabcli annotation_specs import コマンドでアノテーション仕様をインポートしました。"


def read_annotation_specs_json(annotation_specs_json_file: Path) -> dict[str, Any]:
    """アノテーション仕様JSONを読み込む。

    Args:
        annotation_specs_json_file: アノテーション仕様JSONファイルのパス

    Returns:
        読み込んだアノテーション仕様
    """
    with annotation_specs_json_file.open(encoding="utf-8") as f:
        loaded = json.load(f)
    if not isinstance(loaded, dict):
        raise TypeError("`--annotation_specs_json_file` にはJSONオブジェクト形式のアノテーション仕様を指定してください。")
    return loaded


def build_request_body_for_import_annotation_specs(
    current_annotation_specs: dict[str, Any],
    imported_annotation_specs: dict[str, Any],
    *,
    comment: str | None,
) -> dict[str, Any]:
    """アノテーション仕様import用の request body を生成する。

    Args:
        current_annotation_specs: 現在のアノテーション仕様
        imported_annotation_specs: インポートするアノテーション仕様
        comment: 変更コメント

    Returns:
        Annofab API に渡す request body
    """
    request_body = copy.deepcopy(imported_annotation_specs)
    request_body.pop("project_id", None)
    request_body["comment"] = comment if comment is not None else create_comment_for_import_annotation_specs()
    request_body["last_updated_datetime"] = current_annotation_specs["updated_datetime"]
    return request_body


def collect_label_ids_by_attribute_id(annotation_specs: dict[str, Any]) -> dict[str, list[str]]:
    """属性IDごとに、その属性を含むラベルID一覧を収集する。

    Args:
        annotation_specs: アノテーション仕様

    Returns:
        属性IDをキー、ラベルID一覧を値に持つ辞書。
    """
    label_ids_by_attribute_id: dict[str, list[str]] = {}
    for label in annotation_specs["labels"]:
        label_id = label["label_id"]
        for attribute_id in label["additional_data_definitions"]:
            label_ids_by_attribute_id.setdefault(attribute_id, []).append(label_id)
    return label_ids_by_attribute_id


def _append_unique_removed_label_attribute_relation(protected: ProtectedImportChanges, label_id: str, attribute_id: str) -> None:
    """利用中のラベル属性ペアを重複なく追加する。"""
    relation = (label_id, attribute_id)
    if relation not in protected.removed_label_attribute_relations:
        protected.removed_label_attribute_relations.append(relation)


def _append_used_removed_label_attribute_relations(
    protected: ProtectedImportChanges,
    label_attribute_pairs: Iterable[tuple[str, str]],
    *,
    is_attribute_used: Callable[[str, str], bool],
) -> None:
    """利用中のラベル属性ペアを削除対象として追加する。"""
    for label_id, attribute_id in label_attribute_pairs:
        if is_attribute_used(label_id, attribute_id):
            _append_unique_removed_label_attribute_relation(protected, label_id, attribute_id)


def _is_attribute_used_in_any_label(
    label_ids_by_attribute_id: dict[str, list[str]],
    attribute_id: str,
    *,
    is_attribute_used: Callable[[str, str], bool],
) -> bool:
    """属性がいずれかのラベルで使われているかどうかを返す。"""
    return any(is_attribute_used(label_id, attribute_id) for label_id in label_ids_by_attribute_id.get(attribute_id, []))


def _is_choice_used_in_any_label(
    label_ids_by_attribute_id: dict[str, list[str]],
    attribute_id: str,
    choice_id: str,
    *,
    is_choice_used: Callable[[str, str, str], bool],
) -> bool:
    """選択肢がいずれかのラベル属性で使われているかどうかを返す。"""
    return any(is_choice_used(label_id, attribute_id, choice_id) for label_id in label_ids_by_attribute_id.get(attribute_id, []))


def create_protected_import_changes(
    diff: AnnotationSpecsDiff,
    current_annotation_specs: dict[str, Any],
    *,
    is_label_used: Callable[[str], bool],
    is_attribute_used: Callable[[str, str], bool],
    is_choice_used: Callable[[str, str, str], bool],
) -> ProtectedImportChanges:
    """差分のうち、既存アノテーションで使われている変更を抽出する。

    Args:
        diff: 現在仕様とimport仕様の差分
        current_annotation_specs: 現在のアノテーション仕様
        is_label_used: label_idを受け取り、利用中ならTrueを返す関数
        is_attribute_used: label_idとattribute_idを受け取り、利用中ならTrueを返す関数
        is_choice_used: label_id、attribute_id、choice_idを受け取り、利用中ならTrueを返す関数

    Returns:
        importを中止すべき変更一覧
    """
    protected = ProtectedImportChanges()
    label_ids_by_attribute_id = collect_label_ids_by_attribute_id(current_annotation_specs)

    if diff.labels is not None:
        protected.removed_label_ids.extend(label_id for label_id in diff.labels.removed_label_ids if is_label_used(label_id))
        for changed_label in diff.labels.changed_labels:
            if changed_label.annotation_type_changed and is_label_used(changed_label.label_id):
                protected.changed_annotation_type_label_ids.append(changed_label.label_id)
            _append_used_removed_label_attribute_relations(
                protected,
                ((changed_label.label_id, attribute_id) for attribute_id in changed_label.removed_attribute_ids),
                is_attribute_used=is_attribute_used,
            )

    if diff.attributes is not None:
        for changed_attribute in diff.attributes.changed_attributes:
            if changed_attribute.type_changed and _is_attribute_used_in_any_label(
                label_ids_by_attribute_id,
                changed_attribute.attribute_id,
                is_attribute_used=is_attribute_used,
            ):
                protected.changed_type_attribute_ids.append(changed_attribute.attribute_id)
            for choice_id in changed_attribute.removed_choice_ids:
                if _is_choice_used_in_any_label(
                    label_ids_by_attribute_id,
                    changed_attribute.attribute_id,
                    choice_id,
                    is_choice_used=is_choice_used,
                ):
                    protected.removed_choices.append((changed_attribute.attribute_id, choice_id))

    return protected


def validate_import_annotation_specs(protected_changes: ProtectedImportChanges) -> None:
    """importを中止すべき変更があれば例外を送出する。

    Args:
        protected_changes: importを中止すべき変更一覧

    Raises:
        ValueError: 既存アノテーションで使われているラベル/属性/選択肢への削除や種類変更がある場合
    """
    if not protected_changes.has_changes():
        return

    messages = []
    if protected_changes.removed_label_ids:
        messages.append(f"削除対象のラベルがアノテーションで使われています。 :: label_ids={protected_changes.removed_label_ids}")
    if protected_changes.changed_annotation_type_label_ids:
        messages.append(f"種類変更対象のラベルがアノテーションで使われています。 :: label_ids={protected_changes.changed_annotation_type_label_ids}")
    if protected_changes.changed_type_attribute_ids:
        messages.append(f"種類変更対象の属性がアノテーションで使われています。 :: attribute_ids={protected_changes.changed_type_attribute_ids}")
    if protected_changes.removed_label_attribute_relations:
        messages.append(f"ラベルから削除される属性がアノテーションで使われています。 :: label_attribute_pairs={protected_changes.removed_label_attribute_relations}")
    if protected_changes.removed_choices:
        messages.append(f"削除対象の選択肢がアノテーションで使われています。 :: attribute_choice_pairs={protected_changes.removed_choices}")

    raise ValueError("既存アノテーションに影響するため、アノテーション仕様のインポートを中止しました。\n" + "\n".join(messages))


class ImportAnnotationSpecsMain(CommandLineWithConfirm):
    """アノテーション仕様をimportする本体処理。"""

    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        project_id: str,
        all_yes: bool,
    ) -> None:
        self.service = service
        self.project_id = project_id
        CommandLineWithConfirm.__init__(self, all_yes)

    def has_annotation(self, query: dict[str, Any]) -> bool:
        """指定したqueryに一致するアノテーションが存在するかどうかを返す。"""
        content, _ = self.service.api.get_annotation_list(
            self.project_id,
            query_params={"query": query, "limit": 1, "v": "2"},
        )
        return content["total_count"] > 0

    def validate_import(self, *, current_annotation_specs: dict[str, Any], imported_annotation_specs: dict[str, Any]) -> None:
        """importしてよい差分かどうかを検証する。"""
        diff = create_annotation_specs_diff(current_annotation_specs, imported_annotation_specs, targets={"labels", "attributes"})

        @functools.cache
        def is_label_used(label_id: str) -> bool:
            return self.has_annotation({"label_id": label_id})

        @functools.cache
        def is_attribute_used(label_id: str, attribute_id: str) -> bool:
            return self.has_annotation({"label_id": label_id, "attributes": [{"additional_data_definition_id": attribute_id}]})

        @functools.cache
        def is_choice_used(label_id: str, attribute_id: str, choice_id: str) -> bool:
            return self.has_annotation({"label_id": label_id, "attributes": [{"additional_data_definition_id": attribute_id, "choice": choice_id}]})

        protected_changes = create_protected_import_changes(
            diff,
            current_annotation_specs,
            is_label_used=is_label_used,
            is_attribute_used=is_attribute_used,
            is_choice_used=is_choice_used,
        )
        validate_import_annotation_specs(protected_changes)

    def import_annotation_specs(self, *, imported_annotation_specs: dict[str, Any], comment: str | None = None) -> bool:
        """アノテーション仕様をimportする。

        Args:
            imported_annotation_specs: インポートするアノテーション仕様
            comment: 変更コメント

        Returns:
            更新を実行した場合はTrue、確認で中断した場合はFalse
        """
        current_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        self.validate_import(current_annotation_specs=current_annotation_specs, imported_annotation_specs=imported_annotation_specs)

        confirm_message = f"プロジェクト'{self.project_id}'のアノテーション仕様をインポートします。よろしいですか？"
        if not self.confirm_processing(confirm_message):
            return False

        request_body = build_request_body_for_import_annotation_specs(current_annotation_specs, imported_annotation_specs, comment=comment)
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"プロジェクト'{self.project_id}'のアノテーション仕様をインポートしました。")
        return True


class ImportAnnotationSpecs(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs import: error:"

    def main(self) -> None:
        args = self.args
        imported_annotation_specs = read_annotation_specs_json(args.annotation_specs_json_file)
        obj = ImportAnnotationSpecsMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.import_annotation_specs(imported_annotation_specs=imported_annotation_specs, comment=args.comment)


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    parser.add_argument(
        "--annotation_specs_json_file",
        type=Path,
        required=True,
        help="インポートするアノテーション仕様JSONファイルを指定します。 ``annotation_specs export`` コマンドで出力したJSONファイルを指定してください。",
    )
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")
    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ImportAnnotationSpecs(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "import"
    subcommand_help = "アノテーション仕様の情報をインポートします。"
    description = "アノテーション仕様の情報をJSON形式でインポートします。既存アノテーションで使われているラベルや属性、選択肢に影響する削除や種類変更は中止します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
