from __future__ import annotations

import argparse
import copy
import logging
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import annofabapi
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor, get_attribute_name_en, get_label_name_en

import annofabcli.common.cli
from annofabcli.annotation_specs.attribute_restriction import AttributeRestrictionMessage
from annofabcli.annotation_specs.delete_attribute import restriction_references_attribute
from annofabcli.annotation_specs.utils import get_target_labels
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login, get_list_from_args
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedLabelDeletion:
    """
    ラベル削除対象を既存アノテーション仕様に対して解決した結果。
    """

    labels_to_remove: list[Mapping[str, Any]]
    """削除対象ラベル一覧。"""

    orphan_attributes: list[Mapping[str, Any]]
    """削除後にどのラベルからも参照されなくなる属性一覧。"""

    restrictions_to_remove: list[dict[str, Any]]
    """削除対象ラベルまたは孤立属性を参照するため削除する属性制約一覧。"""

    restriction_text_list: list[str]
    """削除する属性制約のテキスト一覧。"""


@dataclass(frozen=True)
class AffectingAnnotation:
    """
    既存アノテーションに影響する削除対象。
    """

    label_name_en: str
    """影響を受けるラベル英語名。"""

    annotation_count: int
    """対象ラベルのアノテーション数。"""


def get_label_text(label: Mapping[str, Any]) -> str:
    """
    ラベルを表示用テキストに変換する。

    Args:
        label: ラベル

    Returns:
        表示用テキスト
    """
    return f"label_name_en='{get_label_name_en(label)}'"


def restriction_references_label(restriction: Mapping[str, Any], label_ids: Collection[str]) -> bool:
    """
    属性制約が指定ラベルを参照しているかどうかを返す。

    Args:
        restriction: 属性制約
        label_ids: ラベルID一覧

    Returns:
        属性制約が指定ラベルを参照していればTrue
    """

    def references_label(value: object) -> bool:
        if isinstance(value, Mapping):
            labels = value.get("labels")
            if isinstance(labels, list) and any(label_id in label_ids for label_id in labels):
                return True
            return any(references_label(child_value) for child_value in value.values())
        if isinstance(value, list):
            return any(references_label(child_value) for child_value in value)
        return False

    return references_label(restriction)


def create_comment_for_delete_labels(resolved_deletion: ResolvedLabelDeletion) -> str:
    """
    ラベル削除時のデフォルトコメントを生成する。

    Args:
        resolved_deletion: 解決済みラベル削除対象

    Returns:
        アノテーション仕様変更コメント
    """
    lines = ["以下のラベルを削除しました。"]
    lines.extend(f" * {get_label_text(label)}" for label in resolved_deletion.labels_to_remove)
    if resolved_deletion.orphan_attributes:
        lines.extend(("", "以下の属性も、どのラベルからも参照されなくなったため削除しました。"))
        lines.extend(f" * attribute_name_en='{get_attribute_name_en(attribute)}'" for attribute in resolved_deletion.orphan_attributes)
    if resolved_deletion.restriction_text_list:
        lines.extend(("", "以下の属性制約も削除しました。"))
        lines.extend(f" * {restriction_text}" for restriction_text in resolved_deletion.restriction_text_list)
    return "\n".join(lines)


def create_confirm_message_for_delete_labels(
    resolved_deletion: ResolvedLabelDeletion,
    *,
    affecting_annotations: Sequence[AffectingAnnotation],
) -> str:
    """
    ラベル削除前の確認メッセージを生成する。

    Args:
        resolved_deletion: 解決済みラベル削除対象
        affecting_annotations: 既存アノテーションに影響する削除対象

    Returns:
        確認メッセージ
    """
    lines = [f"以下のラベル({len(resolved_deletion.labels_to_remove)}件)を削除します。"]
    lines.extend(f" * {get_label_text(label)}" for label in resolved_deletion.labels_to_remove)
    if resolved_deletion.orphan_attributes:
        lines.extend(("", "以下の属性も、どのラベルからも参照されなくなるため削除します。"))
        lines.extend(f" * attribute_name_en='{get_attribute_name_en(attribute)}'" for attribute in resolved_deletion.orphan_attributes)
    if resolved_deletion.restriction_text_list:
        lines.extend(("", "以下の属性制約も削除します。"))
        lines.extend(f" * {restriction_text}" for restriction_text in resolved_deletion.restriction_text_list)
    if affecting_annotations:
        lines.extend(("", "既存アノテーションへの影響:"))
        lines.extend(f" * label_name_en='{affected.label_name_en}': {affected.annotation_count} 件" for affected in affecting_annotations)
    lines.extend(("", "よろしいですか？"))
    return "\n".join(lines)


def create_message_for_affecting_annotations(affecting_annotations: Sequence[AffectingAnnotation]) -> str:
    """
    既存アノテーションに影響する削除対象を表すメッセージを生成する。

    Args:
        affecting_annotations: 既存アノテーションに影響する削除対象

    Returns:
        既存アノテーションに影響する削除対象を表すメッセージ
    """
    label_names = [affected.label_name_en for affected in affecting_annotations]
    annotation_counts = {affected.label_name_en: affected.annotation_count for affected in affecting_annotations}
    return f"削除対象のラベルがアノテーションで使われています。 :: label_names_en={label_names}, annotation_counts={annotation_counts}"


def resolve_label_deletion(
    annotation_specs: dict[str, Any],
    *,
    label_ids: Sequence[str] | None,
    label_name_ens: Sequence[str] | None,
) -> ResolvedLabelDeletion:
    """
    ラベル削除対象を既存アノテーション仕様に対して解決する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        label_ids: 対象ラベルID一覧
        label_name_ens: 対象ラベル英語名一覧

    Returns:
        解決済みラベル削除対象
    """
    annotation_specs_accessor = AnnotationSpecsAccessor(annotation_specs)
    labels_to_remove = get_target_labels(annotation_specs_accessor, label_ids=label_ids, label_name_ens=label_name_ens)
    removed_label_ids = {label["label_id"] for label in labels_to_remove}
    removed_label_attribute_ids = {attribute_id for label in labels_to_remove for attribute_id in label["additional_data_definitions"]}
    remaining_attribute_ids = {attribute_id for label in annotation_specs["labels"] if label["label_id"] not in removed_label_ids for attribute_id in label["additional_data_definitions"]}
    orphan_attributes = [
        attribute
        for attribute in annotation_specs["additionals"]
        if attribute["additional_data_definition_id"] in removed_label_attribute_ids and attribute["additional_data_definition_id"] not in remaining_attribute_ids
    ]
    orphan_attribute_ids = {attribute["additional_data_definition_id"] for attribute in orphan_attributes}
    restrictions_to_remove = [
        restriction
        for restriction in annotation_specs["restrictions"]
        if restriction_references_label(restriction, removed_label_ids) or restriction_references_attribute(restriction, orphan_attribute_ids)
    ]
    message_obj = AttributeRestrictionMessage(
        labels=annotation_specs["labels"],
        additionals=annotation_specs["additionals"],
        raise_if_not_found=True,
    )
    restriction_text_list = [message_obj.get_restriction_text(restriction["additional_data_definition_id"], restriction["condition"]) for restriction in restrictions_to_remove]
    return ResolvedLabelDeletion(
        labels_to_remove=labels_to_remove,
        orphan_attributes=orphan_attributes,
        restrictions_to_remove=restrictions_to_remove,
        restriction_text_list=restriction_text_list,
    )


def build_request_body_for_delete_labels(
    annotation_specs: dict[str, Any],
    *,
    resolved_deletion: ResolvedLabelDeletion,
    comment: str | None,
) -> dict[str, Any]:
    """
    ラベル削除用の request body を生成する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        resolved_deletion: 解決済みラベル削除対象
        comment: 変更コメント

    Returns:
        Annofab API に渡す request body
    """
    request_body = copy.deepcopy(annotation_specs)
    removed_label_ids = {label["label_id"] for label in resolved_deletion.labels_to_remove}
    orphan_attribute_ids = {attribute["additional_data_definition_id"] for attribute in resolved_deletion.orphan_attributes}
    request_body["labels"] = [label for label in request_body["labels"] if label["label_id"] not in removed_label_ids]
    request_body["additionals"] = [attribute for attribute in request_body["additionals"] if attribute["additional_data_definition_id"] not in orphan_attribute_ids]
    request_body["restrictions"] = [restriction for restriction in request_body["restrictions"] if restriction not in resolved_deletion.restrictions_to_remove]
    if comment is None:
        comment = create_comment_for_delete_labels(resolved_deletion)
    request_body["comment"] = comment
    request_body["last_updated_datetime"] = annotation_specs["updated_datetime"]
    return request_body


class DeleteLabelsMain(CommandLineWithConfirm):
    """
    ラベルを削除する本体処理。
    """

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

    def count_annotations_by_label(self, label_id: str) -> int:
        """
        指定ラベルのアノテーション数を返す。

        Args:
            label_id: ラベルID

        Returns:
            指定ラベルのアノテーション数
        """
        content, _ = self.service.api.get_annotation_list(
            self.project_id,
            query_params={"query": {"label_id": label_id}, "limit": 1, "v": "2"},
        )
        return int(content["total_count"])

    def collect_affecting_annotations(self, resolved_deletion: ResolvedLabelDeletion) -> list[AffectingAnnotation]:
        """
        削除対象のうち既存アノテーションに影響するものを返す。

        Args:
            resolved_deletion: 解決済みラベル削除対象

        Returns:
            既存アノテーションに影響する削除対象一覧
        """
        affecting_annotations: list[AffectingAnnotation] = []
        for label in resolved_deletion.labels_to_remove:
            annotation_count = self.count_annotations_by_label(label["label_id"])
            if annotation_count == 0:
                continue
            affecting_annotations.append(
                AffectingAnnotation(
                    label_name_en=get_label_name_en(label),
                    annotation_count=annotation_count,
                )
            )
        return affecting_annotations

    def validate_deletion(self, affecting_annotations: Sequence[AffectingAnnotation]) -> bool:
        """
        ラベルを削除してよいか検証する。

        Args:
            affecting_annotations: 既存アノテーションに影響する削除対象

        Returns:
            削除してよい場合はTrue、既存アノテーションに影響するため中止する場合はFalse
        """
        if len(affecting_annotations) == 0:
            return True

        message = create_message_for_affecting_annotations(affecting_annotations)
        if self.allow_affecting_annotations:
            logger.warning("既存アノテーションに影響する変更がありますが、オプションで許可されているため、ラベルを削除します。\n%s", message)
            return True

        logger.warning(
            "既存アノテーションに影響するため、ラベルの削除を中止しました。既存アノテーションに影響が出ることを理解した上で削除する場合は、 `--allow_affecting_annotations` を指定してください。\n%s",
            message,
        )
        return False

    def delete_labels(
        self,
        *,
        label_ids: Sequence[str] | None,
        label_name_ens: Sequence[str] | None,
        comment: str | None = None,
    ) -> bool:
        """
        指定したラベルを削除し、アノテーション仕様を更新する。

        Args:
            label_ids: 対象ラベルID一覧
            label_name_ens: 対象ラベル英語名一覧
            comment: 変更コメント

        Returns:
            更新を実行した場合はTrue、確認で中断した場合はFalse
        """
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        resolved_deletion = resolve_label_deletion(
            old_annotation_specs,
            label_ids=label_ids,
            label_name_ens=label_name_ens,
        )
        affecting_annotations = self.collect_affecting_annotations(resolved_deletion)
        if not self.validate_deletion(affecting_annotations):
            return False

        confirm_message = create_confirm_message_for_delete_labels(resolved_deletion, affecting_annotations=affecting_annotations)
        if not self.confirm_processing(confirm_message):
            return False

        request_body = build_request_body_for_delete_labels(old_annotation_specs, resolved_deletion=resolved_deletion, comment=comment)
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"{len(resolved_deletion.labels_to_remove)} 件のラベルを削除しました。")
        return True


class DeleteLabels(CommandLine):
    """
    ラベルを削除するコマンド。
    """

    COMMON_MESSAGE = "annofabcli annotation_specs delete_labels: error:"

    def main(self) -> None:
        args = self.args

        label_ids = get_list_from_args(args.label_id) if args.label_id is not None else None
        label_name_ens = get_list_from_args(args.label_name_en) if args.label_name_en is not None else None

        obj = DeleteLabelsMain(
            self.service,
            project_id=args.project_id,
            all_yes=args.yes,
            allow_affecting_annotations=args.allow_affecting_annotations,
        )
        obj.delete_labels(
            label_ids=label_ids,
            label_name_ens=label_name_ens,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    ``delete_labels`` サブコマンドの引数を定義する。

    Args:
        parser: 引数を追加するArgumentParser
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    label_group = parser.add_mutually_exclusive_group(required=True)
    label_group.add_argument(
        "--label_name_en",
        type=str,
        nargs="+",
        help="削除するラベルの英語名。複数指定できます。 ``file://`` を先頭に付けると一覧ファイルを指定できます。",
    )
    label_group.add_argument(
        "--label_id",
        type=str,
        nargs="+",
        help="削除するラベルのlabel_id。複数指定できます。 ``file://`` を先頭に付けると一覧ファイルを指定できます。",
    )
    parser.add_argument(
        "--allow_affecting_annotations",
        action="store_true",
        help="指定すると、既存アノテーションに影響する変更でもラベルを削除します。",
    )
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``delete_labels`` コマンドのエントリポイント。

    Args:
        args: コマンドライン引数
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteLabels(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs delete_labels`` 用のparserを生成する。

    Args:
        subparsers: 親parserのsubparsers

    Returns:
        生成したArgumentParser
    """
    subcommand_name = "delete_labels"
    subcommand_help = "アノテーション仕様からラベルを複数削除します。"
    description = "アノテーション仕様からラベルを複数件削除します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
