"""アノテーションZIPの差分コマンド。"""

from __future__ import annotations

import argparse
import json
import logging
import tempfile
from pathlib import Path
from typing import cast

import yaml
from annofabapi.models import ProjectMemberRole
from pydantic import JsonValue

import annofabcli.common.cli
from annofabcli.annotation_zip.diff_compare import Target, create_annotation_zip_diff
from annofabcli.annotation_zip.diff_models import AnnotationZipDiff, ChangedAnnotation
from annofabcli.common.cli import build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import output_string, print_json

logger = logging.getLogger(__name__)


def _display_value(value: JsonValue) -> JsonValue:
    """複合値を詳細表示用のJSON文字列にする。

    Args:
        value: 表示する値。

    Returns:
        スカラー値またはJSON文字列。
    """
    return json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else value


def _format_changed(item: ChangedAnnotation, *, detail: bool) -> dict[str, JsonValue]:
    """変更された1件のテキスト用データを作る。

    Args:
        item: アノテーションの差分。
        detail: 詳細を表示するか。

    Returns:
        階層表示用のデータ。
    """
    changed: dict[str, JsonValue] = {"task_id": item.task_id, "input_data_id": item.input_data_id, "annotation_id": item.annotation_id}
    changed["fields"] = [field for field in ("label", "data", "attributes") if getattr(item, f"{field}_changed")]
    for field in ("label", "data", "attributes", "external_file"):
        if getattr(item, f"{field}_changed"):
            changed[f"{field}_changed"] = True
    if detail:
        if item.changes:
            changed["changes"] = {key: {"left": _display_value(value.left), "right": _display_value(value.right)} for key, value in item.changes.items()}
        if item.attribute_changes:
            changed["attributes"] = item.attribute_changes
        if item.external_file:
            changed["external_file"] = item.external_file
    elif item.attributes_changed:
        for field in ("added_attribute_keys", "removed_attribute_keys", "changed_attribute_keys"):
            changed[field] = getattr(item, field)
    return changed


def format_diff_as_text(diff: AnnotationZipDiff, *, detail: bool = False) -> str:
    """差分を既存diffコマンドと同じ階層テキストに変換する。

    Args:
        diff: 比較結果。
        detail: 変更前後の値と外部ファイルの差分件数も表示するか。

    Returns:
        差分テキスト。差分なしの場合は空文字。
    """
    if not diff.has_diff:
        return ""
    annotations: dict[str, JsonValue] = {}
    if diff.annotations.added:
        annotations["added"] = [item.model_dump() for item in diff.annotations.added]
    if diff.annotations.removed:
        annotations["removed"] = [item.model_dump() for item in diff.annotations.removed]
    if diff.annotations.changed:
        annotations["changed"] = [_format_changed(item, detail=detail) for item in diff.annotations.changed]
    return "[annotations]\n" + yaml.safe_dump(annotations, allow_unicode=True, sort_keys=False).rstrip() + "\n"


def _resolve_sources(args: argparse.Namespace, directory: Path) -> dict[str, Path]:
    """プロジェクト指定がある場合だけ認証し、比較対象を取得する。

    Args:
        args: CLI引数。
        directory: ダウンロード用の一時ディレクトリ。

    Returns:
        左右のZIPまたは展開ディレクトリのパス。
    """
    paths: dict[str, Path] = {}
    for side in ("left", "right"):
        annotation: Path | None = getattr(args, f"{side}_annotation")
        if annotation is not None:
            paths[side] = annotation
    project_ids = list(dict.fromkeys(project_id for project_id in (args.left_project_id, args.right_project_id) if project_id is not None))
    if project_ids:
        service = build_annofabapi_resource_and_login(args)
        facade = AnnofabApiFacade(service)
        for project_id in project_ids:
            facade.require_project_access(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
        downloader = DownloadingFile(service)
        directory.mkdir(parents=True, exist_ok=True)
        downloaded = {project_id: downloader.download_annotation_zip_to_dir(project_id, directory, is_latest=args.latest) for project_id in project_ids}
        for side in ("left", "right"):
            project_id = getattr(args, f"{side}_project_id")
            if project_id is not None:
                paths[side] = downloaded[project_id]
    return paths


def main(args: argparse.Namespace) -> None:
    """指定された入力から差分を出力する。

    Args:
        args: CLI引数。

    Returns:
        なし。
    """
    with tempfile.TemporaryDirectory() as directory:
        paths = _resolve_sources(args, args.temp_dir if args.temp_dir is not None else Path(directory))
        diff = create_annotation_zip_diff(
            paths["left"],
            paths["right"],
            targets=cast(list[Target], args.target or ["label", "data", "attributes"]),
            target_task_ids=annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None,
        )
    if args.format in ("json", "pretty_json"):
        print_json(diff.model_dump(exclude_none=True), is_pretty=args.format == "pretty_json", output=args.output)
    else:
        text = format_diff_as_text(diff, detail=args.format == "detail_text")
        if not text:
            logger.info("差分はありません。")
        if text or args.output is not None:
            output_string(text, args.output)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """diffコマンドを登録する。

    Args:
        subparsers: 親のサブパーサー。

    Returns:
        diffコマンドのパーサー。
    """
    epilog = (
        "``--left_project_id`` または ``--right_project_id`` を指定する場合は、指定した各プロジェクトに対してオーナーロールまたはアノテーションユーザーロールを持つユーザーで実行してください。"
        "ローカルファイル同士を比較する場合は、プロジェクトのロールに関係なく実行できます。"
    )
    parser = annofabcli.common.cli.add_parser(
        subparsers,
        "diff",
        "アノテーションZIPの差分を出力します。",
        "プロジェクトまたはローカルのZIP・展開ディレクトリから、2つのアノテーション結果を比較します。",
        epilog=epilog,
    )
    for side, description in (("left", "比較元（左側）"), ("right", "比較先（右側）")):
        group = parser.add_mutually_exclusive_group(required=True)
        direction = "右側にのみあるアノテーションは追加として出力します。" if side == "left" else "左側にのみあるアノテーションは削除として出力します。"
        group.add_argument(f"--{side}_project_id", help=f"{description}のプロジェクトID。アノテーションZIPを取得します。{direction}")
        group.add_argument(f"--{side}_annotation", type=Path, help=f"{description}のローカルのアノテーションZIPまたは展開ディレクトリ。{direction}")
    parser.add_argument("--latest", action="store_true", help="プロジェクトIDを指定した側のアノテーションZIPを最新化して取得します。更新に数分かかる場合があります。")
    parser.add_argument("--temp_dir", type=Path, help="アノテーションZIPのダウンロード先ディレクトリ。指定したディレクトリとファイルは比較後も保持します。")
    annofabcli.common.cli.ArgumentParser(parser).add_task_id(required=False, help_message="左右の比較対象とするタスクのtask_idを指定します。省略時はすべてのタスクを比較します。")
    parser.add_argument("--target", nargs="+", choices=["label", "data", "attributes"], help="比較するフィールド。省略時はすべて比較します。アノテーションの追加・削除は常に出力します。")
    parser.add_argument(
        "-f",
        "--format",
        choices=["text", "detail_text", "json", "pretty_json"],
        default="text",
        help="出力形式。textは変更項目、detail_textは変更前後の値と外部ファイルの差分件数、json/pretty_jsonは構造化した差分を出力します。",
    )
    parser.add_argument("--output", type=Path, help="出力先のファイルパス。省略時は標準出力。")
    parser.set_defaults(subcommand_func=main)
    return parser
