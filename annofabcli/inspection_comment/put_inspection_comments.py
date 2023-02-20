import argparse
import logging
from typing import Optional

import annofabcli
import annofabcli.common.cli
from annofabcli.comment.put_inspection_comment import PutInspectionComment
from annofabcli.comment.put_inspection_comment import parse_args as parse_args_in_put_inspection_comment
from annofabcli.common.cli import build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    obj = PutInspectionComment(service, facade, args)
    obj.COMMON_MESSAGE = "annofabcli inspection_comment put: error:"
    obj.main()


def parse_args(parser: argparse.ArgumentParser):
    parse_args_in_put_inspection_comment(parser)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "put"
    subcommand_help = "[DEPRECATED] 検査コメントを付与します。"
    description = (
        "[DEPRECATED] 検査コメントを付与します。\n2022/12/01以降に廃止する予定です。替わりに ``annofabcli comment put_inspection`` コマンドを利用してください。"
    )

    epilog = "チェッカーロールまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog
    )
    parse_args(parser)
    return parser
