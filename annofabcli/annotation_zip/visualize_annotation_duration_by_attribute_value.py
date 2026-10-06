import argparse

import annofabcli.common.cli
from annofabcli.annotation_zip.visualize_annotation_duration import add_arguments


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """属性値ごとの区間長の可視化コマンドを登録します。

    Args:
        subparsers: 親パーサー。

    Returns:
        コマンドのパーサー。
    """
    name = "visualize_annotation_duration_by_attribute_value"
    description = "属性値ごとにタスク単位の区間アノテーションの合計長をヒストグラムで可視化します。"
    parser = annofabcli.common.cli.add_parser(subparsers, name, description, description=description)
    add_arguments(parser, by_attribute=True)
    return parser
