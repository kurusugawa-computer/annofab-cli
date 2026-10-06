import argparse

import annofabcli.common.cli
from annofabcli.annotation_zip.sum_annotation_duration import add_arguments


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """長さ集計コマンドを登録します。

    Args:
        subparsers: 親パーサー。

    Returns:
        コマンドのパーサー。
    """
    name = "sum_annotation_duration_by_attribute_value"
    description = "属性値ごとに区間アノテーションの長さ（秒）を合計して出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, name, description, description=description)
    add_arguments(parser, by_attribute=True)
    return parser
