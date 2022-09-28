import argparse
import json
import logging
from typing import Optional

import annofabcli
import annofabcli.common.cli
from annofabcli.comment.delete_comment import DeleteComment
from annofabcli.common.cli import ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteComment(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    JSON_SAMPLE = {"task_id1": {"input_data_id1": ["comment_id1", "comment_id2"]}}
    parser.add_argument(
        "--json",
        type=str,
        help=("削除する検査コメントIDをJSON形式で指定してください。\n" f"(ex) '{json.dumps(JSON_SAMPLE)}' \n"),
    )

    parser.add_argument(
        "--parallelism", type=int, help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "delete"
    subcommand_help = "[DEPRECATED] 検査コメントを削除します。"
    description = (
        "[DEPRECATED] 検査コメントを削除します。\n【注意】他人の検査コメントや他のフェーズで付与された検査コメントを削除できてしまいます。"
        "2022/12/01以降に廃止する予定です。替わりに ``annofabcli comment delete`` コマンドを利用してください。"
    )

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
