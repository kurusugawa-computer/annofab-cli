from __future__ import annotations

import argparse
import copy
import logging
from collections.abc import Sequence
from typing import Any

import annofabapi
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor

import annofabcli.common.cli
from annofabcli.annotation_specs.utils import get_attribute_name_en, get_label_name_en, get_target_labels
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login, get_list_from_args
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


def create_comment_from_existing_attribute(attribute_name: str, label_names: Sequence[str]) -> str:
    """
    既存属性を複数ラベルへ追加したときのデフォルトコメントを生成する。

    Args:
        attribute_name: 追加する属性の英語名
        label_names: 追加先ラベルの英語名一覧

    Returns:
        アノテーション仕様変更コメント
    """
    labels_text = ", ".join(label_names)
    return f"以下の既存属性をラベルに追加しました。\n属性名(英語): {attribute_name}\n対象ラベル: {labels_text}"


def get_target_attribute(
    annotation_specs_accessor: AnnotationSpecsAccessor,
    *,
    attribute_id: str | None,
    attribute_name_en: str | None,
) -> dict[str, Any]:
    """
    CLI引数で指定された属性IDまたは属性名から追加対象属性を取得する。

    Args:
        annotation_specs_accessor: アノテーション仕様アクセサ
        attribute_id: 指定された属性ID
        attribute_name_en: 指定された属性英語名

    Returns:
        追加対象属性

    Raises:
        ValueError: 属性指定が不正、属性が見つからない、または属性名が曖昧な場合
    """
    if (attribute_id is None) == (attribute_name_en is None):
        raise ValueError("追加する既存属性は `attribute_id` または `attribute_name_en` のどちらか一方だけ指定してください。")

    if attribute_id is not None:
        return annotation_specs_accessor.get_attribute(attribute_id=attribute_id)

    assert attribute_name_en is not None
    return annotation_specs_accessor.get_attribute(attribute_name=attribute_name_en)


class AddExistingAttributeToLabelsMain(CommandLineWithConfirm):
    """
    既存属性を複数の既存ラベルへ追加する本体処理。
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

    def add_existing_attribute_to_labels(
        self,
        *,
        attribute_id: str | None,
        attribute_name_en: str | None,
        label_ids: Sequence[str] | None,
        label_name_ens: Sequence[str] | None,
        comment: str | None = None,
    ) -> bool:
        """
        既存属性を複数の既存ラベルへ追加して、アノテーション仕様を更新する。

        Args:
            attribute_id: 追加する属性ID
            attribute_name_en: 追加する属性英語名
            label_ids: 追加先ラベルID一覧。未指定時はNone
            label_name_ens: 追加先ラベル英語名一覧。未指定時はNone
            comment: 変更コメント

        Returns:
            追加を実行した場合はTrue、確認で中断した場合はFalse

        Raises:
            ValueError: 入力値や既存アノテーション仕様との整合性が不正な場合
        """
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        annotation_specs_accessor = AnnotationSpecsAccessor(old_annotation_specs)

        target_attribute = get_target_attribute(
            annotation_specs_accessor,
            attribute_id=attribute_id,
            attribute_name_en=attribute_name_en,
        )
        target_labels = get_target_labels(annotation_specs_accessor, label_ids=label_ids, label_name_ens=label_name_ens)

        target_attribute_id = target_attribute["additional_data_definition_id"]
        already_linked_label_names = [get_label_name_en(label) for label in target_labels if target_attribute_id in label["additional_data_definitions"]]
        if already_linked_label_names:
            duplicated_text = ", ".join(sorted(already_linked_label_names))
            raise ValueError(f"指定した属性は既に対象ラベルに紐付いています。 :: {duplicated_text}")

        attribute_name = get_attribute_name_en(target_attribute)
        label_names = [get_label_name_en(label) for label in target_labels]
        confirm_message = f"既存属性名(英語)='{attribute_name}', 属性ID='{target_attribute_id}' を、対象ラベル={label_names} に追加します。よろしいですか？"
        if not self.confirm_processing(confirm_message):
            return False

        request_body = copy.deepcopy(old_annotation_specs)
        target_label_id_set = {label["label_id"] for label in target_labels}
        for label in request_body["labels"]:
            if label["label_id"] in target_label_id_set:
                label["additional_data_definitions"].append(target_attribute_id)

        if comment is None:
            comment = create_comment_from_existing_attribute(attribute_name, label_names)
        request_body["comment"] = comment
        request_body["last_updated_datetime"] = old_annotation_specs["updated_datetime"]
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"既存属性名(英語)='{attribute_name}', 属性ID='{target_attribute_id}' を {len(target_labels)} 件のラベルに追加しました。")
        return True


class AddExistingAttributeToLabels(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs add_existing_attribute_to_labels: error:"

    def main(self) -> None:
        """
        コマンドライン引数を解釈し、既存属性を複数ラベルへ追加する処理を実行する。
        """
        args = self.args

        label_ids = get_list_from_args(args.label_id)
        label_name_ens = get_list_from_args(args.label_name_en)

        obj = AddExistingAttributeToLabelsMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.add_existing_attribute_to_labels(
            attribute_id=args.attribute_id,
            attribute_name_en=args.attribute_name_en,
            label_ids=label_ids,
            label_name_ens=label_name_ens,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    ``add_existing_attribute_to_labels`` サブコマンドの引数を定義する。

    Args:
        parser: 引数を追加するArgumentParser
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    attribute_group = parser.add_mutually_exclusive_group(required=True)
    attribute_group.add_argument(
        "--attribute_name_en",
        type=str,
        help="追加する既存属性の英語名。1個のみ指定できます。",
    )
    attribute_group.add_argument(
        "--attribute_id",
        type=str,
        help="追加する既存属性の属性ID。1個のみ指定できます。",
    )

    label_group = parser.add_mutually_exclusive_group(required=True)
    label_group.add_argument(
        "--label_name_en",
        type=str,
        nargs="+",
        help="属性を追加する対象ラベルの英語名。複数指定できます。 ``file://`` を先頭に付けると一覧ファイルを指定できます。",
    )
    label_group.add_argument(
        "--label_id",
        type=str,
        nargs="+",
        help="属性を追加する対象ラベルのlabel_id。複数指定できます。 ``file://`` を先頭に付けると一覧ファイルを指定できます。",
    )

    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``add_existing_attribute_to_labels`` コマンドのエントリポイント。

    Args:
        args: コマンドライン引数
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    AddExistingAttributeToLabels(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs add_existing_attribute_to_labels`` 用のparserを生成する。

    Args:
        subparsers: 親parserのsubparsers

    Returns:
        生成したArgumentParser
    """
    subcommand_name = "add_existing_attribute_to_labels"
    subcommand_help = "アノテーション仕様の既存属性を複数の既存ラベルへ追加します。"
    description = "アノテーション仕様に既に存在する属性1個を、指定した複数ラベルへ追加します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
