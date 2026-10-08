import argparse
import logging
import sys

from annofabapi.models import CommentType, InputDataType, ProjectMemberRole
from annofabapi.plugin import EditorPluginId

import annofabcli.common.cli
from annofabcli.comment.put_comment_simply import AddedSimpleComment, PutCommentSimplyMain
from annofabcli.comment.utils import create_default_inspection_comment_data
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.enums import CustomProjectType
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class CreateInspectionCommentSimply(CommandLine):
    COMMON_MESSAGE = "annofabcli comment create_inspection_simply: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、'--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        required_project_member_roles = [ProjectMemberRole.OWNER] if args.include_complete_task else [ProjectMemberRole.ACCEPTER, ProjectMemberRole.OWNER]
        super().require_project_access(args.project_id, required_project_member_roles)

        comment_data = annofabcli.common.cli.get_json_from_args(args.comment_data)
        custom_project_type = CustomProjectType(args.custom_project_type) if args.custom_project_type is not None else None

        project, _ = self.service.api.get_project(args.project_id)
        if comment_data is None:
            editor_plugin_id = project.get("configuration", {}).get("plugin_id")
            is_3d_point_cloud = editor_plugin_id == EditorPluginId.THREE_DIMENSION.value or custom_project_type == CustomProjectType.THREE_DIMENSION_POINT_CLOUD
            try:
                comment_data = create_default_inspection_comment_data(InputDataType(project["input_data_type"]), is_3d_point_cloud=is_3d_point_cloud)
            except ValueError:
                print(  # noqa: T201
                    f"{self.COMMON_MESSAGE} カスタムプロジェクト（ビルトインのエディタプラグインを使用していない）に検査コメントを作成する場合は、'--comment_data' または '--custom_project_type'を指定してください。",  # noqa: E501
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        task_id_list = get_list_from_args(args.task_id)
        phrase_id_list = get_list_from_args(args.phrase_id)
        main_obj = PutCommentSimplyMain(
            self.service,
            project_id=args.project_id,
            comment_type=CommentType.INSPECTION,
            all_yes=self.all_yes,
            can_include_complete_task=True,
        )
        main_obj.put_comment_for_task_list(
            task_ids=task_id_list,
            comment_info=AddedSimpleComment(comment=args.comment, data=comment_data, phrases=phrase_id_list),
            parallelism=args.parallelism,
            cancel_acceptance=args.include_complete_task,
            include_break_task=args.include_break_task,
            include_on_hold_task=args.include_on_hold_task,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CreateInspectionCommentSimply(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "-t",
        "--task_id",
        type=str,
        nargs="+",
        required=True,
        help=(
            "検査コメントを作成するタスクのtask_idを指定してください。"
            "\n``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。"
            " ファイルを読み込む場合は、ファイル指定を1個だけ渡してください。"
            "直接指定する値や別のファイル指定とは併用できません。"
        ),
    )

    parser.add_argument(
        "--comment",
        type=str,
        required=True,
        help="作成する検査コメントのメッセージを指定します。",
    )

    parser.add_argument("--phrase_id", type=str, nargs="+", help="定型指摘コメントのIDを指定してください。")

    parser.add_argument(
        "--comment_data",
        type=str,
        help="検査コメントを作成する位置や区間をJSON形式で指定します。\n"
        "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。\n"
        "デフォルトの検査コメントの種類と位置は以下の通りです。\n"
        "\n"
        " * 画像プロジェクト：点。先頭画像の左上\n"
        " * 動画プロジェクト：区間。動画の先頭\n"
        " * カスタムプロジェクト(3dpc)：辺が1の立方体。原点\n",
    )

    parser.add_argument(
        "--custom_project_type",
        type=str,
        choices=[e.value for e in CustomProjectType],
        help="[BETA] ビルトインのエディタプラグインを使用していないカスタムプロジェクトの種類を指定します。カスタムプロジェクトに対して、検査コメントの位置を指定しない場合は必須です。\n",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )

    parser.add_argument(
        "--include_break_task",
        action="store_true",
        help="休憩中状態のタスクに対しても検査コメントを作成します。未指定の場合は、休憩中状態のタスクはスキップされます。",
    )

    parser.add_argument(
        "--include_on_hold_task",
        action="store_true",
        help="保留中状態のタスクに対しても検査コメントを作成します。ただし、検査コメントの作成後は保留中状態でなくなります。未指定の場合は、保留中状態のタスクはスキップされます。",
    )

    parser.add_argument(
        "--include_complete_task",
        action="store_true",
        help="オーナーロールで完了状態のタスクに対しても検査コメントを作成します。受入フェーズが完了状態のタスクは、受入を取り消してから検査コメントを作成します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "create_inspection_simply"
    subcommand_help = "``comment create_inspection`` コマンドよりも、簡単に検査コメントを作成します。"
    epilog = "チェッカーロールまたはオーナロールを持つユーザで実行してください。``--include_complete_task`` を指定した場合は、オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
