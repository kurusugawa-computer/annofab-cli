import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import annofabapi
import pandas
from annofabapi.dataclass.task import Task

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import TaskQuery, match_task_with_query
from annofabcli.common.utils import get_columns_with_priority
from annofabcli.common.visualize import AddProps
from annofabcli.task.list_tasks import ListTasks

logger = logging.getLogger(__name__)


class ListTasksWithJsonMain:
    def __init__(self, service: annofabapi.Resource):
        self.service = service
        self.facade = AnnofabApiFacade(service)

    @staticmethod
    def match_task_with_conditions(
        task: Dict[str, Any],
        task_id_set: Optional[Set[str]] = None,
        task_query: Optional[TaskQuery] = None,
    ) -> bool:
        result = True

        dc_task = Task.from_dict(task)
        result = result and match_task_with_query(dc_task, task_query)
        if task_id_set is not None:
            result = result and (dc_task.task_id in task_id_set)
        return result

    def get_task_list(
        self,
        project_id: str,
        task_json: Optional[Path],
        task_id_list: Optional[List[str]] = None,
        task_query: Optional[TaskQuery] = None,
        is_latest: bool = False,
        wait_options: Optional[WaitOptions] = None,
    ) -> List[Dict[str, Any]]:
        if task_json is None:
            downloading_obj = DownloadingFile(self.service)
            cache_dir = annofabcli.utils.get_cache_dir()
            json_path = cache_dir / f"{project_id}-task.json"

            downloading_obj.download_task_json(
                project_id, str(json_path), is_latest=is_latest, wait_options=wait_options
            )
        else:
            json_path = task_json

        logger.debug(f"{json_path} を読み込んでいます。")
        with json_path.open() as f:
            task_list = json.load(f)

        if task_query is not None:
            task_query = self.facade.set_account_id_of_task_query(project_id, task_query)

        logger.debug(f"出力対象のタスクを抽出しています。")
        task_id_set = set(task_id_list) if task_id_list is not None else None
        filtered_task_list = [
            e for e in task_list if self.match_task_with_conditions(e, task_query=task_query, task_id_set=task_id_set)
        ]

        visualize_obj = AddProps(self.service, project_id)
        return [visualize_obj.add_properties_to_task(e) for e in filtered_task_list]


class ListTasksWithJson(AbstractCommandLineInterface):
    def main(self):
        args = self.args

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = (
            TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query))
            if args.task_query is not None
            else None
        )
        wait_options = (
            WaitOptions.from_dict(annofabcli.common.cli.get_json_from_args(args.wait_options))
            if args.wait_options is not None
            else None
        )

        project_id = args.project_id
        super().validate_project(project_id, project_member_roles=None)

        main_obj = ListTasksWithJsonMain(self.service)
        task_list = main_obj.get_task_list(
            project_id=project_id,
            task_json=args.task_json,
            task_id_list=task_id_list,
            task_query=task_query,
            is_latest=args.latest,
            wait_options=wait_options,
        )

        logger.debug(f"タスク一覧の件数: {len(task_list)}")

        if len(task_list) > 0:
            if self.str_format == FormatArgument.CSV.value:
                task_list = self.search_with_jmespath_expression(task_list)
                df = pandas.DataFrame(task_list)
                columns = get_columns_with_priority(df, prior_columns=ListTasks.PRIOR_COLUMNS)
                self.print_csv(df[columns])
            else:
                self.print_according_to_format(task_list)
        else:
            logger.info(f"タスク一覧の件数が0件のため、出力しません。")


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListTasksWithJson(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_query()
    argument_parser.add_task_id(required=False)

    parser.add_argument(
        "--task_json",
        type=Path,
        help="タスク情報が記載されたJSONファイルのパスを指定すると、JSONに記載された情報を元にタスク一覧を出力します。"
        "指定しない場合、全件ファイルをダウンロードします。"
        "JSONファイルは`$ annofabcli project download task`コマンドで取得できます。",
    )

    parser.add_argument(
        "--latest", action="store_true", help="最新のタスク一覧ファイルを参照します。このオプションを指定すると、タスク一覧ファイルを更新するのに約5分以上待ちます。"
    )

    parser.add_argument(
        "--wait_options",
        type=str,
        help="タスク一覧ファイルの更新が完了するまで待つ際のオプションを、JSON形式で指定してください。"
        "`file://`を先頭に付けるとjsonファイルを指定できます。"
        'デフォルは`{"interval":60, "max_tries":360}` です。'
        "`interval`:完了したかを問い合わせる間隔[秒], "
        "`max_tires`:完了したかの問い合わせを最大何回行うか。",
    )

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON, FormatArgument.TASK_ID_LIST],
        default=FormatArgument.CSV,
    )
    argument_parser.add_output()
    argument_parser.add_csv_format()

    argument_parser.add_query()
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_with_json"
    subcommand_help = "タスク全件ファイルから一覧を出力します。"
    description = "タスク全件ファイルから一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
