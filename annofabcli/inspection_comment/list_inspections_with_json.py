"""
検査コメント一覧を出力する。
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Callable, List, Optional

import annofabapi
from annofabapi.models import Inspection

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.visualize import AddProps
from annofabcli.inspection_comment.list_inspections import create_filter_func

logger = logging.getLogger(__name__)

FilterInspectionFunc = Callable[[Inspection], bool]


class ListInspectionCommentWithJsonMain:
    def __init__(self, service: annofabapi.Resource):
        self.service = service
        self.facade = AnnofabApiFacade(service)

    def filter_inspection_list(
        self,
        project_id: str,
        inspection_comment_list: List[Inspection],
        task_id_list: Optional[List[str]] = None,
        filter_inspection_comment: Optional[FilterInspectionFunc] = None,
    ) -> List[Inspection]:
        """
        引数の検査コメント一覧に`commenter_username`など、ユーザが知りたい情報を追加する。

        Args:
            inspection_list: 検査コメント一覧
            filter_inspection: 検索コメントを絞り込むための関数

        Returns:
            情報が追加された検査コメント一覧
        """

        def filter_task_id(e):
            if task_id_list is None or len(task_id_list) == 0:
                return True
            return e["task_id"] in task_id_list

        def filter_local_inspection_comment(e):
            if filter_inspection_comment is None:
                return True
            return filter_inspection_comment(e)

        inspection_list = [
            e for e in inspection_comment_list if filter_local_inspection_comment(e) and filter_task_id(e)
        ]
        visualize = AddProps(self.service, project_id)
        return [visualize.add_properties_to_inspection(e) for e in inspection_list]

    def get_inspection_comment_list(
        self,
        project_id: str,
        inspection_comment_json: Optional[Path],
        task_id_list: Optional[List[str]],
        only_reply: bool,
        exclude_reply: bool,
    ) -> List[Inspection]:

        if inspection_comment_json is None:
            downloading_obj = DownloadingFile(self.service)
            cache_dir = annofabcli.utils.get_cache_dir()
            json_path = cache_dir / f"{project_id}-inspection.json"

            downloading_obj.download_inspection_json(project_id, str(json_path))
        else:
            json_path = inspection_comment_json

        filter_inspection_comment = create_filter_func(only_reply=only_reply, exclude_reply=exclude_reply)
        with json_path.open() as f:
            inspection_comment_list = json.load(f)

        return self.filter_inspection_list(
            project_id,
            inspection_comment_list=inspection_comment_list,
            task_id_list=task_id_list,
            filter_inspection_comment=filter_inspection_comment,
        )


class ListInspectionCommentWithJson(AbstractCommandLineInterface):
    def main(self):
        args = self.args
        project_id = args.project_id
        super().validate_project(project_id, project_member_roles=None)

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        main_obj = ListInspectionCommentWithJsonMain(self.service)
        inspection_comment_list = main_obj.get_inspection_comment_list(
            project_id=project_id,
            inspection_comment_json=args.inspection_comment_json,
            task_id_list=task_id_list,
            exclude_reply=args.exclude_reply,
            only_reply=args.only_reply,
        )

        logger.info(f"検査コメントの件数: {len(inspection_comment_list)}")

        self.print_according_to_format(inspection_comment_list)


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id(
        required=False,
        help_message="対象のタスクのtask_idを指定します。　"
        "`--inspection_comment_json`を指定しないときは、必須です。"
        "`file://`を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )

    reply_comment_group = parser.add_mutually_exclusive_group()
    reply_comment_group.add_argument("--only_reply", action="store_true", help="返信コメントのみを出力する。")
    reply_comment_group.add_argument("--exclude_reply", action="store_true", help="返信コメントを除外して出力する。")

    parser.add_argument(
        "--inspection_comment_json",
        type=str,
        help="検査コメント情報が記載されたJSONファイルのパスを指定すると、JSONに記載された情報を元に検査コメント一覧を出力します。指定しない場合、全件ファイルをダウンロードします。"
        "JSONファイルは`$ annofabcli project download inspection_comment`コマンドで取得できます。",
    )

    argument_parser.add_format(
        choices=[
            FormatArgument.CSV,
            FormatArgument.JSON,
            FormatArgument.PRETTY_JSON,
            FormatArgument.INSPECTION_ID_LIST,
        ],
        default=FormatArgument.CSV,
    )
    argument_parser.add_output()
    argument_parser.add_csv_format()

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListInspectionCommentWithJson(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_with_json"

    subcommand_help = "検査コメント全件ファイルから一覧を出力します。"

    description = "検査コメント全件ファイルから一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
