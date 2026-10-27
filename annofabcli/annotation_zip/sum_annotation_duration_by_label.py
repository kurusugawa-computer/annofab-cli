import argparse

import annofabcli.common.cli
from annofabcli.annotation_zip.sum_annotation_duration import add_arguments


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """長さ集計コマンドを登録します。

    Args:
        subparsers: 親パーサー。

    Returns:
        コマンドのパーサー。
    """
    name = "sum_annotation_duration_by_label"
    description = "ラベルごとに区間アノテーションの長さ（秒）を合計して出力します。"
    epilog = "オーナーロールまたはアノテーションユーザーロールを持つユーザーで実行してください。"
    parser = annofabcli.common.cli.create_parser(subparsers, name, description, description=description, epilog=epilog)
    add_arguments(parser, by_attribute=False)
    return parser
