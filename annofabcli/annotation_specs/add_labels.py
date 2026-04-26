from __future__ import annotations

import argparse
import copy
import json
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import annofabapi
import pandas

import annofabcli.common.cli
from annofabcli.annotation_specs.add_label import (
    ANNOTATION_TYPE_CHOICES,
    collect_label_colors,
    create_annotation_type_help,
    create_auto_color,
    create_new_label,
    validate_new_label,
)
from annofabcli.annotation_specs.utils import get_label_name_en
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login, get_json_from_args
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import duplicated_set

logger = logging.getLogger(__name__)


@dataclass
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


def normalize_nullable_str(value: object) -> str | None:
    """
    文字列または欠損値を ``str | None`` に正規化する。

    Args:
        value: 正規化対象の値

    Returns:
        文字列またはNone
    """
    if pandas.isna(value):
        return None
    if isinstance(value, str):
        return value
    return str(value)


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

    return LabelInput(
        label_name_en=label_name_en,
        label_name_ja=data.get("label_name_ja"),
        label_id=data.get("label_id"),
    )


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
                "label_name_en": "string",
                "label_name_ja": "string",
            },
        )
    except Exception as e:
        raise ValueError(f"`--label_csv` の読み込みに失敗しました。 :: {e}") from e

    required_columns = {"label_name_en"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"`--label_csv` に不足している必須列があります。 :: {sorted(missing_columns)}")

    result = []
    for row in df.to_dict(orient="records"):
        label_name_en = row["label_name_en"]
        label_name_ja = normalize_nullable_str(row.get("label_name_ja"))
        label_id = normalize_nullable_str(row.get("label_id"))
        result.append(
            LabelInput(
                label_name_en=label_name_en,
                label_name_ja=label_name_ja,
                label_id=label_id,
            )
        )
    return result


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
        annotation_type: str,
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

        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        request_body = copy.deepcopy(old_annotation_specs)
        existing_label_names = {get_label_name_en(label) for label in request_body["labels"]}
        input_label_name_ens = [label.label_name_en for label in label_inputs]
        duplicated_existing_label_names = sorted(set(input_label_name_ens) & existing_label_names)
        if duplicated_existing_label_names:
            duplicated_text = ", ".join(duplicated_existing_label_names)
            raise ValueError(f"以下のラベル名(英語)は既に存在します。 :: {duplicated_text}")

        colors = collect_label_colors(request_body["labels"])

        confirm_message = f"{len(label_inputs)} 件のラベルを追加します。 label_name_en={input_label_name_ens}, annotation_type='{annotation_type}'。よろしいですか？"
        if not self.confirm_processing(confirm_message):
            return False

        for label_input in label_inputs:
            resolved_label_id = label_input.label_id if label_input.label_id is not None else str(uuid.uuid4())
            validate_new_label(request_body["labels"], label_id=resolved_label_id, label_name_en=label_input.label_name_en)

            color = create_auto_color(colors)
            colors.append(color)
            new_label = create_new_label(
                label_id=resolved_label_id,
                label_name_en=label_input.label_name_en,
                label_name_ja=label_input.label_name_ja,
                annotation_type=annotation_type,
                color=color,
            )
            request_body["labels"].append(new_label)

        if comment is None:
            comment = create_comment_from_labels(label_inputs)
        request_body["comment"] = comment
        request_body["last_updated_datetime"] = old_annotation_specs["updated_datetime"]
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"{len(label_inputs)} 件のラベルを追加しました。 :: label_name_ens={input_label_name_ens}, annotation_type='{annotation_type}'")
        return True


class AddLabels(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs add_labels: error:"

    def main(self) -> None:
        """
        コマンドライン引数を解釈し、複数ラベル追加処理を実行する。
        """
        args = self.args
        if args.label_json is not None:
            label_inputs = read_labels_json(args.label_json)
        elif args.label_csv is not None:
            if not args.label_csv.exists():
                raise ValueError(f"`--label_csv` に指定されたファイルが存在しません。 :: {args.label_csv}")
            label_inputs = read_labels_csv(args.label_csv)
        else:
            raise ValueError("`--label_json` または `--label_csv` のいずれかを指定してください。")

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
        {"label_id": "pedestrian", "label_name_en": "pedestrian", "label_name_ja": "歩行者"},
        {"label_name_en": "bicycle"},
    ]
    label_group = parser.add_mutually_exclusive_group(required=True)
    label_group.add_argument(
        "--label_json",
        type=str,
        help=f"追加するラベル情報のJSON配列を指定します。 ``file://`` を先頭に付けるとJSON形式のファイルを指定できます。\n(例) ``{json.dumps(sample_json, ensure_ascii=False)}``",
    )
    label_group.add_argument(
        "--label_csv",
        type=Path,
        help="追加するラベル情報のCSVファイルを指定します。 CSVには ``label_name_en`` 列が必要です。 任意で ``label_id`` , ``label_name_ja`` 列を指定できます。",
    )
    parser.add_argument("--annotation_type", type=str, required=True, choices=ANNOTATION_TYPE_CHOICES, help=create_annotation_type_help())
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
