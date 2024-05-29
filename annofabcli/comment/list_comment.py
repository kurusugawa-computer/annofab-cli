from __future__ import annotations

import argparse
import logging
from typing import Any, List, Optional

import pandas
import requests
from annofabapi.models import Comment, CommentType

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import print_according_to_format, print_csv
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


class ListingComments(CommandLine):
    def get_comments(self, project_id: str, task_id: str, input_data_id: str):  # noqa: ANN201
        comments, _ = self.service.api.get_comments(project_id, task_id, input_data_id, query_params={"v": "2"})
        return comments

    def get_comment_list(
        self, project_id: str, task_id_list: List[str], *, comment_type: Optional[CommentType], exclude_reply: bool
    ) -> list[dict[str, Any]]:
        all_comments: List[Comment] = []

        for task_id in task_id_list:
            try:
                task = self.service.wrapper.get_task_or_none(project_id, task_id)
                if task is None:
                    logger.warning(f"タスク'{task_id}'は存在しないので、スキップします。")
                    continue

                input_data_id_list = task["input_data_id_list"]
                logger.debug(f"タスク '{task_id}' に紐づくコメントを取得します。input_dataの個数 = {len(input_data_id_list)}")
                for input_data_id in input_data_id_list:
                    comments = self.get_comments(project_id, task_id, input_data_id)

                    if comment_type is not None:
                        comments = [e for e in comments if e["comment_type"] == comment_type.value]

                    if exclude_reply:
                        # 返信コメントを除外する
                        comments = [e for e in comments if e["comment_node"]["_type"] != "Reply"]

                    all_comments.extend(comments)

            except requests.HTTPError:
                logger.warning(f"タスク task_id = {task_id} のコメントを取得できませんでした。", exc_info=True)

        visualize = AddProps(self.service, project_id)
        all_comments = [visualize.add_properties_to_comment(e) for e in all_comments]
        return all_comments

    def main(self) -> None:
        args = self.args
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        comment_type = CommentType(args.comment_type) if args.comment_type is not None else None

        comment_list = self.get_comment_list(args.project_id, task_id_list, comment_type=comment_type, exclude_reply=args.exclude_reply)

        logger.info(f"コメントの件数: {len(comment_list)}")

        output_format = FormatArgument(args.format)
        if output_format == FormatArgument.CSV:
            df = pandas.json_normalize(comment_list)
            print_csv(df, output=args.output)
        else:
            print_according_to_format(comment_list, output_format, output=args.output)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListingComments(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id(
        required=True,
        help_message="対象のタスクのtask_idを指定します。 ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "--comment_type",
        choices=[CommentType.INSPECTION.value, CommentType.ONHOLD.value],
        help=(f"コメントの種類で絞り込みます。\n\n * {CommentType.INSPECTION.value}: 検査コメント\n * {CommentType.ONHOLD.value}: 保留コメント\n"),
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


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list"
    subcommand_help = "コメント一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help)
    parse_args(parser)
    return parser
