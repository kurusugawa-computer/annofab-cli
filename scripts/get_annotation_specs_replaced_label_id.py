from __future__ import annotations

import argparse
import subprocess
import traceback
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional


def execute_mask_user_info_command(project_dir: Path, output_project_dir: Path, remainder_options: Optional[list[str]]):
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


def mask_user_info_for_all_project_dir(
    project_root_dir: Path, output_dir: Path, remainder_options: Optional[list[str]]
) -> None:
    for project_dir in project_root_dir.iterdir():
        if not project_dir.is_dir():
            continue

        project_output_dir = output_dir / project_dir.name

        try:
            execute_mask_user_info_command(project_dir, project_output_dir, remainder_options=remainder_options)
        except Exception:  # pylint: disable=broad-except
            print(f"'{project_dir}'のユーザのマスク処理に失敗しました。")
            traceback.print_exc()
            continue


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()

    mask_user_info_for_all_project_dir(args.root_dir, args.output_dir, args.remainder_options)


def create_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description="label_idがUUIDから英語名に置換されたアノテーション仕様のJSONを取得します。アノテーション仕様は変更しません。\n"
        "画面のインポート機能を使って、アノテーション仕様を変更することを想定しています。"
        "【注意】既にアノテーションが存在する状態でlabel_idを変更すると、既存のアノテーション情報が消える恐れがあります。十分注意して、label_idを変更してください。"
    )
    parser.add_argument(
        "-p",
        "--project_id",
        type=str,
        help="Annofabプロジェクトのproject_id",
    )

    parser.add_argument(
        "--label_name",
        type=str,
        nargs="+",
        help="as",
    )


    parser.add_argument(
        "-p",
        "--project_id",
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
