import argparse
import json
import logging
import sys
from typing import Optional

from annofabapi.models import CommentType, ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli.comment.delete_comment import DeleteCommentMain
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class DeleteInspectionComment(AbstractCommandLineInterface):
    COMMON_MESSAGE = "annofabcli comment delete_inspection: error:"

    def validate(self, args: argparse.Namespace) -> bool:

        if args.parallelism is not None and not args.yes:
            print(
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず '--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        super().validate_project(args.project_id, [ProjectMemberRole.ACCEPTER, ProjectMemberRole.OWNER])

        dict_comments = annofabcli.common.cli.get_json_from_args(args.json)
        main_obj = DeleteCommentMain(
            self.service, project_id=args.project_id, comment_type=CommentType.INSPECTION, all_yes=self.all_yes
        )
        main_obj.delete_comments_for_task_list(
            inspection_ids_for_task_list=dict_comments,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteInspectionComment(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    JSON_SAMPLE = {"task_id1": {"input_data_id1": ["comment_id1", "comment_id2"]}}
    parser.add_argument(
        "--json",
        type=str,
        help=("削除するコメントのcomment_idをJSON形式で指定してください。\n" f"(ex) '{json.dumps(JSON_SAMPLE)}' \n"),
    )

    parser.add_argument(
        "--parallelism", type=int, help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "delete"
    subcommand_help = "検査コメントを削除します。"
    description = "検査コメントを削除します。\n【注意】他人の検査コメントや他のフェーズで付与された検査コメントも削除できてしまいます。"
    epilog = "チェッカーロールまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
