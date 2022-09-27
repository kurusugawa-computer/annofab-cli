"""
コメント一覧を出力する。
"""
from __future__ import annotations

import argparse
import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Collection, Optional

import annofabapi
from annofabapi.models import CommentType

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


class ListAllCommentMain:
    def __init__(self, service: annofabapi.Resource):
        self.service = service

    def get_all_comment(
        self,
        project_id: str,
        comment_json: Optional[Path],
        task_ids: Optional[Collection[str]],
        comment_type: Optional[CommentType],
        exclude_reply: bool,
    ) -> list[dict[str, Any]]:

        if comment_json is None:
            downloading_obj = DownloadingFile(self.service)
            with tempfile.NamedTemporaryFile() as temp_file:
                json_path = Path(temp_file.name)
                downloading_obj.download_comment_json(project_id, str(json_path))
                with json_path.open(encoding="utf-8") as f:
                    comment_list = json.load(f)

        else:
            json_path = comment_json
            with json_path.open(encoding="utf-8") as f:
                comment_list = json.load(f)

        if task_ids is not None:
            task_id_set = set(task_ids)
            comment_list = [e for e in comment_list if e["task_id"] in task_id_set]

        if comment_type is not None:
            comment_list = [e for e in comment_list if e["comment_type"] == comment_type.value]

        if exclude_reply:
            # 返信コメントを除外する
            comment_list = [e for e in comment_list if e["comment_node"]["_type"] != "Reply"]

        visualize = AddProps(self.service, project_id)
        comment_list = [visualize.add_properties_to_comment(e) for e in comment_list]
        return comment_list


class ListAllComment(AbstractCommandLineInterface):
    def main(self):
        args = self.args
        project_id = args.project_id
        super().validate_project(project_id, project_member_roles=None)

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        comment_type = CommentType(args.comment_type) if args.comment_type is not None else None

        main_obj = ListAllCommentMain(self.service)
        comment_list = main_obj.get_all_comment(
            project_id=project_id,
            comment_json=args.comment_json,
            task_ids=task_id_list,
            comment_type=comment_type,
            exclude_reply=args.exclude_reply,
        )

        logger.info(f"コメントの件数: {len(comment_list)}")
        self.print_according_to_format(comment_list)


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id(
        required=False,
        help_message=("対象のタスクのtask_idを指定します。 \n" "``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。"),
    )

    parser.add_argument(
        "--comment_type",
        choices=[CommentType.INSPECTION.value, CommentType.ONHOLD.value],
        help=(
            "コメントの種類で絞り込みます。\n\n"
            f" * {CommentType.INSPECTION.value}: 検査コメント\n"
            f" * {CommentType.ONHOLD.value}: 保留コメント\n"
        ),
    )

    parser.add_argument(
        "--comment_json",
        type=Path,
        help="コメント情報が記載されたJSONファイルのパスを指定すると、JSONに記載された情報を元にコメント一覧を出力します。\n"
        "JSONファイルは ``$ annofabcli comment download`` コマンドで取得できます。",
    )

    parser.add_argument("--exclude_reply", action="store_true", help="返信コメントを除外します。")

    argument_parser.add_format(
        choices=[
            FormatArgument.CSV,
            FormatArgument.JSON,
            FormatArgument.PRETTY_JSON,
            FormatArgument.COMMENT_ID_LIST,
        ],
        default=FormatArgument.CSV,
    )
    argument_parser.add_output()
    argument_parser.add_csv_format()

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAllComment(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "list_all"
    subcommand_help = "すべてのコメントの一覧を出力します。"
    description = (
        "すべてのコメントの一覧を出力します。\n"
        "コメント一覧は、コマンドを実行した日の02:00(JST)頃の状態です。最新のコメント情報を取得したい場合は、 ``annofabcli comment list`` コマンドを実行してください。"
    )

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
