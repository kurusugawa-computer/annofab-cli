from __future__ import annotations  # noqa: INP001

import argparse
import subprocess
import traceback
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional


def execute_mask_user_info_command(project_dir: Path, output_project_dir: Path, remainder_options: Optional[list[str]]) -> None:
    command = [
        "annofabcli",
        "stat_visualization",
        "mask_user_info",
        "--dir",
        str(project_dir),
        "--output_dir",
        str(output_project_dir),
    ]
    if remainder_options is not None:
        command.extend(remainder_options)

    subprocess.run(command, check=True)


def mask_user_info_for_all_project_dir(project_root_dir: Path, output_dir: Path, remainder_options: Optional[list[str]]) -> None:
    for project_dir in project_root_dir.iterdir():
        if not project_dir.is_dir():
            continue

        project_output_dir = output_dir / project_dir.name

        try:
            execute_mask_user_info_command(project_dir, project_output_dir, remainder_options=remainder_options)
        except Exception:  # pylint: disable=broad-except
            print(f"'{project_dir}'のユーザのマスク処理に失敗しました。")  # noqa: T201
            traceback.print_exc()
            continue


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()

    mask_user_info_for_all_project_dir(args.root_dir, args.output_dir, args.remainder_options)


def create_parser() -> ArgumentParser:
    parser = ArgumentParser(description="`statistics visualize`コマンドの出力結果である複数のプロジェクトディレクトリに対して、`stat_visualization mask_user_info`コマンドを実行します。")
    parser.add_argument(
        "root_dir",
        type=Path,
        help="`statistics visualize`コマンドの出力結果であるプロジェクトディレクトリが存在するディレクトリ",
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
        help="`stat_visualization mask_user_info`コマンドに指定するオプション",
    )
    return parser


if __name__ == "__main__":
    main()
