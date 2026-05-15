from __future__ import annotations

import argparse
import copy
import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any

import annofabapi
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

import annofabcli.common.cli
from annofabcli.annotation_specs.add_attribute import AttributeType, create_attribute
from annofabcli.annotation_specs.utils import get_attribute_name_en, get_label_name_en, get_target_labels
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login, get_json_from_args
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import duplicated_set

logger = logging.getLogger(__name__)


class AttributeInput(BaseModel):
    """
    コマンドラインから受け取った属性1件分の入力情報。
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="forbid")

    attribute_type: AttributeType
    """属性の種類。"""

    attribute_name_en: str
    """属性の英語名。"""

    label_name_ens: list[str] | None = Field(default=None, alias="label_name_en")
    """属性を紐付ける対象ラベルの英語名一覧。"""

    label_ids: list[str] | None = Field(default=None, alias="label_id")
    """属性を紐付ける対象ラベルのlabel_id一覧。"""

    attribute_name_ja: str | None = None
    """属性の日本語名。"""

    attribute_id: str | None = None
    """属性ID。未指定の場合はUUIDv4を自動生成する。"""

    @field_validator("label_name_ens", "label_ids")
    @classmethod
    def validate_label_list(cls, value: list[str] | None) -> list[str] | None:
        """
        ラベル名一覧またはlabel_id一覧を検証する。

        Args:
            value: 検証対象の一覧

        Returns:
            検証済みの一覧

        Raises:
            ValueError: 空配列または重複を含む場合
        """
        if value is None:
            return None
        if len(value) == 0:
            raise ValueError("1件以上指定してください。")

        duplicated_values = duplicated_set(value)
        if duplicated_values:
            duplicated_text = ", ".join(sorted(duplicated_values))
            raise ValueError(f"重複があります。 :: {duplicated_text}")
        return value

    @model_validator(mode="after")
    def validate_label_selector(self) -> AttributeInput:
        """
        ラベル選択条件の排他・必須条件を検証する。

        Returns:
            検証済みのモデル自身

        Raises:
            ValueError: `label_name_en` と `label_id` の指定条件が不正な場合
        """
        if self.label_name_ens is None and self.label_ids is None:
            raise ValueError("`label_name_en` または `label_id` を指定してください。")
        if self.label_name_ens is not None and self.label_ids is not None:
            raise ValueError("`label_name_en` と `label_id` を同時に指定できません。")
        return self


class ResolvedAttributeInput(BaseModel):
    """
    既存アノテーション仕様に対して解決済みの属性入力情報。
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    attribute_input: AttributeInput
    """元の属性入力。"""

    target_labels: Sequence[Mapping[str, Any]]
    """属性を追加する対象ラベル一覧。"""

    new_attribute: dict[str, Any]
    """追加するAnnofab API向け属性オブジェクト。"""


def parse_attribute_input_from_dict(data: dict[str, Any], *, index: int) -> AttributeInput:
    """
    JSONオブジェクト1件を属性入力に変換する。

    Args:
        data: 属性情報を表すdict
        index: エラーメッセージ用の1始まりの位置

    Returns:
        変換後の属性入力

    Raises:
        ValueError: 入力値が不正な場合
    """
    try:
        return AttributeInput.model_validate(data)
    except ValidationError as e:
        raise ValueError(f"{index}件目の属性の入力値が不正です。 :: {e}") from e


def read_attributes_json(target: str) -> list[AttributeInput]:
    """
    ``--attribute_json`` で指定されたJSONから属性一覧を読み込む。

    Args:
        target: JSON文字列または ``file://`` 付きファイル指定

    Returns:
        属性入力一覧

    Raises:
        TypeError: JSON全体が配列でない、または配列要素がオブジェクトでない場合
        ValueError: 各属性オブジェクトの必須項目が不足している場合
    """
    raw_data = get_json_from_args(target)
    if not isinstance(raw_data, list):
        raise TypeError("`--attribute_json` には属性情報の配列を指定してください。")

    result = []
    for index, attribute_data in enumerate(raw_data, start=1):
        if not isinstance(attribute_data, dict):
            raise TypeError(f"{index}件目の属性がオブジェクト形式ではありません。")
        result.append(parse_attribute_input_from_dict(attribute_data, index=index))
    return result


def validate_attribute_inputs(attribute_inputs: Sequence[AttributeInput]) -> None:
    """
    追加する属性一覧の入力値を検証する。

    Args:
        attribute_inputs: 追加する属性一覧

    Raises:
        ValueError: 件数不足または重複がある場合
    """
    if len(attribute_inputs) == 0:
        raise ValueError("追加する属性を1件以上指定してください。")

    duplicated_attribute_ids = duplicated_set([attribute.attribute_id for attribute in attribute_inputs if attribute.attribute_id is not None])
    if duplicated_attribute_ids:
        duplicated_text = ", ".join(sorted(duplicated_attribute_ids))
        raise ValueError(f"入力された属性に重複した `attribute_id` があります。 :: {duplicated_text}")

    duplicated_attribute_names = duplicated_set([attribute.attribute_name_en for attribute in attribute_inputs])
    if duplicated_attribute_names:
        duplicated_text = ", ".join(sorted(duplicated_attribute_names))
        raise ValueError(f"入力された属性名(英語)に重複があります。 :: {duplicated_text}")


def create_comment_from_attributes(attribute_inputs: Sequence[AttributeInput]) -> str:
    """
    複数属性追加時のデフォルトコメントを生成する。

    Args:
        attribute_inputs: 追加する属性一覧

    Returns:
        アノテーション仕様変更コメント
    """
    attribute_text = ", ".join(attribute.attribute_name_en for attribute in attribute_inputs)
    return f"以下の属性を追加しました。\n属性名(英語): {attribute_text}"


def validate_new_attribute_input(
    additionals: Sequence[dict[str, Any]],
    *,
    attribute_id: str,
    attribute_name_en: str,
) -> None:
    """
    追加予定の属性ID・属性英語名が既存属性と衝突しないか検証する。

    Args:
        additionals: 既存の属性一覧
        attribute_id: 追加予定の属性ID
        attribute_name_en: 追加予定の属性英語名

    Raises:
        ValueError: 属性IDまたは属性英語名が既存属性と重複する場合
    """
    if any(additional["additional_data_definition_id"] == attribute_id for additional in additionals):
        raise ValueError(f"属性ID='{attribute_id}' の属性は既に存在します。")

    duplicated_name_attribute_ids = [additional["additional_data_definition_id"] for additional in additionals if get_attribute_name_en(additional) == attribute_name_en]
    if duplicated_name_attribute_ids:
        duplicated_text = ", ".join(duplicated_name_attribute_ids)
        raise ValueError(f"属性名(英語)='{attribute_name_en}' の属性は既に存在します。 :: {duplicated_text}")


class AddAttributesMain(CommandLineWithConfirm):
    """
    複数の非選択肢系属性をアノテーション仕様へ追加する本体処理。
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

    def _resolve_attribute_inputs(
        self,
        annotation_specs_accessor: AnnotationSpecsAccessor,
        *,
        additionals: Sequence[dict[str, Any]],
        attribute_inputs: Sequence[AttributeInput],
    ) -> list[ResolvedAttributeInput]:
        """
        入力された属性一覧を既存アノテーション仕様に対して解決する。

        Args:
            annotation_specs_accessor: アノテーション仕様アクセサ
            additionals: 既存属性一覧
            attribute_inputs: 入力された属性一覧

        Returns:
            解決済み属性一覧
        """
        resolved_inputs = []
        for attribute_input in attribute_inputs:
            target_labels = get_target_labels(
                annotation_specs_accessor,
                label_ids=attribute_input.label_ids,
                label_name_ens=attribute_input.label_name_ens,
            )
            new_attribute = create_attribute(
                attribute_type=attribute_input.attribute_type,
                attribute_name_en=attribute_input.attribute_name_en,
                attribute_name_ja=attribute_input.attribute_name_ja,
                attribute_id=attribute_input.attribute_id,
            )
            validate_new_attribute_input(
                additionals,
                attribute_id=new_attribute["additional_data_definition_id"],
                attribute_name_en=attribute_input.attribute_name_en,
            )
            resolved_inputs.append(
                ResolvedAttributeInput(
                    attribute_input=attribute_input,
                    target_labels=target_labels,
                    new_attribute=new_attribute,
                )
            )
        return resolved_inputs

    def add_attributes(
        self,
        *,
        attribute_inputs: Sequence[AttributeInput],
        comment: str | None = None,
    ) -> bool:
        """
        複数の非選択肢系属性を追加し、指定ラベルへ紐付けてアノテーション仕様を更新する。

        Args:
            attribute_inputs: 追加する属性一覧
            comment: 変更コメント

        Returns:
            追加を実行した場合はTrue、確認で中断した場合はFalse
        """
        validate_attribute_inputs(attribute_inputs)

        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        annotation_specs_accessor = AnnotationSpecsAccessor(old_annotation_specs)
        resolved_inputs = self._resolve_attribute_inputs(
            annotation_specs_accessor,
            additionals=old_annotation_specs["additionals"],
            attribute_inputs=attribute_inputs,
        )

        input_attribute_name_ens = [attribute.attribute_name_en for attribute in attribute_inputs]
        confirm_message = f"{len(attribute_inputs)} 件の属性を追加します。 attribute_name_ens={input_attribute_name_ens}。よろしいですか？"
        if not self.confirm_processing(confirm_message):
            return False

        request_body = copy.deepcopy(old_annotation_specs)
        labels_by_id = {label["label_id"]: label for label in request_body["labels"]}
        for resolved_input in resolved_inputs:
            request_body["additionals"].append(resolved_input.new_attribute)
            target_label_names = [get_label_name_en(label) for label in resolved_input.target_labels]
            logger.debug(
                f"属性名(英語)='{resolved_input.attribute_input.attribute_name_en}', 属性ID='{resolved_input.new_attribute['additional_data_definition_id']}', "
                f"対象ラベル={target_label_names} を追加します。"
            )
            for target_label in resolved_input.target_labels:
                labels_by_id[target_label["label_id"]]["additional_data_definitions"].append(resolved_input.new_attribute["additional_data_definition_id"])

        if comment is None:
            comment = create_comment_from_attributes(attribute_inputs)
        request_body["comment"] = comment
        request_body["last_updated_datetime"] = old_annotation_specs["updated_datetime"]
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"{len(attribute_inputs)} 件の属性を追加しました。 :: attribute_name_ens={input_attribute_name_ens}")
        return True


class AddAttributes(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs add_attributes: error:"

    def main(self) -> None:
        """
        コマンドライン引数を解釈し、複数属性追加処理を実行する。
        """
        args = self.args
        attribute_inputs = read_attributes_json(args.attribute_json)

        obj = AddAttributesMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.add_attributes(
            attribute_inputs=attribute_inputs,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    ``add_attributes`` サブコマンドの引数を定義する。

    Args:
        parser: 引数を追加するArgumentParser
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    sample_json = [
        {
            "attribute_type": "flag",
            "attribute_name_en": "occluded",
            "attribute_name_ja": "隠れ",
            "label_name_en": ["car", "bus"],
        },
        {
            "attribute_type": "text",
            "attribute_name_en": "comment2",
            "label_id": ["40f7796b-3722-4eed-9c0c-04a27f9165d2"],
        },
    ]
    parser.add_argument(
        "--attribute_json",
        type=str,
        required=True,
        help=f"追加する属性情報のJSON配列を指定します。 ``file://`` を先頭に付けるとJSON形式のファイルを指定できます。\n(例) ``{json.dumps(sample_json, ensure_ascii=False)}``",
    )
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``add_attributes`` コマンドのエントリポイント。

    Args:
        args: コマンドライン引数
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    AddAttributes(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs add_attributes`` 用のparserを生成する。

    Args:
        subparsers: 親parserのsubparsers

    Returns:
        生成したArgumentParser
    """
    subcommand_name = "add_attributes"
    subcommand_help = "アノテーション仕様に複数の非選択肢系属性を追加します。"
    description = "アノテーション仕様に複数の非選択肢系属性を追加します。選択肢系属性の追加は ``add_choice_attribute`` コマンドを使用してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
