from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Optional

from annofabapi.models import CommentType, ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli.comment.put_comment import PutCommentMain, convert_cli_comments
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class PutInspectionComment(CommandLine):
    COMMON_MESSAGE = "annofabcli comment put_inspection: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず '--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        super().validate_project(args.project_id, [ProjectMemberRole.ACCEPTER, ProjectMemberRole.OWNER])

        dict_comments = annofabcli.common.cli.get_json_from_args(args.json)
        if not isinstance(dict_comments, dict):
            print(f"{self.COMMON_MESSAGE} argument --json: JSON形式が不正です。オブジェクトを指定してください。", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
        comments_for_task_list = convert_cli_comments(dict_comments, comment_type=CommentType.INSPECTION)
        main_obj = PutCommentMain(self.service, project_id=args.project_id, comment_type=CommentType.INSPECTION, all_yes=self.all_yes)
        main_obj.add_comments_for_task_list(
            comments_for_task_list=comments_for_task_list,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PutInspectionComment(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    SAMPLE_JSON = {"task1": {"input_data1": [{"comment": "type属性が間違っています。", "data": {"x": 10, "y": 20, "_type": "Point"}}]}}  # noqa: N806
    parser.add_argument(
        "--json",
        type=str,
        help=(f"付与する検査コメントの内容をJSON形式で指定してください。``file://`` を先頭に付けると、JSON形式のファイルを指定できます。\n\n(ex)  ``{json.dumps(SAMPLE_JSON, ensure_ascii=False)}``"),
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "put_inspection"
    subcommand_help = "検査コメントを付与します"
    description = "検査コメントを付与します。"
    epilog = "チェッカーロールまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
