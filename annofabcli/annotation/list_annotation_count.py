import argparse
import logging
import sys
from enum import Enum
from typing import List, Optional

import annofabapi
import pandas
from annofabapi.models import SingleAnnotation

import annofabcli
from annofabcli.annotation.annotation_query import AnnotationQueryForCLI
from annofabcli.annotation.list_annotation import ListAnnotationMain
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    get_list_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


class GroupBy(Enum):
    TASK_ID = "task_id"
    INPUT_DATA_ID = "input_data_id"


class ListAnnotationCount(AbstractCommandLineInterface):
    COMMON_MESSAGE = "annofabcli annotation list_count: error:"

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)
        self.list_annotation_main_obj = ListAnnotationMain(service, project_id=args.project_id)

    @staticmethod
    def aggregate_annotations(annotations: List[SingleAnnotation], group_by: GroupBy) -> pandas.DataFrame:
        df = pandas.DataFrame(annotations)
        df = df[["task_id", "input_data_id"]]
        df["annotation_count"] = 1

        if group_by == GroupBy.INPUT_DATA_ID:
            return df.groupby(["task_id", "input_data_id"], as_index=False).count()

        elif group_by == GroupBy.TASK_ID:
            return df.groupby(["task_id"], as_index=False).count().drop(["input_data_id"], axis=1)

        else:
            return pandas.DataFrame()

    def main(self):
        args = self.args
        project_id = args.project_id

        if args.annotation_query is not None:
            annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params={"v": "2"})
            try:
                dict_annotation_query = get_json_from_args(args.annotation_query)
                annotation_query_for_cli = AnnotationQueryForCLI.from_dict(dict_annotation_query)
                annotation_query = annotation_query_for_cli.to_query_for_api(annotation_specs)
            except ValueError as e:
                print(f"{self.COMMON_MESSAGE} argument '--annotation_query' の値が不正です。{e}", file=sys.stderr)
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
        else:
            annotation_query = None

        task_id_list = get_list_from_args(args.task_id) if args.task_id is not None else None
        input_data_id_list = get_list_from_args(args.input_data_id) if args.input_data_id is not None else None

        super().validate_project(project_id, project_member_roles=None)
        all_annotation_list = self.list_annotation_main_obj.get_all_annotation_list(
            project_id,
            annotation_query=annotation_query,
            task_id_list=task_id_list,
            input_data_id_list=input_data_id_list,
        )

        group_by = GroupBy(args.group_by)

        logger.debug(f"アノテーション一覧の件数: {len(all_annotation_list)}")
        if len(all_annotation_list) > 0:
            df = self.aggregate_annotations(all_annotation_list, group_by)
            self.print_csv(df)
        else:
            logger.info(f"アノテーション一覧が0件のため出力しません。")
            return


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAnnotationCount(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "-aq",
        "--annotation_query",
        type=str,
        help="アノテーションの検索クエリをJSON形式で指定します。" " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
    )

    id_group = parser.add_mutually_exclusive_group()

    id_group.add_argument(
        "-t",
        "--task_id",
        nargs="+",
        help=("対象のタスクのtask_idを指定します。" " ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。"),
    )

    id_group.add_argument(
        "-i",
        "--input_data_id",
        nargs="+",
        help=("対象の入力データのinput_data_idを指定します。" " ``file://`` を先頭に付けると、input_data_idの一覧が記載されたファイルを指定できます。"),
    )

    parser.add_argument(
        "--group_by",
        type=str,
        choices=[GroupBy.TASK_ID.value, GroupBy.INPUT_DATA_ID.value],
        default=GroupBy.TASK_ID.value,
        help="アノテーションの個数をどの単位で集約するかを指定してます。",
    )

    argument_parser.add_output()
    argument_parser.add_csv_format()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "list_count"
    subcommand_help = "task_idまたはinput_data_idで集約したアノテーションの個数を出力します。"
    description = "task_idまたはinput_data_idで集約したアノテーションの個数を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
