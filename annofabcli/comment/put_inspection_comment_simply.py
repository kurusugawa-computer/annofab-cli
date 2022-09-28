import argparse
import logging
import sys
from typing import Optional

from annofabapi.models import CommentType, InputDataType, ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli.comment.put_comment_simply import AddedSimpleComment, PutCommentSimplyMain
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.enums import CustomProjectType
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class PutInspectionCommentSimply(AbstractCommandLineInterface):

    COMMON_MESSAGE = "annofabcli comment put_inspection_simply: error:"

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

        comment_data = annofabcli.common.cli.get_json_from_args(args.comment_data)
        custom_project_type = (
            CustomProjectType(args.custom_project_type) if args.custom_project_type is not None else None
        )

        project, _ = self.service.api.get_project(args.project_id)
        if comment_data is None:
            if project["input_data_type"] == InputDataType.IMAGE.value:
                comment_data = {"x": 0, "y": 0, "_type": "Point"}
            elif project["input_data_type"] == InputDataType.MOVIE.value:
                # 注意：少なくとも0.1秒以上の区間にしないと、Annofab上で検査コメントを確認できない
                comment_data = {"start": 0, "end": 100, "_type": "Time"}
            elif project["input_data_type"] == InputDataType.CUSTOM.value:
                if custom_project_type == CustomProjectType.THREE_DIMENSION_POINT_CLOUD:
                    comment_data = {
                        "data": '{"kind": "CUBOID", "shape": {"dimensions": {"width": 1.0, "height": 1.0, "depth": 1.0}, "location": {"x": 0.0, "y": 0.0, "z": 0.0}, "rotation": {"x": 0.0, "y": 0.0, "z": 0.0}, "direction": {"front": {"x": 1.0, "y": 0.0, "z": 0.0}, "up": {"x": 0.0, "y": 0.0, "z": 1.0}}}, "version": "2"}',  # noqa: E501
                        "_type": "Custom",
                    }
                else:
                    print(
                        f"{self.COMMON_MESSAGE}: カスタムプロジェクトに検査コメントを付与する場合は、'--comment_data' または '--custom_project_type'を指定してください。",  # noqa: E501
                        file=sys.stderr,
                    )
                    sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        task_id_list = get_list_from_args(args.task_id)
        phrase_id_list = get_list_from_args(args.phrase_id)
        main_obj = PutCommentSimplyMain(
            self.service, project_id=args.project_id, comment_type=CommentType.INSPECTION, all_yes=self.all_yes
        )
        main_obj.put_comment_for_task_list(
            task_ids=task_id_list,
            comment_info=AddedSimpleComment(comment=args.comment, data=comment_data, phrases=phrase_id_list),
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PutInspectionCommentSimply(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "-t",
        "--task_id",
        type=str,
        nargs="+",
        required=True,
        help=("検査コメントを付与するタスクのtask_idを指定してください。\n" "``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。"),
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
        " * カスタムプロジェクト(3dpc)：辺が1の立方体。原点\n",
    )

    parser.add_argument(
        "--custom_project_type",
        type=str,
        choices=[e.value for e in CustomProjectType],
        help="[BETA] カスタムプロジェクトの種類を指定します。カスタムプロジェクトに対して、検査コメントの位置を指定しない場合は必須です。\n"
        "※ Annofabの情報だけでは'3dpc'プロジェクトかどうかが分からないため、指定する必要があります。",
    )

    parser.add_argument(
        "--parallelism", type=int, help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "put_inspection_simply"
    subcommand_help = "``comment put_inspection`` コマンドよりも、簡単に検査コメントを付与します。"
    epilog = "チェッカーロールまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
