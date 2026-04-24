from __future__ import annotations

import argparse
import copy
import logging
from collections.abc import Sequence
from typing import Any

import annofabapi
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor

import annofabcli.common.cli
from annofabcli.annotation_specs.add_choice_attribute import get_attribute_name_en, get_label_name_en, get_target_labels
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login, get_list_from_args
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import duplicated_set

logger = logging.getLogger(__name__)


def create_comment_from_existing_attributes(label_name: str, attribute_names: Sequence[str]) -> str:
    """
    既存属性をラベルへ追加したときのデフォルトコメントを生成する。

    Args:
        label_name: 追加先ラベルの英語名
        attribute_names: 追加する属性の英語名一覧

    Returns:
        アノテーション仕様変更コメント
    """
    attributes_text = ", ".join(attribute_names)
    return f"以下の既存属性をラベルに追加しました。\n対象ラベル: {label_name}\n追加した属性: {attributes_text}"


def get_target_attributes(
    annotation_specs_accessor: AnnotationSpecsAccessor,
    *,
    attribute_ids: Sequence[str],
    attribute_name_ens: Sequence[str],
) -> list[dict[str, Any]]:
    """
    CLI引数で指定された属性ID・属性名から追加対象属性一覧を取得する。

    Args:
        annotation_specs_accessor: アノテーション仕様アクセサ
        attribute_ids: 指定された属性ID一覧
        attribute_name_ens: 指定された属性英語名一覧

    Returns:
        追加対象属性一覧

    Raises:
        ValueError: 属性が見つからない、属性名が曖昧、または入力に重複がある場合
    """
    attribute_id_list = list(attribute_ids)
    attribute_name_en_list = list(attribute_name_ens)

    duplicated_attribute_ids: set[str] = duplicated_set(attribute_id_list)
    if duplicated_attribute_ids:
        duplicated_text = ", ".join(sorted(duplicated_attribute_ids))
        raise ValueError(f"入力された属性IDに重複があります。 :: {duplicated_text}")

    duplicated_attribute_names: set[str] = duplicated_set(attribute_name_en_list)
    if duplicated_attribute_names:
        duplicated_text = ", ".join(sorted(duplicated_attribute_names))
        raise ValueError(f"入力された属性名(英語)に重複があります。 :: {duplicated_text}")

    result = []
    result_attribute_ids: set[str] = set()

    for attribute_id in attribute_id_list:
        attribute = annotation_specs_accessor.get_attribute(attribute_id=attribute_id)
        resolved_attribute_id = attribute["additional_data_definition_id"]
        if resolved_attribute_id not in result_attribute_ids:
            result.append(attribute)
            result_attribute_ids.add(resolved_attribute_id)

    for attribute_name_en in attribute_name_en_list:
        attribute = annotation_specs_accessor.get_attribute(attribute_name=attribute_name_en)
        resolved_attribute_id = attribute["additional_data_definition_id"]
        if resolved_attribute_id not in result_attribute_ids:
            result.append(attribute)
            result_attribute_ids.add(resolved_attribute_id)

    if len(result) == 0:
        raise ValueError("追加する既存属性を1件以上指定してください。")
    return result


class AddExistingAttributeMain(CommandLineWithConfirm):
    """
    既存属性を既存ラベルへ追加する本体処理。
    """

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

    def add_existing_attribute(
        self,
        *,
        label_ids: Sequence[str],
        label_name_ens: Sequence[str],
        attribute_ids: Sequence[str],
        attribute_name_ens: Sequence[str],
        comment: str | None = None,
    ) -> bool:
        """
        既存属性を既存ラベルへ追加して、アノテーション仕様を更新する。

        Args:
            label_ids: 追加先ラベルID一覧
            label_name_ens: 追加先ラベル英語名一覧
            attribute_ids: 追加する属性ID一覧
            attribute_name_ens: 追加する属性英語名一覧
            comment: 変更コメント

        Returns:
            追加を実行した場合はTrue、確認で中断した場合はFalse

        Raises:
            ValueError: 入力値や既存アノテーション仕様との整合性が不正な場合
        """
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        annotation_specs_accessor = AnnotationSpecsAccessor(old_annotation_specs)

        target_labels = get_target_labels(annotation_specs_accessor, label_ids=label_ids, label_name_ens=label_name_ens)
        if len(target_labels) != 1:
            raise ValueError("追加先のラベルは1件だけ指定してください。")
        target_label = target_labels[0]

        target_attributes = get_target_attributes(
            annotation_specs_accessor,
            attribute_ids=attribute_ids,
            attribute_name_ens=attribute_name_ens,
        )

        existing_attribute_ids = set(target_label["additional_data_definitions"])
        duplicated_target_attributes = [attribute["additional_data_definition_id"] for attribute in target_attributes if attribute["additional_data_definition_id"] in existing_attribute_ids]
        if duplicated_target_attributes:
            duplicated_text = ", ".join(sorted(duplicated_target_attributes))
            raise ValueError(f"対象ラベルには既に指定した属性が紐付いています。 :: {duplicated_text}")

        label_name = get_label_name_en(target_label)
        attribute_names = [get_attribute_name_en(attribute) for attribute in target_attributes]
        attribute_ids_to_add = [attribute["additional_data_definition_id"] for attribute in target_attributes]
        confirm_message = f"ラベル名(英語)='{label_name}' に、既存属性 {attribute_names} (attribute_id={attribute_ids_to_add}) を追加します。よろしいですか？"
        if not self.confirm_processing(confirm_message):
            return False

        request_body = copy.deepcopy(old_annotation_specs)
        for label in request_body["labels"]:
            if label["label_id"] == target_label["label_id"]:
                label["additional_data_definitions"].extend(attribute_ids_to_add)
                break

        if comment is None:
            comment = create_comment_from_existing_attributes(label_name, attribute_names)
        request_body["comment"] = comment
        request_body["last_updated_datetime"] = old_annotation_specs["updated_datetime"]
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"ラベル名(英語)='{label_name}' に {len(target_attributes)} 件の既存属性を追加しました。")
        return True


class AddExistingAttribute(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs add_existing_attribute: error:"

    def main(self) -> None:
        """
        コマンドライン引数を解釈し、既存属性追加処理を実行する。
        """
        args = self.args

        label_ids = get_list_from_args(args.label_id)
        label_name_ens = get_list_from_args(args.label_name_en)
        attribute_ids = get_list_from_args(args.attribute_id)
        attribute_name_ens = get_list_from_args(args.attribute_name_en)

        obj = AddExistingAttributeMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.add_existing_attribute(
            label_ids=label_ids,
            label_name_ens=label_name_ens,
            attribute_ids=attribute_ids,
            attribute_name_ens=attribute_name_ens,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    ``add_existing_attribute`` サブコマンドの引数を定義する。

    Args:
        parser: 引数を追加するArgumentParser
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    label_group = parser.add_mutually_exclusive_group(required=True)
    label_group.add_argument(
        "--label_name_en",
        type=str,
        nargs=1,
        help="属性を追加する対象ラベルの英語名。 ``file://`` を先頭に付けると一覧ファイルを指定できますが、指定できるラベルは1件だけです。",
    )
    label_group.add_argument(
        "--label_id",
        type=str,
        nargs=1,
        help="属性を追加する対象ラベルのlabel_id。 ``file://`` を先頭に付けると一覧ファイルを指定できますが、指定できるラベルは1件だけです。",
    )

    attribute_group = parser.add_mutually_exclusive_group(required=True)
    attribute_group.add_argument(
        "--attribute_name_en",
        type=str,
        nargs="+",
        help="追加する既存属性の英語名。複数指定できます。 ``file://`` を先頭に付けると一覧ファイルを指定できます。",
    )
    attribute_group.add_argument(
        "--attribute_id",
        type=str,
        nargs="+",
        help="追加する既存属性の属性ID。複数指定できます。 ``file://`` を先頭に付けると一覧ファイルを指定できます。",
    )

    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更時に指定できるコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``add_existing_attribute`` コマンドのエントリポイント。

    Args:
        args: コマンドライン引数
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    AddExistingAttribute(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs add_existing_attribute`` 用のparserを生成する。

    Args:
        subparsers: 親parserのsubparsers

    Returns:
        生成したArgumentParser
    """
    subcommand_name = "add_existing_attribute"
    subcommand_help = "アノテーション仕様の既存属性を既存ラベルへ追加します。"
    description = "アノテーション仕様に既に存在する属性を、指定したラベルへ追加します。属性定義そのものは新規作成しません。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
