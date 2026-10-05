import argparse

import annofabcli.common.cli
from annofabcli.common.video_duration import add_arguments, run_command


def main(args: argparse.Namespace) -> None:
    run_command(args, "task", visualize=False)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    parser = annofabcli.common.cli.add_parser(
        subparsers,
        "list_video_duration",
        "各タスクの動画の長さを出力します。",
        epilog="オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。",
    )
    add_arguments(parser, visualize=False)
    parser.set_defaults(subcommand_func=main)
    return parser
