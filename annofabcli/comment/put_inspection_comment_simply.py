import argparse
import logging
import sys

from annofabapi.models import CommentType, ProjectMemberRole

import annofabcli.common.cli
from annofabcli.comment.put_comment_simply import AddedSimpleComment, PutCommentSimplyMain
from annofabcli.comment.utils import resolve_inspection_comment_data
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)

DEPRECATED_MESSAGE = (
    "[DEPRECATED] :: `comment put_inspection_simply` コマンドは非推奨です。代わりに `comment create_inspection_simply` コマンドを使用してください。 "
    "`comment put_inspection_simply` コマンドは2027/04/01以降に廃止予定です。"
)


class PutInspectionCommentSimply(CommandLine):
    COMMON_MESSAGE = "annofabcli comment put_inspection_simply: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、'--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        print(DEPRECATED_MESSAGE, file=sys.stderr)  # noqa: T201

        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        super().require_project_access(args.project_id, [ProjectMemberRole.ACCEPTER, ProjectMemberRole.OWNER])

        comment_data = annofabcli.common.cli.get_json_from_args(args.comment_data)

        project, _ = self.service.api.get_project(args.project_id)
        try:
            comment_data = resolve_inspection_comment_data(project, comment_data)
        except ValueError as e:
            print(f"{self.COMMON_MESSAGE} {e}", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        task_id_list = get_list_from_args(args.task_id)
        phrase_id_list = get_list_from_args(args.phrase_id)
        main_obj = PutCommentSimplyMain(self.service, project_id=args.project_id, comment_type=CommentType.INSPECTION, all_yes=self.all_yes)
        main_obj.put_comment_for_task_list(
            task_ids=task_id_list,
            comment_info=AddedSimpleComment(comment=args.comment, data=comment_data, phrases=phrase_id_list),
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PutInspectionCommentSimply(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "-t",
        "--task_id",
        type=str,
        nargs="+",
        required=True,
        help=("検査コメントを付与するタスクのtask_idを指定してください。\n``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。"),
    )

    parser.add_argument(
        "--comment",
        type=str,
        required=True,
        help="付与する検査コメントのメッセージを指定します。",
    )

    parser.add_argument("--phrase_id", type=str, nargs="+", help="定型指摘コメントのIDを指定してください。")

    parser.add_argument(
        "--comment_data",
        type=str,
        help="検査コメントを付与する位置や区間をJSON形式で指定します。\n"
        "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。\n"
        "デフォルトの検査コメントの種類と位置は以下の通りです。\n"
        "\n"
        " * 画像プロジェクト：点。先頭画像の左上\n"
        " * 動画プロジェクト：区間。動画の先頭\n"
        " * カスタムプロジェクト（標準3Dエディタ）：辺が1の立方体。原点\n\n"
        "標準3Dエディタ以外のカスタムプロジェクトへの検査コメント作成はサポートしていません。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "put_inspection_simply"
    subcommand_help = "[DEPRECATED] ``comment put_inspection`` コマンドよりも、簡単に検査コメントを付与します。"
    description = f"{DEPRECATED_MESSAGE}\n``comment put_inspection`` コマンドよりも、簡単に検査コメントを付与します。"
    epilog = "チェッカーロールまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog)
    parse_args(parser)
    return parser
