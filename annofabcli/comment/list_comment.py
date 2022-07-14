import argparse
import logging
from pathlib import Path
from typing import List, Optional

import requests
from annofabapi.models import Comment

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


class ListingComments(AbstractCommandLineInterface):
    def get_comments(self, project_id: str, task_id: str, input_data_id: str):
        comments, _ = self.service.api.get_comments(project_id, task_id, input_data_id, query_params={"v": "2"})
        return comments

    def list_comments(self, project_id: str, task_id_list: List[str], output_file: Path):
        all_comments: List[Comment] = []

        for task_id in task_id_list:
            try:
                task = self.service.wrapper.get_task_or_none(project_id, task_id)
                if task is None:
                    logger.warning(f"タスク'{task_id}'は存在しないので、スキップします。")
                    continue

                input_data_id_list = task["input_data_id_list"]
                logger.info(f"タスク '{task_id}' に紐づくコメントを取得します。input_dataの個数 = {len(input_data_id_list)}")
                for input_data_id in input_data_id_list:
                    comments = self.get_comments(project_id, task_id, input_data_id)
                    all_comments.extend(comments)

            except requests.HTTPError:
                logger.warning(f"タスク task_id = {task_id} のコメントを取得できませんでした。", exc_info=True)

        logger.info(f"対象タスクに紐付いたコメントをすべて取得しました。output={output_file}")

        visualize = AddProps(self.service, project_id)
        all_comments = [visualize.add_properties_to_comment(e) for e in all_comments]
        self.print_according_to_format(all_comments)

    def main(self):
        args = self.args
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

        self.list_comments(
            args.project_id,
            task_id_list,
            output_file=args.output,
        )


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListingComments(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id(
        required=True,
        help_message="対象のタスクのtask_idを指定します。" " ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )

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


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "list"
    subcommand_help = "コメント一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help)
    parse_args(parser)
    return parser
