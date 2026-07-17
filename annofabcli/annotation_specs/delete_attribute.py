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
from annofabcli.annotation_specs.utils import get_target_attributes, get_target_labels
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login, get_list_from_args
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LabelAttributePair:
    """
    削除対象のラベルと属性の組み合わせ。
    """

    label: Mapping[str, Any]
    """削除対象属性が紐づいているラベル。"""

    attribute: Mapping[str, Any]
    """ラベルから削除する属性。"""


@dataclass(frozen=True)
class ResolvedAttributeDeletion:
    """
    属性削除対象を既存アノテーション仕様に対して解決した結果。
    """

    label_attribute_pairs: list[LabelAttributePair]
    """削除対象のラベルと属性の組み合わせ一覧。"""

    orphan_attributes: list[Mapping[str, Any]]
    """削除後にどのラベルからも参照されなくなる属性一覧。"""

    restrictions_to_remove: list[dict[str, Any]]
    """削除後に不要になる属性制約一覧。"""

    restriction_text_list: list[str]
    """削除後に不要になる属性制約のテキスト一覧。"""


@dataclass(frozen=True)
class AffectingAnnotation:
    """
    既存アノテーションに影響する削除対象。
    """

    label_name_en: str
    """影響を受けるラベル英語名。"""

    attribute_name_en: str
    """影響を受ける属性英語名。"""

    annotation_count: int
    """対象ラベルのアノテーション数。"""


def get_label_attribute_pair_text(pair: LabelAttributePair) -> str:
    """
    ラベル属性ペアを表示用テキストに変換する。

    Args:
        pair: ラベル属性ペア

    Returns:
        表示用テキスト
    """
    return f"label_name_en='{get_label_name_en(pair.label)}', attribute_name_en='{get_attribute_name_en(pair.attribute)}'"


def restriction_references_attribute(restriction: Mapping[str, Any], attribute_ids: Collection[str]) -> bool:
    """
    属性制約が指定属性を参照しているかどうかを返す。

    Args:
        restriction: 属性制約
        attribute_ids: 属性ID一覧

    Returns:
        属性制約が指定属性を参照していればTrue
    """

    def references_attribute(value: object) -> bool:
        if isinstance(value, Mapping):
            if value.get("additional_data_definition_id") in attribute_ids:
                return True
            return any(references_attribute(child_value) for child_value in value.values())
        if isinstance(value, list):
            return any(references_attribute(child_value) for child_value in value)
        return False

    return references_attribute(restriction)


def create_comment_for_delete_attribute(resolved_deletion: ResolvedAttributeDeletion) -> str:
    """
    属性削除時のデフォルトコメントを生成する。

    Args:
        resolved_deletion: 解決済み属性削除対象

    Returns:
        アノテーション仕様変更コメント
    """
    lines = ["以下のラベルから属性を削除しました。"]
    lines.extend(f" * {get_label_attribute_pair_text(pair)}" for pair in resolved_deletion.label_attribute_pairs)
    if resolved_deletion.restriction_text_list:
        lines.extend(("", "以下の属性制約も削除しました。"))
        lines.extend(f" * {restriction_text}" for restriction_text in resolved_deletion.restriction_text_list)
    return "\n".join(lines)


def create_confirm_message_for_delete_attribute(
    resolved_deletion: ResolvedAttributeDeletion,
    *,
    affecting_annotations: Sequence[AffectingAnnotation],
) -> str:
    """
    属性削除前の確認メッセージを生成する。

    Args:
        resolved_deletion: 解決済み属性削除対象
        affecting_annotations: 既存アノテーションに影響する削除対象

    Returns:
        確認メッセージ
    """
    lines = [f"以下のラベルから属性({len(resolved_deletion.label_attribute_pairs)}件)を削除します。"]
    lines.extend(f" * {get_label_attribute_pair_text(pair)}" for pair in resolved_deletion.label_attribute_pairs)
    if resolved_deletion.restriction_text_list:
        lines.extend(("", "以下の属性制約も削除します。"))
        lines.extend(f" * {restriction_text}" for restriction_text in resolved_deletion.restriction_text_list)
    if affecting_annotations:
        lines.extend(("", "既存アノテーションへの影響:"))
        lines.extend(f" * label_name_en='{affected.label_name_en}', attribute_name_en='{affected.attribute_name_en}': {affected.annotation_count} 件" for affected in affecting_annotations)
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
    label_attribute_names = [(affected.label_name_en, affected.attribute_name_en) for affected in affecting_annotations]
    annotation_counts = {(affected.label_name_en, affected.attribute_name_en): affected.annotation_count for affected in affecting_annotations}
    return f"削除対象の属性を含むラベルがアノテーションで使われています。 :: label_attribute_names_en={label_attribute_names}, annotation_counts={annotation_counts}"


def get_labels_having_attribute(annotation_specs: Mapping[str, Any], *, attribute_id: str) -> list[Mapping[str, Any]]:
    """
    指定属性を持つラベル一覧を返す。

    Args:
        annotation_specs: 既存のアノテーション仕様
        attribute_id: 属性ID

    Returns:
        指定属性を持つラベル一覧
    """
    return [label for label in annotation_specs["labels"] if attribute_id in label["additional_data_definitions"]]


def resolve_attribute_deletion(
    annotation_specs: dict[str, Any],
    *,
    attribute_ids: Collection[str] | None,
    attribute_name_ens: Collection[str] | None,
    label_ids: Sequence[str] | None,
    label_name_ens: Sequence[str] | None,
    all_labels: bool = False,
) -> ResolvedAttributeDeletion:
    """
    属性削除対象を既存アノテーション仕様に対して解決する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        attribute_ids: 対象属性ID一覧
        attribute_name_ens: 対象属性英語名一覧
        label_ids: 対象ラベルID一覧
        label_name_ens: 対象ラベル英語名一覧
        all_labels: Trueなら、対象属性が紐づいているすべてのラベルから削除する

    Returns:
        解決済み属性削除対象
    """
    annotation_specs_accessor = AnnotationSpecsAccessor(annotation_specs)
    target_attributes = get_target_attributes(annotation_specs_accessor, attribute_ids=attribute_ids, attribute_name_ens=attribute_name_ens)

    if all_labels:
        label_attribute_pairs = [
            LabelAttributePair(label=label, attribute=attribute)
            for attribute in target_attributes
            for label in get_labels_having_attribute(annotation_specs, attribute_id=attribute["additional_data_definition_id"])
        ]
    else:
        target_labels = get_target_labels(annotation_specs_accessor, label_ids=label_ids, label_name_ens=label_name_ens)
        label_attribute_pairs = []
        for attribute in target_attributes:
            attribute_id = attribute["additional_data_definition_id"]
            for label in target_labels:
                if attribute_id not in label["additional_data_definitions"]:
                    raise ValueError(f"ラベルに対象属性が紐づいていません。 :: label_name_en='{get_label_name_en(label)}', attribute_name_en='{get_attribute_name_en(attribute)}'")
                label_attribute_pairs.append(LabelAttributePair(label=label, attribute=attribute))

    if len(label_attribute_pairs) == 0:
        raise ValueError("削除対象のラベルと属性の組み合わせがありません。")

    removed_pair_keys = {(pair.label["label_id"], pair.attribute["additional_data_definition_id"]) for pair in label_attribute_pairs}
    remaining_attribute_ids = {
        attribute_id for label in annotation_specs["labels"] for attribute_id in label["additional_data_definitions"] if (label["label_id"], attribute_id) not in removed_pair_keys
    }
    orphan_attributes = [attribute for attribute in target_attributes if attribute["additional_data_definition_id"] not in remaining_attribute_ids]
    orphan_attribute_ids = {attribute["additional_data_definition_id"] for attribute in orphan_attributes}
    restrictions_to_remove = [restriction for restriction in annotation_specs["restrictions"] if restriction_references_attribute(restriction, orphan_attribute_ids)]
    message_obj = AttributeRestrictionMessage(
        labels=annotation_specs["labels"],
        additionals=annotation_specs["additionals"],
        raise_if_not_found=True,
    )
    restriction_text_list = [message_obj.get_restriction_text(restriction["additional_data_definition_id"], restriction["condition"]) for restriction in restrictions_to_remove]

    return ResolvedAttributeDeletion(
        label_attribute_pairs=label_attribute_pairs,
        orphan_attributes=orphan_attributes,
        restrictions_to_remove=restrictions_to_remove,
        restriction_text_list=restriction_text_list,
    )


def build_request_body_for_delete_attribute(
    annotation_specs: dict[str, Any],
    *,
    resolved_deletion: ResolvedAttributeDeletion,
    comment: str | None,
) -> dict[str, Any]:
    """
    属性削除用の request body を生成する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        resolved_deletion: 解決済み属性削除対象
        comment: 変更コメント

    Returns:
        Annofab API に渡す request body
    """
    request_body = copy.deepcopy(annotation_specs)
    removed_attribute_ids_by_label_id: dict[str, set[str]] = {}
    for pair in resolved_deletion.label_attribute_pairs:
        removed_attribute_ids_by_label_id.setdefault(pair.label["label_id"], set()).add(pair.attribute["additional_data_definition_id"])

    for label in request_body["labels"]:
        removed_attribute_ids = removed_attribute_ids_by_label_id.get(label["label_id"], set())
        label["additional_data_definitions"] = [attribute_id for attribute_id in label["additional_data_definitions"] if attribute_id not in removed_attribute_ids]

    orphan_attribute_ids = {attribute["additional_data_definition_id"] for attribute in resolved_deletion.orphan_attributes}
    request_body["additionals"] = [attribute for attribute in request_body["additionals"] if attribute["additional_data_definition_id"] not in orphan_attribute_ids]
    request_body["restrictions"] = [restriction for restriction in request_body["restrictions"] if restriction not in resolved_deletion.restrictions_to_remove]
    if comment is None:
        comment = create_comment_for_delete_attribute(resolved_deletion)
    request_body["comment"] = comment
    request_body["last_updated_datetime"] = annotation_specs["updated_datetime"]
    return request_body


class DeleteAttributeMain(CommandLineWithConfirm):
    """
    ラベルから属性を削除する本体処理。
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

    def collect_affecting_annotations(self, resolved_deletion: ResolvedAttributeDeletion) -> list[AffectingAnnotation]:
        """
        削除対象のうち既存アノテーションに影響するものを返す。

        Args:
            resolved_deletion: 解決済み属性削除対象

        Returns:
            既存アノテーションに影響する削除対象一覧
        """
        count_by_label_id: dict[str, int] = {}
        affecting_annotations: list[AffectingAnnotation] = []
        for pair in resolved_deletion.label_attribute_pairs:
            label_id = pair.label["label_id"]
            if label_id not in count_by_label_id:
                count_by_label_id[label_id] = self.count_annotations_by_label(label_id)
            annotation_count = count_by_label_id[label_id]
            if annotation_count == 0:
                continue
            affecting_annotations.append(
                AffectingAnnotation(
                    label_name_en=get_label_name_en(pair.label),
                    attribute_name_en=get_attribute_name_en(pair.attribute),
                    annotation_count=annotation_count,
                )
            )
        return affecting_annotations

    def validate_deletion(self, affecting_annotations: Sequence[AffectingAnnotation]) -> bool:
        """
        属性を削除してよいか検証する。

        Args:
            affecting_annotations: 既存アノテーションに影響する削除対象

        Returns:
            削除してよい場合はTrue、既存アノテーションに影響するため中止する場合はFalse
        """
        if len(affecting_annotations) == 0:
            return True

        message = create_message_for_affecting_annotations(affecting_annotations)
        if self.allow_affecting_annotations:
            logger.warning("既存アノテーションに影響する変更がありますが、オプションで許可されているため、属性を削除します。\n%s", message)
            return True

        logger.warning("既存アノテーションに影響するため、属性の削除を中止しました。\n%s", message)
        return False

    def delete_attribute(
        self,
        *,
        attribute_ids: Collection[str] | None,
        attribute_name_ens: Collection[str] | None,
        label_ids: Sequence[str] | None,
        label_name_ens: Sequence[str] | None,
        all_labels: bool = False,
        comment: str | None = None,
    ) -> bool:
        """
        指定したラベルから属性を削除し、アノテーション仕様を更新する。

        Args:
            attribute_ids: 対象属性ID一覧
            attribute_name_ens: 対象属性英語名一覧
            label_ids: 対象ラベルID一覧
            label_name_ens: 対象ラベル英語名一覧
            all_labels: Trueなら、対象属性が紐づいているすべてのラベルから削除する
            comment: 変更コメント

        Returns:
            更新を実行した場合はTrue、確認で中断した場合はFalse
        """
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        resolved_deletion = resolve_attribute_deletion(
            old_annotation_specs,
            attribute_ids=attribute_ids,
            attribute_name_ens=attribute_name_ens,
            label_ids=label_ids,
            label_name_ens=label_name_ens,
            all_labels=all_labels,
        )
        affecting_annotations = self.collect_affecting_annotations(resolved_deletion)
        if not self.validate_deletion(affecting_annotations):
            return False

        confirm_message = create_confirm_message_for_delete_attribute(resolved_deletion, affecting_annotations=affecting_annotations)
        if not self.confirm_processing(confirm_message):
            return False

        request_body = build_request_body_for_delete_attribute(old_annotation_specs, resolved_deletion=resolved_deletion, comment=comment)
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"{len(resolved_deletion.label_attribute_pairs)} 件のラベル属性関係を削除しました。")
        return True


class DeleteAttribute(CommandLine):
    """
    ラベルから属性を削除するコマンド。
    """

    COMMON_MESSAGE = "annofabcli annotation_specs delete_attribute: error:"

    def main(self) -> None:
        args = self.args

        attribute_ids = get_list_from_args(args.attribute_id) if args.attribute_id is not None else None
        attribute_name_ens = get_list_from_args(args.attribute_name_en) if args.attribute_name_en is not None else None
        label_ids = get_list_from_args(args.label_id) if args.label_id is not None else None
        label_name_ens = get_list_from_args(args.label_name_en) if args.label_name_en is not None else None

        obj = DeleteAttributeMain(
            self.service,
            project_id=args.project_id,
            all_yes=args.yes,
            allow_affecting_annotations=args.allow_affecting_annotations,
        )
        obj.delete_attribute(
            attribute_ids=attribute_ids,
            attribute_name_ens=attribute_name_ens,
            label_ids=label_ids,
            label_name_ens=label_name_ens,
            all_labels=args.all_labels,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    ``delete_attribute`` サブコマンドの引数を定義する。

    Args:
        parser: 引数を追加するArgumentParser
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    attribute_group = parser.add_mutually_exclusive_group(required=True)
    attribute_group.add_argument(
        "--attribute_name_en",
        type=str,
        nargs="+",
        help="削除する属性の英語名。複数指定できます。 ``file://`` を先頭に付けると一覧ファイルを指定できます。",
    )
    attribute_group.add_argument(
        "--attribute_id",
        type=str,
        nargs="+",
        help="削除する属性の属性ID。複数指定できます。 ``file://`` を先頭に付けると一覧ファイルを指定できます。",
    )

    label_group = parser.add_mutually_exclusive_group(required=True)
    label_group.add_argument(
        "--label_name_en",
        type=str,
        nargs="+",
        help="属性を削除する対象ラベルの英語名。複数指定できます。 ``file://`` を先頭に付けると一覧ファイルを指定できます。",
    )
    label_group.add_argument(
        "--label_id",
        type=str,
        nargs="+",
        help="属性を削除する対象ラベルのlabel_id。複数指定できます。 ``file://`` を先頭に付けると一覧ファイルを指定できます。",
    )
    label_group.add_argument(
        "--all_labels",
        action="store_true",
        help="指定した属性が紐づいているすべてのラベルから属性を削除します。",
    )

    parser.add_argument(
        "--allow_affecting_annotations",
        action="store_true",
        help="指定すると、既存アノテーションに影響する変更でも属性を削除します。",
    )
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``delete_attribute`` コマンドのエントリポイント。

    Args:
        args: コマンドライン引数
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteAttribute(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs delete_attribute`` 用のparserを生成する。

    Args:
        subparsers: 親parserのsubparsers

    Returns:
        生成したArgumentParser
    """
    subcommand_name = "delete_attribute"
    subcommand_help = "アノテーション仕様のラベルから属性を削除します。"
    description = "アノテーション仕様のラベルから属性を削除します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
