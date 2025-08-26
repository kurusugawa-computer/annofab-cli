"""
AnnofabのアノテーションZIPまたはそれを展開したディレクトリに関するモジュール
"""

import zipfile
from collections.abc import Iterator
from pathlib import Path

from annofabapi.parser import (
    SimpleAnnotationParser,
    lazy_parse_simple_annotation_dir,
    lazy_parse_simple_annotation_zip,
)


def lazy_parse_simple_annotation_by_input_data(annotation_path: Path) -> Iterator[SimpleAnnotationParser]:
    """
    アノテーションZIPを入力データごとに読み込むparserのイテレータを返します。

    Args:
        アノテーションZIPまたは、それを展開したディレクトリのパス

    Returns:
        SimpleAnnotationParserのイテレータ

    Raises:
        ValueError: 指定されたパスが存在しない、またはzipファイルやディレクトリではない場合
    """
    if not annotation_path.exists():
        raise ValueError(f"'{annotation_path}' は存在しません。")

    if annotation_path.is_dir():
        return lazy_parse_simple_annotation_dir(annotation_path)
    elif zipfile.is_zipfile(str(annotation_path)):
        return lazy_parse_simple_annotation_zip(annotation_path)
    else:
        raise ValueError(f"'{annotation_path}'は、zipファイルまたはディレクトリではありません。")
