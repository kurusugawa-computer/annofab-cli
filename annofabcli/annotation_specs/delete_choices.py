from __future__ import annotations

import argparse
import copy
import logging
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import annofabapi
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor, get_attribute_name_en, get_choice_name_en

import annofabcli.common.cli
from annofabcli.annotation_specs.attribute_restriction import AttributeRestrictionMessage
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login, get_list_from_args
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedChoiceDeletion:
    """
    選択肢削除対象を既存アノテーション仕様に対して解決した結果。
    """

    target_attribute: Mapping[str, Any]
    """選択肢を削除する対象属性。"""

    choices_to_remove: list[Mapping[str, Any]]
    """削除対象選択肢一覧。"""

    restrictions_to_remove: list[dict[str, Any]]
    """削除対象選択肢を参照するため削除する属性制約一覧。"""

    restriction_text_list: list[str]
    """削除する属性制約のテキスト一覧。"""


@dataclass(frozen=True)
class AffectingAnnotation:
    """
    既存アノテーションに影響する削除対象。
    """

    attribute_name_en: str
    """影響を受ける属性英語名。"""

    choice_name_en: str
    """影響を受ける選択肢英語名。"""

    annotation_count: int
    """対象選択肢のアノテーション数。"""


def get_choice_text(target_attribute: Mapping[str, Any], choice: Mapping[str, Any]) -> str:
    """
    属性と選択肢を表示用テキストに変換する。

    Args:
        target_attribute: 選択肢が属する属性
        choice: 選択肢

    Returns:
        表示用テキスト
    """
    return f"attribute_name_en='{get_attribute_name_en(target_attribute)}', choice_name_en='{get_choice_name_en(choice)}'"


def restriction_references_choice(restriction: Mapping[str, Any], *, attribute_id: str, choice_ids: Collection[str]) -> bool:
    """
    属性制約が指定選択肢を参照しているかどうかを返す。

    Args:
        restriction: 属性制約
        attribute_id: 選択肢が属する属性ID
        choice_ids: 選択肢ID一覧

    Returns:
        属性制約が指定選択肢を参照していればTrue
    """

    def condition_references_choice(current_attribute_id: str, condition: Mapping[str, Any]) -> bool:
        condition_type = condition["_type"]
        if condition_type == "Imply":
            premise = condition["premise"]
            return condition_references_choice(premise["additional_data_definition_id"], premise["condition"]) or condition_references_choice(current_attribute_id, condition["condition"])

        return current_attribute_id == attribute_id and condition_type in ["Equals", "NotEquals"] and condition.get("value") in choice_ids

    return condition_references_choice(restriction["additional_data_definition_id"], restriction["condition"])


def get_target_choices(
    target_attribute: Mapping[str, Any],
    *,
    choice_ids: Sequence[str] | None,
    choice_name_ens: Sequence[str] | None,
) -> list[Mapping[str, Any]]:
    """
    CLI引数で指定された選択肢ID・選択肢名から削除対象選択肢一覧を取得する。

    Args:
        target_attribute: 選択肢を削除する対象属性
        choice_ids: 指定された選択肢ID一覧。未指定時はNone
        choice_name_ens: 指定された選択肢英語名一覧。未指定時はNone

    Returns:
        重複を除いた削除対象選択肢一覧

    Raises:
        ValueError: 引数の指定方法が不正な場合、選択肢が見つからない場合、または選択肢名が曖昧な場合
    """
    if (choice_ids is None) == (choice_name_ens is None):
        raise ValueError("対象選択肢は `choice_id` または `choice_name_en` のどちらか一方だけ指定してください。")

    resolved_choice_ids = [] if choice_ids is None else list(choice_ids)
    resolved_choice_name_ens = [] if choice_name_ens is None else list(choice_name_ens)
    if len(resolved_choice_ids) == 0 and len(resolved_choice_name_ens) == 0:
        raise ValueError("対象選択肢を1件以上指定してください。")

    choices = target_attribute["choices"]
    result: list[Mapping[str, Any]] = []
    result_choice_ids: set[str] = set()
    for choice_id in resolved_choice_ids:
        matched_choices = [choice for choice in choices if choice["choice_id"] == choice_id]
        if len(matched_choices) == 0:
            raise ValueError(f"選択肢情報が見つかりませんでした。 :: choice_id='{choice_id}'")
        choice = matched_choices[0]
        if choice_id not in result_choice_ids:
            result.append(choice)
            result_choice_ids.add(choice_id)

    for choice_name_en in resolved_choice_name_ens:
        matched_choices = [choice for choice in choices if get_choice_name_en(choice) == choice_name_en]
        if len(matched_choices) == 0:
            raise ValueError(f"選択肢情報が見つかりませんでした。 :: choice_name_en='{choice_name_en}'")
        if len(matched_choices) > 1:
            raise ValueError(f"選択肢情報が複数（{len(matched_choices)}件）見つかりました。 :: choice_name_en='{choice_name_en}'")
        choice = matched_choices[0]
        resolved_choice_id = choice["choice_id"]
        if resolved_choice_id not in result_choice_ids:
            result.append(choice)
            result_choice_ids.add(resolved_choice_id)

    return result


def create_comment_for_delete_choices(resolved_deletion: ResolvedChoiceDeletion) -> str:
    """
    選択肢削除時のデフォルトコメントを生成する。

    Args:
        resolved_deletion: 解決済み選択肢削除対象

    Returns:
        アノテーション仕様変更コメント
    """
    lines = ["以下の選択肢を属性から削除しました。"]
    lines.extend(f" * {get_choice_text(resolved_deletion.target_attribute, choice)}" for choice in resolved_deletion.choices_to_remove)
    if resolved_deletion.restriction_text_list:
        lines.extend(("", "以下の属性制約も削除しました。"))
        lines.extend(f" * {restriction_text}" for restriction_text in resolved_deletion.restriction_text_list)
    return "\n".join(lines)


def create_confirm_message_for_delete_choices(
    resolved_deletion: ResolvedChoiceDeletion,
    *,
    affecting_annotations: Sequence[AffectingAnnotation],
) -> str:
    """
    選択肢削除前の確認メッセージを生成する。

    Args:
        resolved_deletion: 解決済み選択肢削除対象
        affecting_annotations: 既存アノテーションに影響する削除対象

    Returns:
        確認メッセージ
    """
    lines = [f"以下の選択肢({len(resolved_deletion.choices_to_remove)}件)を属性から削除します。"]
    lines.extend(f" * {get_choice_text(resolved_deletion.target_attribute, choice)}" for choice in resolved_deletion.choices_to_remove)
    if resolved_deletion.restriction_text_list:
        lines.extend(("", "以下の属性制約も削除します。"))
        lines.extend(f" * {restriction_text}" for restriction_text in resolved_deletion.restriction_text_list)
    if affecting_annotations:
        lines.extend(("", "既存アノテーションへの影響:"))
        lines.extend(f" * attribute_name_en='{affected.attribute_name_en}', choice_name_en='{affected.choice_name_en}': {affected.annotation_count} 件" for affected in affecting_annotations)
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
    attribute_choice_names = [(affected.attribute_name_en, affected.choice_name_en) for affected in affecting_annotations]
    annotation_counts = {(affected.attribute_name_en, affected.choice_name_en): affected.annotation_count for affected in affecting_annotations}
    return f"削除対象の選択肢がアノテーションで使われています。 :: attribute_choice_names_en={attribute_choice_names}, annotation_counts={annotation_counts}"


def resolve_choice_deletion(
    annotation_specs: dict[str, Any],
    *,
    attribute_id: str | None,
    attribute_name_en: str | None,
    choice_ids: Sequence[str] | None,
    choice_name_ens: Sequence[str] | None,
    unsafe_defaults: bool = False,
) -> ResolvedChoiceDeletion:
    """
    選択肢削除対象を既存アノテーション仕様に対して解決する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        attribute_id: 対象属性ID
        attribute_name_en: 対象属性英語名
        choice_ids: 対象選択肢ID一覧
        choice_name_ens: 対象選択肢英語名一覧
        unsafe_defaults: Trueなら、削除対象選択肢がデフォルト値でも削除を許可する

    Returns:
        解決済み選択肢削除対象
    """
    annotation_specs_accessor = AnnotationSpecsAccessor(annotation_specs)
    target_attribute = annotation_specs_accessor.get_attribute(attribute_id=attribute_id, attribute_name=attribute_name_en)
    if target_attribute["type"] not in ["choice", "select"]:
        raise ValueError(f"属性ID='{target_attribute['additional_data_definition_id']}' は選択肢系属性ではありません。")

    target_attribute_choices = target_attribute["choices"]
    assert target_attribute_choices is not None
    choices_to_remove = get_target_choices(target_attribute, choice_ids=choice_ids, choice_name_ens=choice_name_ens)
    if len(target_attribute_choices) - len(choices_to_remove) < 2:
        raise ValueError("削除後の選択肢数が2件未満になるため、選択肢を削除できません。")

    removed_choice_ids = {choice["choice_id"] for choice in choices_to_remove}
    default_choice_id = target_attribute.get("default")
    if default_choice_id in removed_choice_ids and not unsafe_defaults:
        raise ValueError("削除対象の選択肢が属性のデフォルト値に設定されています。削除する場合は `--unsafe_defaults` を指定してください。")

    target_attribute_id = target_attribute["additional_data_definition_id"]
    restrictions_to_remove = [
        restriction for restriction in annotation_specs["restrictions"] if restriction_references_choice(restriction, attribute_id=target_attribute_id, choice_ids=removed_choice_ids)
    ]
    message_obj = AttributeRestrictionMessage(
        labels=annotation_specs["labels"],
        additionals=annotation_specs["additionals"],
        raise_if_not_found=True,
    )
    restriction_text_list = [message_obj.get_restriction_text(restriction["additional_data_definition_id"], restriction["condition"]) for restriction in restrictions_to_remove]
    return ResolvedChoiceDeletion(
        target_attribute=target_attribute,
        choices_to_remove=choices_to_remove,
        restrictions_to_remove=restrictions_to_remove,
        restriction_text_list=restriction_text_list,
    )


def build_request_body_for_delete_choices(
    annotation_specs: dict[str, Any],
    *,
    resolved_deletion: ResolvedChoiceDeletion,
    unsafe_defaults: bool,
    comment: str | None,
) -> dict[str, Any]:
    """
    選択肢削除用の request body を生成する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        resolved_deletion: 解決済み選択肢削除対象
        unsafe_defaults: Trueなら、削除対象選択肢がデフォルト値でもデフォルト値を解除して削除する
        comment: 変更コメント

    Returns:
        Annofab API に渡す request body
    """
    request_body = copy.deepcopy(annotation_specs)
    target_attribute_id = resolved_deletion.target_attribute["additional_data_definition_id"]
    removed_choice_ids = {choice["choice_id"] for choice in resolved_deletion.choices_to_remove}
    for attribute in request_body["additionals"]:
        if attribute["additional_data_definition_id"] != target_attribute_id:
            continue
        attribute["choices"] = [choice for choice in attribute["choices"] if choice["choice_id"] not in removed_choice_ids]
        if unsafe_defaults and attribute.get("default") in removed_choice_ids:
            attribute["default"] = ""
        break

    request_body["restrictions"] = [restriction for restriction in request_body["restrictions"] if restriction not in resolved_deletion.restrictions_to_remove]
    if comment is None:
        comment = create_comment_for_delete_choices(resolved_deletion)
    request_body["comment"] = comment
    request_body["last_updated_datetime"] = annotation_specs["updated_datetime"]
    return request_body


class DeleteChoicesMain(CommandLineWithConfirm):
    """
    選択肢を削除する本体処理。
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

    def count_annotations_by_choice(self, attribute_id: str, choice_id: str) -> int:
        """
        指定選択肢のアノテーション数を返す。

        Args:
            attribute_id: 属性ID
            choice_id: 選択肢ID

        Returns:
            指定選択肢のアノテーション数
        """
        content, _ = self.service.api.get_annotation_list(
            self.project_id,
            query_params={"query": {"attributes": [{"additional_data_definition_id": attribute_id, "choice": choice_id}]}, "limit": 1, "v": "2"},
        )
        return int(content["total_count"])

    def collect_affecting_annotations(self, resolved_deletion: ResolvedChoiceDeletion) -> list[AffectingAnnotation]:
        """
        削除対象のうち既存アノテーションに影響するものを返す。

        Args:
            resolved_deletion: 解決済み選択肢削除対象

        Returns:
            既存アノテーションに影響する削除対象一覧
        """
        target_attribute = resolved_deletion.target_attribute
        attribute_id = target_attribute["additional_data_definition_id"]
        attribute_name_en = get_attribute_name_en(target_attribute)
        affecting_annotations: list[AffectingAnnotation] = []
        for choice in resolved_deletion.choices_to_remove:
            annotation_count = self.count_annotations_by_choice(attribute_id, choice["choice_id"])
            if annotation_count == 0:
                continue
            affecting_annotations.append(
                AffectingAnnotation(
                    attribute_name_en=attribute_name_en,
                    choice_name_en=get_choice_name_en(choice),
                    annotation_count=annotation_count,
                )
            )
        return affecting_annotations

    def validate_deletion(self, affecting_annotations: Sequence[AffectingAnnotation]) -> bool:
        """
        選択肢を削除してよいか検証する。

        Args:
            affecting_annotations: 既存アノテーションに影響する削除対象

        Returns:
            削除してよい場合はTrue、既存アノテーションに影響するため中止する場合はFalse
        """
        if len(affecting_annotations) == 0:
            return True

        message = create_message_for_affecting_annotations(affecting_annotations)
        if self.allow_affecting_annotations:
            logger.warning("既存アノテーションに影響する変更がありますが、オプションで許可されているため、選択肢を削除します。\n%s", message)
            return True

        logger.warning(
            "既存アノテーションに影響するため、選択肢の削除を中止しました。既存アノテーションに影響が出ることを理解した上で削除する場合は、 `--allow_affecting_annotations` を指定してください。\n%s",
            message,
        )
        return False

    def delete_choices(
        self,
        *,
        attribute_id: str | None,
        attribute_name_en: str | None,
        choice_ids: Sequence[str] | None,
        choice_name_ens: Sequence[str] | None,
        unsafe_defaults: bool = False,
        comment: str | None = None,
    ) -> bool:
        """
        指定した選択肢を属性から削除し、アノテーション仕様を更新する。

        Args:
            attribute_id: 対象属性ID
            attribute_name_en: 対象属性英語名
            choice_ids: 対象選択肢ID一覧
            choice_name_ens: 対象選択肢英語名一覧
            unsafe_defaults: Trueなら、削除対象選択肢がデフォルト値でもデフォルト値を解除して削除する
            comment: 変更コメント

        Returns:
            更新を実行した場合はTrue、確認で中断した場合はFalse
        """
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        resolved_deletion = resolve_choice_deletion(
            old_annotation_specs,
            attribute_id=attribute_id,
            attribute_name_en=attribute_name_en,
            choice_ids=choice_ids,
            choice_name_ens=choice_name_ens,
            unsafe_defaults=unsafe_defaults,
        )
        affecting_annotations = self.collect_affecting_annotations(resolved_deletion)
        if not self.validate_deletion(affecting_annotations):
            return False

        confirm_message = create_confirm_message_for_delete_choices(resolved_deletion, affecting_annotations=affecting_annotations)
        if not self.confirm_processing(confirm_message):
            return False

        request_body = build_request_body_for_delete_choices(old_annotation_specs, resolved_deletion=resolved_deletion, unsafe_defaults=unsafe_defaults, comment=comment)
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"{len(resolved_deletion.choices_to_remove)} 件の選択肢を削除しました。")
        return True


class DeleteChoices(CommandLine):
    """
    選択肢を削除するコマンド。
    """

    COMMON_MESSAGE = "annofabcli annotation_specs delete_choices: error:"

    def main(self) -> None:
        args = self.args

        choice_ids = get_list_from_args(args.choice_id) if args.choice_id is not None else None
        choice_name_ens = get_list_from_args(args.choice_name_en) if args.choice_name_en is not None else None

        obj = DeleteChoicesMain(
            self.service,
            project_id=args.project_id,
            all_yes=args.yes,
            allow_affecting_annotations=args.allow_affecting_annotations,
        )
        obj.delete_choices(
            attribute_id=args.attribute_id,
            attribute_name_en=args.attribute_name_en,
            choice_ids=choice_ids,
            choice_name_ens=choice_name_ens,
            unsafe_defaults=args.unsafe_defaults,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    ``delete_choices`` サブコマンドの引数を定義する。

    Args:
        parser: 引数を追加するArgumentParser
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    attribute_group = parser.add_mutually_exclusive_group(required=True)
    attribute_group.add_argument("--attribute_name_en", type=str, help="選択肢を削除する対象属性の英語名。")
    attribute_group.add_argument("--attribute_id", type=str, help="選択肢を削除する対象属性の属性ID。")

    choice_group = parser.add_mutually_exclusive_group(required=True)
    choice_group.add_argument(
        "--choice_name_en",
        type=str,
        nargs="+",
        help="削除する選択肢の英語名。複数指定できます。 ``file://`` を先頭に付けると一覧ファイルを指定できます。",
    )
    choice_group.add_argument(
        "--choice_id",
        type=str,
        nargs="+",
        help="削除する選択肢のchoice_id。複数指定できます。 ``file://`` を先頭に付けると一覧ファイルを指定できます。",
    )
    parser.add_argument(
        "--allow_affecting_annotations",
        action="store_true",
        help="指定すると、既存アノテーションに影響する変更でも選択肢を削除します。",
    )
    parser.add_argument(
        "--unsafe_defaults",
        action="store_true",
        help="指定すると、削除対象選択肢が属性のデフォルト値に設定されている場合でも、デフォルト値を解除して選択肢を削除します。",
    )
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``delete_choices`` コマンドのエントリポイント。

    Args:
        args: コマンドライン引数
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteChoices(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs delete_choices`` 用のparserを生成する。

    Args:
        subparsers: 親parserのsubparsers

    Returns:
        生成したArgumentParser
    """
    subcommand_name = "delete_choices"
    subcommand_help = "アノテーション仕様の選択肢系属性から選択肢を削除します。"
    description = "アノテーション仕様の選択肢系属性から選択肢を複数件削除します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
