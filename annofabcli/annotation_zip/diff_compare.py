"""ローカルのアノテーション結果と外部ファイルを比較する。"""

from __future__ import annotations

import json
import logging
import zipfile
from collections.abc import Collection
from contextlib import ExitStack
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Literal

import numpy
from annofabapi.parser import SimpleAnnotationParser, SimpleAnnotationZipParser, lazy_parse_simple_annotation_dir
from annofabapi.segmentation import read_binary_image
from pydantic import BaseModel, JsonValue, TypeAdapter

from annofabcli.annotation_zip.diff_models import AnnotationKey, AnnotationZipDiff, ChangedAnnotation, ValueChange
from annofabcli.common.exceptions import AnnofabCliException

logger = logging.getLogger(__name__)

type Target = Literal["label", "data", "attributes"]
"""比較対象のアノテーションフィールド。"""

CHUNK_SIZE = 64 * 1024
"""バイト列比較時の読み込みサイズ。"""


class AnnotationDetail(BaseModel):
    """比較に必要な結果のみを読み込む。"""

    annotation_id: str
    """アノテーションID。"""
    label: str
    """ラベル名。"""
    data: dict[str, JsonValue]
    """形状や外部ファイルの参照情報。画像全体は_type='Classification'。"""
    attributes: dict[str, JsonValue]
    """属性キーと値。"""


class AnnotationSource:
    """比較中はZIPを開いたまま保持する入力。"""

    def __init__(self, path: Path, stack: ExitStack) -> None:
        """パス由来の入力データキーでパーサーを索引化する。

        Args:
            path: ZIPまたは展開ディレクトリ。
            stack: ZIPを閉じるためのコンテキスト。

        Returns:
            なし。
        """
        self.zip_file: zipfile.ZipFile | None = None
        """比較中に保持するZIP。ディレクトリ入力ならNone。"""
        self.parsers: dict[tuple[str, str], SimpleAnnotationParser] = {}
        """パス由来の入力データキーとパーサーの索引。"""
        if path.is_dir():
            parsers = list(lazy_parse_simple_annotation_dir(path))
        else:
            self.zip_file = stack.enter_context(zipfile.ZipFile(path))
            parsers = []
            for info in self.zip_file.infolist():
                parts = PurePosixPath(info.filename).parts
                if not info.is_dir() and len(parts) == 2 and parts[1].endswith(".json"):
                    parsers.append(SimpleAnnotationZipParser(self.zip_file, info.filename))
        for parser in parsers:
            key = (parser.task_id, parser.input_data_id)
            if key in self.parsers:
                raise ValueError(f"入力データJSONが重複しています。 :: task_id='{key[0]}', input_data_id='{key[1]}'")
            self.parsers[key] = parser

    def open_external(self, parser: SimpleAnnotationParser, uri: str, stack: ExitStack) -> BinaryIO:
        """入力データ配下の外部ファイルを開く。

        Args:
            parser: 入力データのパーサー。
            uri: 正規化済みの相対参照。
            stack: ファイルを閉じるためのコンテキスト。

        Returns:
            読み取り可能なバイナリストリーム。
        """
        relative = PurePosixPath(uri)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError(f"外部ファイルの参照が不正です。 :: uri='{uri}'")
        return stack.enter_context(parser.open_outer_file(str(relative)))

    def external_size(self, parser: SimpleAnnotationParser, uri: str) -> int:
        """展開後の外部ファイルサイズを取得する。

        Args:
            parser: 入力データのパーサー。
            uri: 正規化済みの相対参照。

        Returns:
            ファイルのバイト数。
        """
        if self.zip_file is not None:
            path = PurePosixPath(parser.json_file_path).with_suffix("") / uri
            return self.zip_file.getinfo(str(path)).file_size
        return (Path(parser.json_file_path).with_suffix("") / uri).stat().st_size


def _load_details(parser: SimpleAnnotationParser) -> dict[str, AnnotationDetail]:
    """重複IDを検証してアノテーションを索引化する。

    Args:
        parser: 入力データのパーサー。

    Returns:
        IDとアノテーション結果の辞書。
    """
    details = TypeAdapter(list[AnnotationDetail]).validate_python(parser.load_json()["details"])
    result = {}
    for detail in details:
        if detail.annotation_id in result:
            raise ValueError(f"annotation_idが重複しています。 :: annotation_id='{detail.annotation_id}'")
        result[detail.annotation_id] = detail
    return result


def _external_reference(data: dict[str, JsonValue], input_data_id: str) -> tuple[str, str] | None:
    """外部ファイルの種類と入力データ配下の参照を取り出す。

    Args:
        data: アノテーションの形状情報。
        input_data_id: パス由来の入力データID。

    Returns:
        種類と相対パス。外部参照なしの場合はNone。
    """
    if data.get("_type") in ("Segmentation", "SegmentationV2"):
        uri = data.get("data_uri")
        if not isinstance(uri, str):
            raise ValueError("塗りつぶし画像のdata_uriが文字列ではありません。")
        return "SEGMENTATION", uri
    if data.get("_type") == "Unknown" and isinstance(data.get("data"), str):
        uri = data["data"]
        assert isinstance(uri, str)
        try:
            json.loads(uri)
        except json.JSONDecodeError:
            parts = PurePosixPath(uri).parts
            if parts and parts[0] == input_data_id:
                uri = str(PurePosixPath(*parts[1:]))
            return "SEGMENT", uri
    return None


def _comparable_data(data: dict[str, JsonValue], reference: tuple[str, str] | None) -> dict[str, JsonValue]:
    """参照パスを除き、埋め込みJSONを正規化する。

    Args:
        data: アノテーションの形状情報。
        reference: 外部ファイルの参照。

    Returns:
        内容比較用の形状情報。
    """
    result = dict(data)
    if reference is not None:
        del result["data_uri" if reference[0] == "SEGMENTATION" else "data"]
    elif data.get("_type") == "Unknown" and isinstance(data.get("data"), str):
        result["data"] = json.loads(str(data["data"]))
    return result


def _same_bytes(left: BinaryIO, right: BinaryIO) -> bool:
    """バイト列を一定サイズずつ比較する。

    Args:
        left: 比較元のストリーム。
        right: 比較先のストリーム。

    Returns:
        全バイトが一致するか。
    """
    while True:
        left_chunk, right_chunk = left.read(CHUNK_SIZE), right.read(CHUNK_SIZE)
        if left_chunk != right_chunk:
            return False
        if not left_chunk:
            return True


def _equal_json(left: JsonValue, right: JsonValue) -> bool:
    """真偽値と数値を区別してJSONを再帰的に比較する。

    Args:
        left: 比較元の値。
        right: 比較先の値。

    Returns:
        JSONとして同じ値か。数値の1と1.0は同じ値として扱う。
    """
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, dict):
        return isinstance(right, dict) and left.keys() == right.keys() and all(_equal_json(value, right[key]) for key, value in left.items())
    if isinstance(left, list):
        return isinstance(right, list) and len(left) == len(right) and all(_equal_json(lvalue, rvalue) for lvalue, rvalue in zip(left, right, strict=True))
    return left == right


def _segment_points(file: BinaryIO) -> set[int]:
    """対応形式の3Dセグメントから点集合を読み込む。

    Args:
        file: 外部JSONのストリーム。

    Returns:
        セグメントに所属する点の集合。
    """
    data = json.load(file)
    if not isinstance(data, dict) or data.get("kind") != "SEGMENT" or data.get("version", "1") != "1":
        raise ValueError("対応していない3Dセグメント形式です。")
    points = data.get("points")
    if not isinstance(points, list) or any(type(point) is not int or point < 0 for point in points):
        raise ValueError("3Dセグメントのpointsは非負整数の配列である必要があります。")
    return set(points)


def _compare_external(
    left_source: AnnotationSource,
    right_source: AnnotationSource,
    left_parser: SimpleAnnotationParser,
    right_parser: SimpleAnnotationParser,
    left_reference: tuple[str, str],
    right_reference: tuple[str, str],
) -> dict[str, JsonValue] | None:
    """外部ファイルを形式に応じて比較する。

    Args:
        left_source: 比較元の入力。
        right_source: 比較先の入力。
        left_parser: 比較元のパーサー。
        right_parser: 比較先のパーサー。
        left_reference: 比較元の参照。
        right_reference: 比較先の参照。

    Returns:
        差分件数。内容一致の場合はNone。
    """
    with ExitStack() as stack:
        left = left_source.open_external(left_parser, left_reference[1], stack)
        right = right_source.open_external(right_parser, right_reference[1], stack)
        if left_reference[0] != right_reference[0]:
            raise ValueError("左右の外部ファイルの種類が異なります。")
        if left_reference[0] == "SEGMENT":
            left_points, right_points = _segment_points(left), _segment_points(right)
            if left_points == right_points:
                return None
            return {
                "kind": "SEGMENT",
                "point_count": {"left": len(left_points), "right": len(right_points)},
                "added_point_count": len(right_points - left_points),
                "removed_point_count": len(left_points - right_points),
            }
        if left_source.external_size(left_parser, left_reference[1]) == right_source.external_size(right_parser, right_reference[1]) and _same_bytes(left, right):
            return None
        left.seek(0)
        right.seek(0)
        left_mask, right_mask = read_binary_image(left), read_binary_image(right)
        if numpy.array_equal(left_mask, right_mask):
            return None
        return {
            "kind": "SEGMENTATION",
            "image_size": {"left": [int(left_mask.shape[1]), int(left_mask.shape[0])], "right": [int(right_mask.shape[1]), int(right_mask.shape[0])]},
            "filled_pixel_count": {"left": int(numpy.count_nonzero(left_mask)), "right": int(numpy.count_nonzero(right_mask))},
            "changed_pixel_count": int(numpy.count_nonzero(left_mask != right_mask)) if left_mask.shape == right_mask.shape else None,
        }


def _compare_annotation(
    key: AnnotationKey,
    left: AnnotationDetail,
    right: AnnotationDetail,
    left_source: AnnotationSource,
    right_source: AnnotationSource,
    left_parser: SimpleAnnotationParser,
    right_parser: SimpleAnnotationParser,
    targets: Collection[Target],
) -> ChangedAnnotation | None:
    """1件のアノテーションの指定フィールドを比較する。

    Args:
        key: パス由来の比較キー。
        left: 比較元の結果。
        right: 比較先の結果。
        left_source: 比較元の入力。
        right_source: 比較先の入力。
        left_parser: 比較元のパーサー。
        right_parser: 比較先のパーサー。
        targets: 比較するフィールド。

    Returns:
        変更内容。結果一致の場合はNone。
    """
    result = ChangedAnnotation(**key.model_dump())
    if "label" in targets and left.label != right.label:
        result.label_changed = True
        result.changes["label"] = ValueChange(left=left.label, right=right.label)
    if "attributes" in targets:
        result.added_attribute_keys = sorted(right.attributes.keys() - left.attributes.keys())
        result.removed_attribute_keys = sorted(left.attributes.keys() - right.attributes.keys())
        result.changed_attribute_keys = sorted(k for k in left.attributes.keys() & right.attributes.keys() if not _equal_json(left.attributes[k], right.attributes[k]))
        result.attributes_changed = bool(result.added_attribute_keys or result.removed_attribute_keys or result.changed_attribute_keys)
        if result.attributes_changed:
            result.attribute_changes = {
                "added": [{"key": k, "right": right.attributes[k]} for k in result.added_attribute_keys],
                "removed": [{"key": k, "left": left.attributes[k]} for k in result.removed_attribute_keys],
                "changed": [{"key": k, "left": left.attributes[k], "right": right.attributes[k]} for k in result.changed_attribute_keys],
            }
    if "data" in targets:
        left_reference = _external_reference(left.data, key.input_data_id)
        right_reference = _external_reference(right.data, key.input_data_id)
        if not _equal_json(_comparable_data(left.data, left_reference), _comparable_data(right.data, right_reference)):
            result.data_changed = True
            result.changes["data"] = ValueChange(left=left.data, right=right.data)
        if left_reference and right_reference and left_reference[0] == right_reference[0]:
            result.external_file = _compare_external(left_source, right_source, left_parser, right_parser, left_reference, right_reference)
            result.external_file_changed = result.external_file is not None
            result.data_changed |= result.external_file_changed
        elif left_reference or right_reference:
            result.data_changed = True
            result.external_file_changed = True
    return result if result.label_changed or result.data_changed or result.attributes_changed else None


def create_annotation_zip_diff(left_path: Path, right_path: Path, *, targets: Collection[Target] = ("label", "data", "attributes")) -> AnnotationZipDiff:
    """パス由来の入力データとannotation_idで結果を比較する。

    Args:
        left_path: 比較元のZIPまたは展開ディレクトリ。
        right_path: 比較先のZIPまたは展開ディレクトリ。
        targets: 比較するフィールド。追加・削除は常に比較する。

    Returns:
        アノテーションの差分。
    """
    result = AnnotationZipDiff()
    with ExitStack() as stack:
        sources = []
        for side, path in (("left", left_path), ("right", right_path)):
            try:
                sources.append(AnnotationSource(path, stack))
            except Exception as exc:
                raise AnnofabCliException(f"入力を読み込めません。 :: side='{side}', path='{path}': {exc}") from exc
        left_source, right_source = sources
        input_keys = sorted(left_source.parsers.keys() | right_source.parsers.keys())
        for index, input_key in enumerate(input_keys, start=1):
            left_parser, right_parser = left_source.parsers.get(input_key), right_source.parsers.get(input_key)
            try:
                left_details = _load_details(left_parser) if left_parser else {}
                right_details = _load_details(right_parser) if right_parser else {}
            except Exception as exc:
                raise AnnofabCliException(f"アノテーションJSONを読み込めません。 :: task_id='{input_key[0]}', input_data_id='{input_key[1]}': {exc}") from exc
            for annotation_id in sorted(left_details.keys() | right_details.keys()):
                key = AnnotationKey(task_id=input_key[0], input_data_id=input_key[1], annotation_id=annotation_id)
                if annotation_id not in left_details:
                    result.annotations.added.append(key)
                elif annotation_id not in right_details:
                    result.annotations.removed.append(key)
                else:
                    assert left_parser is not None and right_parser is not None
                    try:
                        changed = _compare_annotation(key, left_details[annotation_id], right_details[annotation_id], left_source, right_source, left_parser, right_parser, targets)
                    except Exception as exc:
                        raise AnnofabCliException(f"アノテーションを比較できません。 :: {key.model_dump()}, left='{left_path}', right='{right_path}': {exc}") from exc
                    if changed is not None:
                        result.annotations.changed.append(changed)
            if index % 1000 == 0:
                logger.info(f"{index}/{len(input_keys)} 件の入力データを比較しました。")
    logger.info(f"比較完了。追加={len(result.annotations.added)}, 削除={len(result.annotations.removed)}, 変更={len(result.annotations.changed)}")
    return result
