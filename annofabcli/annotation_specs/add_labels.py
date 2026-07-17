from __future__ import annotations

import argparse
import copy
import json
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import annofabapi
import pandas
from annofabapi.util.annotation_specs import get_label_name_en

import annofabcli.common.cli
from annofabcli.annotation_specs.add_label import (
    ANNOTATION_TYPE_CHOICES,
    collect_label_colors,
    create_annotation_type_help,
    create_auto_color,
    create_new_label,
    validate_field_values_input,
    validate_new_label,
)
from annofabcli.annotation_specs.color import RgbColor, hex_to_rgb
from annofabcli.common.annofab.annotation_specs import validate_keybind_input
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    get_list_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import duplicated_set

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LabelInput:
    """
    コマンドラインから受け取ったラベル1件分の入力情報。
    """

    label_name_en: str
    """ラベルの英語名。"""

    label_name_ja: str | None = None
    """ラベルの日本語名。"""

    label_id: str | None = None
    """ラベルID。未指定の場合はUUIDv4を自動生成する。"""

    annotation_type: str | None = None
    """ラベルのアノテーション種類。未指定の場合は ``--annotation_type`` の値を使用する。"""

    color: str | None = None
    """``#RRGGBB`` 形式のカラーコード。未指定の場合は自動設定する。"""

    keybind: dict[str, Any] | None = None
    """新規ラベルに設定するkeybind。未指定の場合はNone。"""

    field_values: dict[str, Any] | None = None
    """新規ラベルに設定するfield_values。未指定の場合はNone。"""


def parse_label_input_from_dict(data: dict[str, Any], *, index: int) -> LabelInput:
    """
    JSONオブジェクト1件をラベル入力に変換する。

    Args:
        data: ラベル情報を表すdict
        index: エラーメッセージ用の1始まりの位置

    Returns:
        変換後のラベル入力

    Raises:
        ValueError: 必須項目が不足している場合
    """
    label_name_en = data.get("label_name_en")
    if label_name_en is None:
        raise ValueError(f"{index}件目のラベルに `label_name_en` が指定されていません。")
    field_values = data.get("field_values")
    keybind = data.get("keybind")
    annotation_type = data.get("annotation_type")
    if annotation_type is not None:
        annotation_type = validate_annotation_type(annotation_type, index=index)

    return LabelInput(
        label_name_en=label_name_en,
        label_name_ja=data.get("label_name_ja"),
        label_id=data.get("label_id"),
        annotation_type=annotation_type,
        color=data.get("color"),
        keybind=None if keybind is None else validate_keybind_input(keybind),
        field_values=None if field_values is None else validate_field_values_input(field_values),
    )


def validate_annotation_type(annotation_type: object, *, index: int) -> str:
    """
    ラベル入力の ``annotation_type`` を検証する。

    Args:
        annotation_type: 入力されたアノテーション種類
        index: エラーメッセージ用の1始まりの位置

    Returns:
        検証済みのアノテーション種類

    Raises:
        ValueError: 指定値がサポート対象外の場合
    """
    if not isinstance(annotation_type, str) or annotation_type not in ANNOTATION_TYPE_CHOICES:
        raise ValueError(f"{index}件目のラベルの `annotation_type` に不正な値が指定されています。")
    return annotation_type


def parse_field_values_in_csv(value: object, *, index: int) -> dict[str, Any] | None:
    """
    CSVの ``field_values`` 列を ``dict[str, Any] | None`` に変換する。

    Args:
        value: CSVセルの値
        index: エラーメッセージ用の1始まりの位置

    Returns:
        変換後のfield_values

    Raises:
        ValueError: JSON文字列として不正な場合
    """
    if not isinstance(value, str):
        value = str(value)
    if value == "":
        return None

    try:
        return validate_field_values_input(json.loads(value))
    except (TypeError, json.JSONDecodeError) as e:
        raise ValueError(f"{index}件目のラベルの `field_values` はJSONオブジェクト形式で指定してください。") from e


def parse_keybind_in_csv(value: object, *, index: int) -> dict[str, Any] | None:
    """
    CSVの ``keybind`` 列を ``dict[str, Any] | None`` に変換する。
    """
    if not isinstance(value, str):
        value = str(value)
    if value == "":
        return None

    try:
        return validate_keybind_input(json.loads(value))
    except (TypeError, ValueError, json.JSONDecodeError) as e:
        raise ValueError(f"{index}件目のラベルの `keybind` はJSONオブジェクト形式で指定してください。") from e


def parse_annotation_type_in_csv(value: object, *, index: int) -> str | None:
    """
    CSVの ``annotation_type`` 列を ``str | None`` に変換する。

    Args:
        value: CSVセルの値
        index: エラーメッセージ用の1始まりの位置

    Returns:
        変換後のアノテーション種類

    Raises:
        ValueError: ``annotation_type`` が不正な場合
    """
    if not isinstance(value, str):
        value = str(value)
    if value == "":
        return None

    return validate_annotation_type(value, index=index)


def read_labels_json(target: str) -> list[LabelInput]:
    """
    ``--label_json`` で指定されたJSONからラベル一覧を読み込む。

    Args:
        target: JSON文字列または ``file://`` 付きファイル指定

    Returns:
        ラベル入力の一覧

    Raises:
        TypeError: JSON全体が配列でない、または配列要素がオブジェクトでない場合
        ValueError: 各ラベルオブジェクトの必須項目が不足している場合
    """
    raw_data = get_json_from_args(target)
    if not isinstance(raw_data, list):
        raise TypeError("`--label_json` にはラベル情報の配列を指定してください。")

    result = []
    for index, label_data in enumerate(raw_data, start=1):
        if not isinstance(label_data, dict):
            raise TypeError(f"{index}件目のラベルがオブジェクト形式ではありません。")
        result.append(parse_label_input_from_dict(label_data, index=index))
    return result


def read_labels_csv(csv_path: Path) -> list[LabelInput]:
    """
    ``--label_csv`` で指定されたCSVからラベル一覧を読み込む。

    Args:
        csv_path: CSVファイルパス

    Returns:
        ラベル入力の一覧

    Raises:
        ValueError: CSV読み込みに失敗した場合、または必須列が不足している場合
    """
    try:
        df = pandas.read_csv(
            csv_path,
            dtype={
                "label_id": "string",
                "annotation_type": "string",
                "label_name_en": "string",
                "label_name_ja": "string",
                "color": "string",
                "keybind": "string",
                "field_values": "string",
            },
        )
    except Exception as e:
        raise ValueError(f"`--label_csv` の読み込みに失敗しました。 :: {e}") from e

    required_columns = {"label_name_en"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"`--label_csv` に不足している必須列があります。 :: {sorted(missing_columns)}")

    result = []
    for index, row in enumerate(df.to_dict(orient="records"), start=1):
        label_name_en = row["label_name_en"]
        label_name_ja = row.get("label_name_ja")
        label_id = row.get("label_id")
        annotation_type = parse_annotation_type_in_csv(row.get("annotation_type"), index=index)
        color = row.get("color")
        keybind = parse_keybind_in_csv(row.get("keybind"), index=index)
        field_values = parse_field_values_in_csv(row.get("field_values"), index=index)
        result.append(
            LabelInput(
                label_name_en=label_name_en,
                label_name_ja=label_name_ja,
                label_id=label_id,
                annotation_type=annotation_type,
                color=color,
                keybind=keybind,
                field_values=field_values,
            )
        )
    return result


def create_label_inputs_from_name_ens(label_name_ens: Sequence[str]) -> list[LabelInput]:
    """
    ラベル英語名一覧からラベル入力一覧を生成する。

    Args:
        label_name_ens: ラベル英語名一覧

    Returns:
        ラベル入力一覧
    """
    return [LabelInput(label_name_en=label_name_en) for label_name_en in label_name_ens]


def create_label_color(color_code: str | None, colors: list[RgbColor]) -> RgbColor:
    """
    ラベル入力から使用する色を決定する。

    Args:
        color_code: 入力されたカラーコード
        colors: 既存ラベルと今回追加分を含む使用済み色一覧

    Returns:
        Annofab API向けのRGB辞書

    Raises:
        ValueError: カラーコードの形式が不正な場合
    """
    if color_code is None:
        return create_auto_color(colors)

    try:
        return hex_to_rgb(color_code)
    except ValueError as e:
        raise ValueError("`color` には `#RRGGBB` 形式の16進数カラーコードを指定してください。") from e


def validate_label_inputs(label_inputs: Sequence[LabelInput]) -> None:
    """
    追加するラベル一覧の入力値を検証する。

    Args:
        label_inputs: 追加するラベル一覧

    Raises:
        ValueError: 件数不足または重複がある場合
    """
    if len(label_inputs) == 0:
        raise ValueError("追加するラベルを1件以上指定してください。")

    duplicated_label_ids = duplicated_set([label.label_id for label in label_inputs if label.label_id is not None])
    if duplicated_label_ids:
        duplicated_text = ", ".join(sorted(duplicated_label_ids))
        raise ValueError(f"入力されたラベルに重複した `label_id` があります。 :: {duplicated_text}")

    duplicated_label_names: set[str] = duplicated_set([label.label_name_en for label in label_inputs])
    if duplicated_label_names:
        duplicated_text = ", ".join(sorted(duplicated_label_names))
        raise ValueError(f"入力されたラベル名(英語)に重複があります。 :: {duplicated_text}")


def resolve_annotation_types(label_inputs: Sequence[LabelInput], *, annotation_type: str | None) -> list[LabelInput]:
    """
    ラベルごとの ``annotation_type`` を解決する。

    Args:
        label_inputs: 追加するラベル一覧
        annotation_type: ``--annotation_type`` に指定された既定値

    Returns:
        ``annotation_type`` を補完済みのラベル一覧

    Raises:
        ValueError: ラベル側と ``--annotation_type`` が不一致、または両方とも未指定の場合
    """
    resolved_label_inputs = []
    for index, label_input in enumerate(label_inputs, start=1):
        resolved_annotation_type = label_input.annotation_type
        if resolved_annotation_type is None:
            if annotation_type is None:
                raise ValueError(f"{index}件目のラベルに `annotation_type` が指定されていません。 `--annotation_type` を指定するか、入力データに `annotation_type` を含めてください。")
            resolved_annotation_type = annotation_type
        elif annotation_type is not None and resolved_annotation_type != annotation_type:
            raise ValueError(
                f"{index}件目のラベルの `annotation_type` と `--annotation_type` の値が一致しません。 :: label.annotation_type='{resolved_annotation_type}', --annotation_type='{annotation_type}'"
            )

        resolved_label_inputs.append(replace(label_input, annotation_type=resolved_annotation_type))
    return resolved_label_inputs


def create_comment_from_labels(label_inputs: Sequence[LabelInput]) -> str:
    """
    複数ラベル追加時のデフォルトコメントを生成する。

    Args:
        label_inputs: 追加するラベル一覧

    Returns:
        アノテーション仕様変更コメント
    """
    label_text = ", ".join(label.label_name_en for label in label_inputs)
    return f"以下のラベルを追加しました。\nラベル名(英語): {label_text}"


def build_request_body_for_add_labels(
    annotation_specs: dict[str, Any],
    *,
    resolved_label_inputs: Sequence[LabelInput],
    comment: str | None,
) -> dict[str, Any]:
    """
    複数ラベル追加用の request body を生成する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        resolved_label_inputs: ``annotation_type`` 解決済みのラベル一覧
        comment: 変更コメント

    Returns:
        Annofab API に渡す request body
    """
    request_body = copy.deepcopy(annotation_specs)
    existing_label_names = {get_label_name_en(label) for label in request_body["labels"]}
    input_label_name_ens = [label.label_name_en for label in resolved_label_inputs]
    duplicated_existing_label_names = sorted(set(input_label_name_ens) & existing_label_names)
    if duplicated_existing_label_names:
        duplicated_text = ", ".join(duplicated_existing_label_names)
        raise ValueError(f"以下のラベル名(英語)は既に存在します。 :: {duplicated_text}")

    colors = collect_label_colors(request_body["labels"])
    for label_input in resolved_label_inputs:
        resolved_label_id = label_input.label_id if label_input.label_id is not None else str(uuid.uuid4())
        validate_new_label(request_body["labels"], label_id=resolved_label_id, label_name_en=label_input.label_name_en)

        color = create_label_color(label_input.color, colors)
        colors.append(color)
        new_label = create_new_label(
            label_id=resolved_label_id,
            label_name_en=label_input.label_name_en,
            label_name_ja=label_input.label_name_ja,
            annotation_type=cast(str, label_input.annotation_type),
            color=color,
            keybind=label_input.keybind,
            field_values=label_input.field_values,
        )
        request_body["labels"].append(new_label)

    if comment is None:
        comment = create_comment_from_labels(resolved_label_inputs)
    request_body["comment"] = comment
    request_body["last_updated_datetime"] = annotation_specs["updated_datetime"]
    return request_body


class AddLabelsMain(CommandLineWithConfirm):
    """
    複数ラベルをアノテーション仕様へ追加する本体処理。
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

    def add_labels(
        self,
        *,
        label_inputs: Sequence[LabelInput],
        annotation_type: str | None = None,
        comment: str | None = None,
    ) -> bool:
        """
        複数ラベルを追加してアノテーション仕様を更新する。

        Args:
            label_inputs: 追加するラベル一覧
            annotation_type: 追加するラベルのアノテーション種類
            comment: 変更コメント

        Returns:
            追加を実行した場合はTrue、確認で中断した場合はFalse

        Raises:
            ValueError: 入力値や既存アノテーション仕様との整合性が不正な場合
        """
        validate_label_inputs(label_inputs)
        resolved_label_inputs = resolve_annotation_types(label_inputs, annotation_type=annotation_type)

        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        input_label_name_ens = [label.label_name_en for label in resolved_label_inputs]
        annotation_types = sorted({cast(str, label.annotation_type) for label in resolved_label_inputs})

        confirm_message = f"{len(label_inputs)} 件のラベルを追加します。 label_name_en={input_label_name_ens}, annotation_types={annotation_types}。よろしいですか？"
        if not self.confirm_processing(confirm_message):
            return False

        request_body = build_request_body_for_add_labels(
            old_annotation_specs,
            resolved_label_inputs=resolved_label_inputs,
            comment=comment,
        )
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"{len(label_inputs)} 件のラベルを追加しました。 :: label_name_ens={input_label_name_ens}, annotation_types={annotation_types}")
        return True


class AddLabels(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs add_labels: error:"

    def main(self) -> None:
        """
        コマンドライン引数を解釈し、複数ラベル追加処理を実行する。
        """
        args = self.args
        if args.label_name_en is not None:
            label_inputs = create_label_inputs_from_name_ens(get_list_from_args(args.label_name_en))
        elif args.label_json is not None:
            label_inputs = read_labels_json(args.label_json)
        elif args.label_csv is not None:
            if not args.label_csv.exists():
                raise ValueError(f"`--label_csv` に指定されたファイルが存在しません。 :: {args.label_csv}")
            label_inputs = read_labels_csv(args.label_csv)
        else:
            raise ValueError("`--label_name_en` , `--label_json` , `--label_csv` のいずれかを指定してください。")

        obj = AddLabelsMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.add_labels(
            label_inputs=label_inputs,
            annotation_type=args.annotation_type,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    ``add_labels`` サブコマンドの引数を定義する。

    Args:
        parser: 引数を追加するArgumentParser
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    sample_json = [
        {
            "label_id": "pedestrian",
            "label_name_en": "pedestrian",
            "label_name_ja": "歩行者",
            "annotation_type": "bounding_box",
            "color": "#123456",
            "keybind": {"alt": False, "code": "Digit1", "ctrl": True, "shift": False},
            "field_values": {"display_name": {"_type": "DisplayName", "text": "歩行者"}},
        },
        {"label_name_en": "bicycle", "annotation_type": "bounding_box"},
    ]
    label_group = parser.add_mutually_exclusive_group(required=True)
    label_group.add_argument(
        "--label_name_en",
        type=str,
        nargs="+",
        help="追加するラベルの英語名。複数指定できます。 ``file://`` を先頭に付けると一覧ファイルを指定できます。",
    )
    label_group.add_argument(
        "--label_json",
        type=str,
        help=(
            "追加するラベル情報のJSON配列を指定します。 ``file://`` を先頭に付けるとJSON形式のファイルを指定できます。"
            " 各要素には ``label_name_en`` が必要です。 任意で ``label_id`` , ``label_name_ja`` , ``annotation_type`` ,"
            " ``color`` , ``keybind`` , ``field_values`` を指定できます。 ``keybind`` と ``field_values`` にはJSONオブジェクトを指定してください。"
            " APIの ``keybind`` は配列形式ですが、このコマンドでは画面と同じく1つだけ指定できます。"
            f"\n(例) ``{json.dumps(sample_json, ensure_ascii=False)}``"
        ),
    )
    label_group.add_argument(
        "--label_csv",
        type=Path,
        help=(
            "追加するラベル情報のCSVファイルを指定します。 CSVには ``label_name_en`` 列が必要です。"
            " 任意で ``label_id`` , ``label_name_ja`` , ``annotation_type`` , ``color`` , ``keybind`` , ``field_values`` 列を指定できます。"
            " ``keybind`` 列と ``field_values`` 列にはJSONオブジェクト文字列を指定してください。"
            " APIの ``keybind`` は配列形式ですが、このコマンドでは画面と同じく1つだけ指定できます。"
        ),
    )
    parser.add_argument(
        "--annotation_type",
        type=str,
        choices=ANNOTATION_TYPE_CHOICES,
        help=f"追加するラベルの既定のアノテーション種類。 ``--label_name_en`` を指定する場合は必須です。 JSON/CSV側にも ``annotation_type`` を指定できます。\n{create_annotation_type_help()}",
    )
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``add_labels`` コマンドのエントリポイント。

    Args:
        args: コマンドライン引数
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    AddLabels(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs add_labels`` 用のparserを生成する。

    Args:
        subparsers: 親parserのsubparsers

    Returns:
        生成したArgumentParser
    """
    subcommand_name = "add_labels"
    subcommand_help = "アノテーション仕様にラベルを複数追加します。"
    description = "アノテーション仕様にラベルを複数件追加します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
