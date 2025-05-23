from __future__ import annotations  # noqa: INP001

import argparse
import subprocess
import traceback
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional


def execute_mask_user_info_command(csv_path: Path, output_csv: Path, remainder_options: Optional[list[str]]) -> None:
    command = [
        "annofabcli",
        "filesystem",
        "mask_user_info",
        "--csv",
        str(csv_path),
        "--csv_header",
        "2",
        "--output",
        str(output_csv),
    ]
    if remainder_options is not None:
        command.extend(remainder_options)

    subprocess.run(command, check=True)


def mask_user_info_for_dir(root_dir: Path, output_dir: Path, remainder_options: Optional[list[str]]) -> None:
    for sub_dirname in [
        "annotation_productivity",
        "inspection_acceptance_productivity",
        "annotation_quality_inspection_comment",
        "annotation_quality_task_rejected_count",
    ]:
        for suffix in ["", "_deviation", "_rank"]:
            path = f"{sub_dirname}/{sub_dirname}{suffix}.csv"
            try:
                execute_mask_user_info_command(root_dir / path, output_dir / path, remainder_options=remainder_options)
            except Exception:  # pylint: disable=broad-except
                print(f"'{root_dir / path}'のユーザー情報のマスク処理に失敗しました。")  # noqa: T201
                traceback.print_exc()
                continue


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()

    mask_user_info_for_dir(args.root_dir, args.output_dir, args.remainder_options)


def create_parser() -> ArgumentParser:
    parser = ArgumentParser(description="`stat_visualization write_performance_rating_csv`コマンドの出力結果である複数のCSVに対して、`filesystem mask_user_info`コマンドを実行します。")
    parser.add_argument(
        "root_dir",
        type=Path,
        help="マスク対象である`stat_visualization write_performance_rating_csv`コマンドの出力先ディレクトリ",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="出力先ディレクトリ。ディレクトリ直下にプロジェクトディレクトリが存在します。",
    )
    parser.add_argument(
        "remainder_options",
        nargs=argparse.REMAINDER,
        type=str,
        help="`filesystem mask_user_info`コマンドに指定するオプション",
    )
    return parser


if __name__ == "__main__":
    main()
