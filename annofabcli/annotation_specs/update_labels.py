from __future__ import annotations

import argparse
import copy
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import annofabapi
import pandas
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor, get_label_name_en

import annofabcli.common.cli
from annofabcli.annotation_specs.add_labels import parse_field_values_in_csv, parse_keybind_in_csv
from annofabcli.annotation_specs.color import hex_to_rgb
from annofabcli.common.annofab.annotation_specs import keybind_to_api_keybind, validate_keybind_input
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
    get_json_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import duplicated_set

logger = logging.getLogger(__name__)

FieldValuesOperation = Literal["merge", "replace"]
"""field_values の更新方法。"""

FIELD_VALUES_OPERATIONS: list[FieldValuesOperation] = ["merge", "replace"]
"""``field_values_operation`` に指定できる値。"""

LABEL_JSON_KEYS = {
    "label_id",
    "label_name_en",
    "label_name_ja",
    "color",
    "keybind",
    "field_values",
    "field_values_operation",
}
"""``--label_json`` の各要素に指定できるキー。"""


@dataclass(frozen=True)
class LabelUpdateInput:
    """
    コマンドラインから受け取ったラベル1件分の更新情報。
    """

    label_id: str | None = None
    """更新対象ラベルID。"""

    label_name_en: str | None = None
    """更新対象ラベルの英語名。"""

    label_name_ja: str | None = None
    """更新後のラベル日本語名。"""

    color: str | None = None
    """更新後の ``#RRGGBB`` 形式のカラーコード。"""

    keybind: dict[str, Any] | None = None
    """更新後のkeybind。"""

    field_values: dict[str, Any] | None = None
    """更新するfield_values。"""

    field_values_operation: FieldValuesOperation | None = None
    """field_values の更新方法。"""


@dataclass(frozen=True)
class ResolvedLabelUpdateInput:
    """
    既存アノテーション仕様に対して解決済みのラベル更新情報。
    """

    target_label: Mapping[str, Any]
    """更新対象ラベル。"""

    label_update_input: LabelUpdateInput
    """更新情報。"""


def validate_field_values_operation(value: object, *, index: int) -> FieldValuesOperation:
    """
    ``field_values_operation`` を検証する。

    Args:
        value: 入力された値
        index: エラーメッセージ用の1始まりの位置

    Returns:
        検証済みのfield_values更新方法

    Raises:
        ValueError: 指定値が不正な場合
    """
    if value not in FIELD_VALUES_OPERATIONS:
        raise ValueError(f"{index}件目のラベルの `field_values_operation` に不正な値が指定されています。")
    return value


def validate_label_update_input(label_update_input: LabelUpdateInput, *, index: int) -> None:
    """
    ラベル更新入力を検証する。

    Args:
        label_update_input: ラベル更新入力
        index: エラーメッセージ用の1始まりの位置

    Raises:
        ValueError: 入力値の組み合わせが不正な場合
    """
    if (label_update_input.label_id is None) == (label_update_input.label_name_en is None):
        raise ValueError(f"{index}件目のラベルは `label_id` または `label_name_en` のどちらか一方だけ指定してください。")

    has_field_values_update = label_update_input.field_values is not None or label_update_input.field_values_operation is not None
    has_update_field = any(
        [
            label_update_input.label_name_ja is not None,
            label_update_input.color is not None,
            label_update_input.keybind is not None,
            has_field_values_update,
        ]
    )
    if not has_update_field:
        raise ValueError(f"{index}件目のラベルに更新するフィールドが指定されていません。")

    if label_update_input.field_values is None and label_update_input.field_values_operation == "merge":
        raise ValueError(f"{index}件目のラベルは `field_values_operation='merge'` の場合、`field_values` が必要です。")


def parse_label_update_input_from_dict(data: dict[str, Any], *, index: int) -> LabelUpdateInput:
    """
    JSONオブジェクト1件をラベル更新入力に変換する。

    Args:
        data: ラベル更新情報を表すdict
        index: エラーメッセージ用の1始まりの位置

    Returns:
        変換後のラベル更新入力

    Raises:
        ValueError: 不正なキーや値が指定されている場合
    """
    unexpected_keys = set(data) - LABEL_JSON_KEYS
    if unexpected_keys:
        raise ValueError(f"{index}件目のラベルに指定できないキーがあります。 :: {sorted(unexpected_keys)}")

    field_values = data.get("field_values")
    field_values_operation = data.get("field_values_operation")
    label_update_input = LabelUpdateInput(
        label_id=data.get("label_id"),
        label_name_en=data.get("label_name_en"),
        label_name_ja=data.get("label_name_ja"),
        color=data.get("color"),
        keybind=None if data.get("keybind") is None else validate_keybind_input(data["keybind"]),
        field_values=None if field_values is None else validate_field_values_input(field_values),
        field_values_operation=None if field_values_operation is None else validate_field_values_operation(field_values_operation, index=index),
    )
    validate_label_update_input(label_update_input, index=index)
    return label_update_input


def parse_field_values_operation_in_csv(value: object, *, index: int) -> FieldValuesOperation | None:
    """
    CSVの ``field_values_operation`` 列を変換する。

    Args:
        value: CSVセルの値
        index: エラーメッセージ用の1始まりの位置

    Returns:
        変換後のfield_values更新方法
    """
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    if value == "":
        return None
    return validate_field_values_operation(value, index=index)


def validate_field_values_input(field_values: object) -> dict[str, Any]:
    """
    ``field_values`` を検証する。

    Args:
        field_values: JSONから読み込んだ値

    Returns:
        検証済みのfield_values

    Raises:
        TypeError: JSONオブジェクトでない場合
    """
    if not isinstance(field_values, dict):
        raise TypeError("`field_values` にはJSONオブジェクトを指定してください。")
    return cast(dict[str, Any], field_values)


def read_labels_json(target: str) -> list[LabelUpdateInput]:
    """
    ``--label_json`` で指定されたJSONからラベル更新一覧を読み込む。

    Args:
        target: JSON文字列または ``file://`` 付きファイル指定

    Returns:
        ラベル更新入力の一覧
    """
    raw_data = get_json_from_args(target)
    if not isinstance(raw_data, list):
        raise TypeError("`--label_json` にはラベル更新情報の配列を指定してください。")

    result = []
    for index, label_data in enumerate(raw_data, start=1):
        if not isinstance(label_data, dict):
            raise TypeError(f"{index}件目のラベルがオブジェクト形式ではありません。")
        result.append(parse_label_update_input_from_dict(label_data, index=index))
    return result


def read_labels_csv(csv_path: Path) -> list[LabelUpdateInput]:
    """
    ``--label_csv`` で指定されたCSVからラベル更新一覧を読み込む。

    Args:
        csv_path: CSVファイルパス

    Returns:
        ラベル更新入力の一覧

    Raises:
        ValueError: CSV読み込みに失敗した場合、または入力値が不正な場合
    """
    try:
        df = pandas.read_csv(
            csv_path,
            dtype={
                "label_id": "string",
                "label_name_en": "string",
                "label_name_ja": "string",
                "color": "string",
                "keybind": "string",
                "field_values": "string",
                "field_values_operation": "string",
            },
        )
    except Exception as e:
        raise ValueError(f"`--label_csv` の読み込みに失敗しました。 :: {e}") from e

    unexpected_columns = set(df.columns) - LABEL_JSON_KEYS
    if unexpected_columns:
        raise ValueError(f"`--label_csv` に指定できない列があります。 :: {sorted(unexpected_columns)}")

    result = []
    for index, row in enumerate(df.to_dict(orient="records"), start=1):
        label_update_input = LabelUpdateInput(
            label_id=row.get("label_id"),
            label_name_en=row.get("label_name_en"),
            label_name_ja=row.get("label_name_ja"),
            color=row.get("color"),
            keybind=parse_keybind_in_csv(row.get("keybind"), index=index),
            field_values=parse_field_values_in_csv(row.get("field_values"), index=index),
            field_values_operation=parse_field_values_operation_in_csv(row.get("field_values_operation"), index=index),
        )
        validate_label_update_input(label_update_input, index=index)
        result.append(label_update_input)
    return result


def validate_label_update_inputs(label_update_inputs: Sequence[LabelUpdateInput]) -> None:
    """
    ラベル更新入力一覧を検証する。

    Args:
        label_update_inputs: ラベル更新入力一覧

    Raises:
        ValueError: 件数不足または対象指定に重複がある場合
    """
    if len(label_update_inputs) == 0:
        raise ValueError("更新するラベルを1件以上指定してください。")

    duplicated_label_ids = duplicated_set([label.label_id for label in label_update_inputs if label.label_id is not None])
    if duplicated_label_ids:
        duplicated_text = ", ".join(sorted(duplicated_label_ids))
        raise ValueError(f"入力されたラベルに重複した `label_id` があります。 :: {duplicated_text}")

    duplicated_label_names = duplicated_set([label.label_name_en for label in label_update_inputs if label.label_name_en is not None])
    if duplicated_label_names:
        duplicated_text = ", ".join(sorted(duplicated_label_names))
        raise ValueError(f"入力されたラベル名(英語)に重複があります。 :: {duplicated_text}")


def resolve_label_update_inputs(
    annotation_specs: dict[str, Any],
    *,
    label_update_inputs: Sequence[LabelUpdateInput],
) -> list[ResolvedLabelUpdateInput]:
    """
    ラベル更新入力一覧を既存アノテーション仕様に対して解決する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        label_update_inputs: ラベル更新入力一覧

    Returns:
        解決済みラベル更新入力一覧

    Raises:
        ValueError: 同じ既存ラベルを複数回更新しようとした場合
    """
    validate_label_update_inputs(label_update_inputs)
    annotation_specs_accessor = AnnotationSpecsAccessor(annotation_specs)

    result = []
    resolved_label_ids: set[str] = set()
    for label_update_input in label_update_inputs:
        if label_update_input.label_id is not None:
            target_label = annotation_specs_accessor.get_label(label_id=label_update_input.label_id)
        else:
            assert label_update_input.label_name_en is not None
            target_label = annotation_specs_accessor.get_label(label_name=label_update_input.label_name_en)

        target_label_id = target_label["label_id"]
        if target_label_id in resolved_label_ids:
            raise ValueError(f"同じラベルを複数回更新しようとしています。 :: label_id='{target_label_id}'")
        resolved_label_ids.add(target_label_id)
        result.append(ResolvedLabelUpdateInput(target_label=target_label, label_update_input=label_update_input))

    return result


def update_label_name_ja(label: dict[str, Any], label_name_ja: str) -> None:
    """
    ラベル日本語名を更新する。

    Args:
        label: 更新対象ラベル
        label_name_ja: 更新後のラベル日本語名
    """
    messages = label["label_name"]["messages"]
    for message in messages:
        if message["lang"] == "ja-JP":
            message["message"] = label_name_ja
            return

    messages.append({"lang": "ja-JP", "message": label_name_ja})


def update_label_field_values(label: dict[str, Any], label_update_input: LabelUpdateInput) -> None:
    """
    ラベルのfield_valuesを更新する。

    Args:
        label: 更新対象ラベル
        label_update_input: ラベル更新入力
    """
    if label_update_input.field_values is None and label_update_input.field_values_operation is None:
        return

    field_values_operation = label_update_input.field_values_operation
    if field_values_operation is None:
        field_values_operation = "merge"

    if field_values_operation == "replace":
        label["field_values"] = copy.deepcopy(label_update_input.field_values) if label_update_input.field_values is not None else {}
        return

    merged_field_values = copy.deepcopy(label.get("field_values", {}))
    assert label_update_input.field_values is not None
    merged_field_values.update(copy.deepcopy(label_update_input.field_values))
    label["field_values"] = merged_field_values


def create_comment_for_update_labels(resolved_label_update_inputs: Sequence[ResolvedLabelUpdateInput]) -> str:
    """
    ラベル更新時のデフォルトコメントを生成する。

    Args:
        resolved_label_update_inputs: 解決済みラベル更新入力一覧

    Returns:
        アノテーション仕様変更コメント
    """
    label_names = [get_label_name_en(label_input.target_label) for label_input in resolved_label_update_inputs]
    return f"以下のラベル情報を更新しました。\n対象ラベル: {', '.join(label_names)}"


def build_request_body_for_update_labels(
    annotation_specs: dict[str, Any],
    *,
    resolved_label_update_inputs: Sequence[ResolvedLabelUpdateInput],
    comment: str | None,
) -> dict[str, Any]:
    """
    複数ラベル更新用の request body を生成する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        resolved_label_update_inputs: 解決済みラベル更新入力一覧
        comment: 変更コメント

    Returns:
        Annofab API に渡す request body
    """
    request_body = copy.deepcopy(annotation_specs)
    label_input_dict = {label_input.target_label["label_id"]: label_input.label_update_input for label_input in resolved_label_update_inputs}
    for label in request_body["labels"]:
        label_update_input = label_input_dict.get(label["label_id"])
        if label_update_input is None:
            continue

        if label_update_input.label_name_ja is not None:
            update_label_name_ja(label, label_update_input.label_name_ja)
        if label_update_input.color is not None:
            label["color"] = hex_to_rgb(label_update_input.color)
        if label_update_input.keybind is not None:
            label["keybind"] = keybind_to_api_keybind(copy.deepcopy(label_update_input.keybind))
        update_label_field_values(label, label_update_input)

    if comment is None:
        comment = create_comment_for_update_labels(resolved_label_update_inputs)
    request_body["comment"] = comment
    request_body["last_updated_datetime"] = annotation_specs["updated_datetime"]
    return request_body


class UpdateLabelsMain(CommandLineWithConfirm):
    """
    既存ラベルの情報を更新する本体処理。
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

    def update_labels(
        self,
        *,
        label_update_inputs: Sequence[LabelUpdateInput],
        comment: str | None = None,
    ) -> bool:
        """
        複数ラベルの情報を更新して、アノテーション仕様を更新する。

        Args:
            label_update_inputs: ラベル更新入力一覧
            comment: 変更コメント

        Returns:
            更新を実行した場合はTrue、確認で中断した場合はFalse
        """
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        resolved_label_update_inputs = resolve_label_update_inputs(old_annotation_specs, label_update_inputs=label_update_inputs)
        label_names = [get_label_name_en(label_input.target_label) for label_input in resolved_label_update_inputs]

        confirm_message = f"{len(resolved_label_update_inputs)} 件のラベル情報を更新します。対象ラベル={label_names}。よろしいですか？"
        if not self.confirm_processing(confirm_message):
            return False

        request_body = build_request_body_for_update_labels(
            old_annotation_specs,
            resolved_label_update_inputs=resolved_label_update_inputs,
            comment=comment,
        )
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"{len(resolved_label_update_inputs)} 件のラベル情報を更新しました。")
        return True


class UpdateLabels(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs update_labels: error:"

    def main(self) -> None:
        """
        コマンドライン引数を解釈し、複数ラベル更新処理を実行する。
        """
        args = self.args
        if args.label_json is not None:
            label_update_inputs = read_labels_json(args.label_json)
        elif args.label_csv is not None:
            if not args.label_csv.exists():
                raise ValueError(f"`--label_csv` に指定されたファイルが存在しません。 :: {args.label_csv}")
            label_update_inputs = read_labels_csv(args.label_csv)
        else:
            raise ValueError("`--label_json` , `--label_csv` のいずれかを指定してください。")

        obj = UpdateLabelsMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.update_labels(
            label_update_inputs=label_update_inputs,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    ``update_labels`` サブコマンドの引数を定義する。

    Args:
        parser: 引数を追加するArgumentParser
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    sample_json = [
        {
            "label_name_en": "car",
            "label_name_ja": "車",
            "color": "#123456",
            "keybind": {"alt": False, "code": "Digit1", "ctrl": True, "shift": False},
            "field_values": {"margin_of_error_tolerance": {"max_pixel": 5, "_type": "MarginOfErrorTolerance"}},
        },
        {"label_id": "bike", "field_values_operation": "replace"},
    ]
    label_group = parser.add_mutually_exclusive_group(required=True)
    label_group.add_argument(
        "--label_json",
        type=str,
        help=(
            "更新するラベル情報のJSON配列を指定します。 ``file://`` を先頭に付けるとJSON形式のファイルを指定できます。"
            " 各要素には ``label_id`` または ``label_name_en`` のどちらか一方が必要です。"
            " 任意で ``label_name_ja`` , ``color`` , ``keybind`` , ``field_values`` , ``field_values_operation`` を指定できます。"
            f"\n(例) ``{json.dumps(sample_json, ensure_ascii=False)}``"
        ),
    )
    label_group.add_argument(
        "--label_csv",
        type=Path,
        help=(
            "更新するラベル情報のCSVファイルを指定します。 CSVには ``label_id`` または ``label_name_en`` 列のどちらか一方が必要です。"
            " 任意で ``label_name_ja`` , ``color`` , ``keybind`` , ``field_values`` , ``field_values_operation`` 列を指定できます。"
            " ``keybind`` 列と ``field_values`` 列にはJSONオブジェクト文字列を指定してください。"
        ),
    )
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``update_labels`` コマンドのエントリポイント。

    Args:
        args: コマンドライン引数
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateLabels(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs update_labels`` 用のparserを生成する。

    Args:
        subparsers: 親parserのsubparsers

    Returns:
        生成したArgumentParser
    """
    subcommand_name = "update_labels"
    subcommand_help = "アノテーション仕様の既存ラベル情報を更新します。"
    description = "アノテーション仕様の既存ラベルに設定された日本語名、色、キーバインド、field_values を更新します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
