from __future__ import annotations

import argparse
import copy
import functools
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import annofabapi
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor, get_english_message

import annofabcli.common.cli
from annofabcli.annotation_specs.diff_compare import create_annotation_specs_diff
from annofabcli.annotation_specs.diff_models import AnnotationSpecsDiff
from annofabcli.annotation_specs.diff_text_formatter import format_annotation_specs_diff_as_text
from annofabcli.annotation_specs.utils import get_attribute_name_en, get_label_name_en
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import output_string

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProtectedImportChanges:
    """既存アノテーションで使われているため、importを中止する変更一覧。"""

    removed_label_names: set[str] = field(default_factory=set)
    """削除対象のうち、アノテーションで使われているラベル英語名一覧。"""

    changed_annotation_type_label_names: set[str] = field(default_factory=set)
    """種類変更対象のうち、アノテーションで使われているラベル英語名一覧。"""

    changed_type_attribute_names: set[str] = field(default_factory=set)
    """種類変更対象のうち、アノテーションで使われている属性英語名一覧。"""

    removed_label_attribute_relations: set[tuple[str, str]] = field(default_factory=set)
    """ラベルから削除される属性のうち、アノテーションで使われている一覧。要素は(label_name_en, attribute_name_en)。"""

    removed_choices: set[tuple[str, str]] = field(default_factory=set)
    """削除対象のうち、アノテーションで使われている選択肢一覧。要素は(attribute_name_en, choice_name_en)。"""

    def has_changes(self) -> bool:
        """importを中止すべき変更があるかどうかを返す。"""
        return any(
            [
                self.removed_label_names,
                self.changed_annotation_type_label_names,
                self.changed_type_attribute_names,
                self.removed_label_attribute_relations,
                self.removed_choices,
            ]
        )


def create_comment_for_import_annotation_specs(diff_text: str | None = None) -> str:
    """import時のデフォルトコメントを生成する。"""
    comment = "annofabcli annotation_specs import コマンドでアノテーション仕様をインポートしました。"
    if diff_text is None or diff_text == "":
        return comment

    return f"{comment}\n\nインポートによるアノテーション仕様の差分:\n{diff_text}"


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
    diff_text: str | None = None,
) -> dict[str, Any]:
    """アノテーション仕様import用の request body を生成する。

    Args:
        current_annotation_specs: 現在のアノテーション仕様
        imported_annotation_specs: インポートするアノテーション仕様
        comment: 変更コメント
        diff_text: importで適用されるアノテーション仕様の差分テキスト

    Returns:
        Annofab API に渡す request body
    """
    request_body = copy.deepcopy(imported_annotation_specs)
    request_body.pop("project_id", None)
    request_body["comment"] = comment if comment is not None else create_comment_for_import_annotation_specs(diff_text)
    request_body["last_updated_datetime"] = current_annotation_specs["updated_datetime"]
    return request_body


def create_protected_import_changes(
    diff: AnnotationSpecsDiff,
    current_annotation_specs: dict[str, Any],
    *,
    is_label_used: Callable[[str], bool],
    is_choice_used: Callable[[str, str], bool],
) -> ProtectedImportChanges:
    """差分のうち、既存アノテーションで使われている変更を抽出する。

    Args:
        diff: 現在仕様とimport仕様の差分
        current_annotation_specs: 現在のアノテーション仕様
        is_label_used: label_idを受け取り、利用中ならTrueを返す関数
        is_choice_used: attribute_idとchoice_idを受け取り、利用中ならTrueを返す関数

    Returns:
        importを中止すべき変更一覧
    """
    protected = ProtectedImportChanges()
    annotation_specs_accessor = AnnotationSpecsAccessor(current_annotation_specs)

    def get_label_name(label_id: str) -> str:
        return get_label_name_en(annotation_specs_accessor.get_label(label_id=label_id)) or label_id

    def get_attribute_name(attribute_id: str) -> str:
        return get_attribute_name_en(annotation_specs_accessor.get_attribute(attribute_id=attribute_id)) or attribute_id

    def get_choice_name(attribute_id: str, choice_id: str) -> str:
        attribute = annotation_specs_accessor.get_attribute(attribute_id=attribute_id)
        choices = attribute["choices"]
        assert choices is not None
        choice = next(choice for choice in choices if choice["choice_id"] == choice_id)
        return get_english_message(choice["name"]) or choice_id

    @functools.cache
    def is_attribute_used(attribute_id: str) -> bool:
        """属性を含むラベルがアノテーションで使われているかどうかを返す。"""
        return any(is_label_used(label["label_id"]) for label in current_annotation_specs["labels"] if attribute_id in label["additional_data_definitions"])

    if diff.labels is not None:
        protected.removed_label_names.update(get_label_name(label_id) for label_id in diff.labels.removed_label_ids if is_label_used(label_id))
        for changed_label in diff.labels.changed_labels:
            if changed_label.annotation_type_changed and is_label_used(changed_label.label_id):
                protected.changed_annotation_type_label_names.add(get_label_name(changed_label.label_id))
            for attribute_id in changed_label.removed_attribute_ids:
                if is_label_used(changed_label.label_id):
                    protected.removed_label_attribute_relations.add((get_label_name(changed_label.label_id), get_attribute_name(attribute_id)))

    if diff.attributes is not None:
        for changed_attribute in diff.attributes.changed_attributes:
            if changed_attribute.type_changed and is_attribute_used(changed_attribute.attribute_id):
                protected.changed_type_attribute_names.add(get_attribute_name(changed_attribute.attribute_id))
            for choice_id in changed_attribute.removed_choice_ids:
                if is_choice_used(changed_attribute.attribute_id, choice_id):
                    protected.removed_choices.add((get_attribute_name(changed_attribute.attribute_id), get_choice_name(changed_attribute.attribute_id, choice_id)))

    return protected


def _format_names_for_message(names: set[str]) -> list[str]:
    """メッセージ表示用に英語名一覧を整列する。"""
    return sorted(names)


def _format_name_pairs_for_message(name_pairs: set[tuple[str, str]]) -> list[tuple[str, str]]:
    """メッセージ表示用に英語名ペア一覧を整列する。"""
    return sorted(name_pairs)


def create_message_for_protected_import_changes(protected_changes: ProtectedImportChanges) -> str:
    """既存アノテーションに影響する変更内容を表すメッセージを生成する。

    Args:
        protected_changes: importを中止すべき変更一覧

    Returns:
        既存アノテーションに影響する変更内容を表すメッセージ
    """
    messages = []
    if protected_changes.removed_label_names:
        messages.append(f"削除対象のラベルがアノテーションで使われています。 :: label_names={_format_names_for_message(protected_changes.removed_label_names)}")
    if protected_changes.changed_annotation_type_label_names:
        messages.append(f"種類変更対象のラベルがアノテーションで使われています。 :: label_names={_format_names_for_message(protected_changes.changed_annotation_type_label_names)}")
    if protected_changes.changed_type_attribute_names:
        messages.append(f"種類変更対象の属性がアノテーションで使われています。 :: attribute_names={_format_names_for_message(protected_changes.changed_type_attribute_names)}")
    if protected_changes.removed_label_attribute_relations:
        messages.append(f"ラベルから削除される属性がアノテーションで使われています。 :: label_attribute_names={_format_name_pairs_for_message(protected_changes.removed_label_attribute_relations)}")
    if protected_changes.removed_choices:
        messages.append(f"削除対象の選択肢がアノテーションで使われています。 :: attribute_choice_names={_format_name_pairs_for_message(protected_changes.removed_choices)}")

    return "\n".join(messages)


def validate_import_annotation_specs(
    protected_changes: ProtectedImportChanges,
    *,
    allow_affecting_annotations: bool = False,
) -> bool:
    """importしてよい変更かどうかを返す。

    Args:
        protected_changes: importを中止すべき変更一覧
        allow_affecting_annotations: Trueなら既存アノテーションに影響する変更でも許可する

    Returns:
        importしてよい場合はTrue、既存アノテーションに影響するため中止する場合はFalse
    """
    if not protected_changes.has_changes():
        return True

    message = create_message_for_protected_import_changes(protected_changes)
    if allow_affecting_annotations:
        logger.warning("既存アノテーションに影響する変更がありますが、オプションで許可されているため、アノテーション仕様をインポートします。\n%s", message)
        return True

    logger.warning("既存アノテーションに影響するため、アノテーション仕様のインポートを中止しました。\n%s", message)
    return False


def create_annotation_specs_diff_text_for_import(current_annotation_specs: dict[str, Any], imported_annotation_specs: dict[str, Any]) -> str:
    """importで適用されるアノテーション仕様の差分テキストを生成する。

    Args:
        current_annotation_specs: 現在のアノテーション仕様
        imported_annotation_specs: インポートするアノテーション仕様

    Returns:
        アノテーション仕様の差分テキスト。差分がない場合は空文字。
    """
    diff = create_annotation_specs_diff(current_annotation_specs, imported_annotation_specs)
    return format_annotation_specs_diff_as_text(diff, left_specs=current_annotation_specs, right_specs=imported_annotation_specs, detail=False)


def output_annotation_specs_diff_for_import(diff_text: str) -> None:
    """importで適用されるアノテーション仕様の差分を出力する。

    Args:
        diff_text: importで適用されるアノテーション仕様の差分テキスト
    """
    if diff_text == "":
        logger.info("差分はありません。")
        return

    output_string(f"インポートによるアノテーション仕様の差分:\n{diff_text}")


class ImportAnnotationSpecsMain(CommandLineWithConfirm):
    """アノテーション仕様をimportする本体処理。"""

    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        project_id: str,
        all_yes: bool,
        allow_affecting_annotations: bool = False,
    ) -> None:
        self.service = service
        self.project_id = project_id
        self.allow_affecting_annotations = allow_affecting_annotations
        CommandLineWithConfirm.__init__(self, all_yes)

    def has_annotation(self, query: dict[str, Any]) -> bool:
        """指定したqueryに一致するアノテーションが存在するかどうかを返す。"""
        content, _ = self.service.api.get_annotation_list(
            self.project_id,
            query_params={"query": query, "limit": 1, "v": "2"},
        )
        return content["total_count"] > 0

    def validate_import(self, *, current_annotation_specs: dict[str, Any], imported_annotation_specs: dict[str, Any]) -> bool:
        """importしてよい差分かどうかを検証する。"""
        diff = create_annotation_specs_diff(current_annotation_specs, imported_annotation_specs, targets={"labels", "attributes"})

        @functools.cache
        def is_label_used(label_id: str) -> bool:
            return self.has_annotation({"label_id": label_id})

        @functools.cache
        def is_choice_used(attribute_id: str, choice_id: str) -> bool:
            return self.has_annotation({"attributes": [{"additional_data_definition_id": attribute_id, "choice": choice_id}]})

        protected_changes = create_protected_import_changes(
            diff,
            current_annotation_specs,
            is_label_used=is_label_used,
            is_choice_used=is_choice_used,
        )
        return validate_import_annotation_specs(
            protected_changes,
            allow_affecting_annotations=self.allow_affecting_annotations,
        )

    def import_annotation_specs(self, *, imported_annotation_specs: dict[str, Any], comment: str | None = None) -> bool:
        """アノテーション仕様をimportする。

        Args:
            imported_annotation_specs: インポートするアノテーション仕様
            comment: 変更コメント

        Returns:
            更新を実行した場合はTrue、確認で中断した場合はFalse
        """
        current_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        if not self.validate_import(current_annotation_specs=current_annotation_specs, imported_annotation_specs=imported_annotation_specs):
            return False

        diff_text = create_annotation_specs_diff_text_for_import(current_annotation_specs, imported_annotation_specs)
        output_annotation_specs_diff_for_import(diff_text)

        confirm_message = f"プロジェクト'{self.project_id}'のアノテーション仕様をインポートします。よろしいですか？"
        if not self.confirm_processing(confirm_message):
            return False

        request_body = build_request_body_for_import_annotation_specs(current_annotation_specs, imported_annotation_specs, comment=comment, diff_text=diff_text)
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"プロジェクト'{self.project_id}'のアノテーション仕様をインポートしました。")
        return True


class ImportAnnotationSpecs(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs import: error:"

    def main(self) -> None:
        args = self.args
        imported_annotation_specs = read_annotation_specs_json(args.annotation_specs_json_file)
        obj = ImportAnnotationSpecsMain(
            self.service,
            project_id=args.project_id,
            all_yes=args.yes,
            allow_affecting_annotations=args.allow_affecting_annotations,
        )
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
    parser.add_argument(
        "--allow_affecting_annotations",
        action="store_true",
        help="指定すると、既存アノテーションに影響する変更でもアノテーション仕様をインポートします。",
    )
    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ImportAnnotationSpecs(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "import"
    subcommand_help = "アノテーション仕様の情報をインポートします。"
    description = "アノテーション仕様の情報をJSON形式でインポートします。既存アノテーションで使われているラベルや属性、選択肢に影響する削除や種類変更は、通常は中止します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
