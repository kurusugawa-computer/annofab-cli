import argparse

import annofabcli.common.cli
from annofabcli.common.video_duration import add_arguments, run_command


def main(args: argparse.Namespace) -> None:
    run_command(args, "input_data", visualize=True)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    parser = annofabcli.common.cli.add_parser(
        subparsers,
        "visualize_video_duration",
        "入力データごとの動画の長さをヒストグラムで可視化します。タスク未使用の動画も含め、各入力データを1回数えます。",
        epilog="オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。",
    )
    add_arguments(parser, visualize=True)
    parser.set_defaults(subcommand_func=main)
    return parser
