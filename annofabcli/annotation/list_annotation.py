from __future__ import annotations

import argparse
import logging
import sys
from typing import Any, Dict, List, Optional

import annofabapi
import pandas
from annofabapi.models import SingleAnnotation

import annofabcli
from annofabcli.annotation.annotation_query import AnnotationQueryForAPI, AnnotationQueryForCLI
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    get_list_from_args,
)
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import get_columns_with_priority
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


class ListAnnotationMain:
    def __init__(self, service: annofabapi.Resource, project_id: str):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.visualize = AddProps(self.service, project_id)

    def get_annotation_list(
        self,
        project_id: str,
        annotation_query: Optional[AnnotationQueryForAPI],
        *,
        task_id: Optional[str] = None,
        input_data_id: Optional[str] = None,
    ) -> List[SingleAnnotation]:
        dict_query = {}
        if annotation_query is not None:
            dict_query.update(annotation_query.to_dict())

        if task_id is not None:
            dict_query.update({"task_id": task_id, "exact_match_task_id": True})

        if input_data_id is not None:
            dict_query.update({"input_data_id": input_data_id, "exact_match_input_data_id": True})

        annotation_list = self.service.wrapper.get_all_annotation_list(project_id, query_params={"query": dict_query})
        return [self.visualize.add_properties_to_single_annotation(annotation) for annotation in annotation_list]

    def get_all_annotation_list(
        self,
        project_id: str,
        annotation_query: Optional[AnnotationQueryForAPI],
        *,
        task_id_list: Optional[List[str]],
        input_data_id_list: Optional[List[str]],
    ) -> List[SingleAnnotation]:
        assert task_id_list is None or input_data_id_list is None, "task_id_listとinput_data_listのどちらかはNoneにしてください。"

        all_annotation_list = []
        UPPER_BOUND = 10_000
        if task_id_list is not None:
            for task_id in task_id_list:
                try:
                    annotation_list = self.get_annotation_list(project_id, annotation_query, task_id=task_id)
                except Exception:
                    logger.warning(f"タスク'{task_id}'のアノテーションの一覧の取得に失敗しました。", exc_info=True)
                    continue
                logger.debug(f"タスク {task_id} のアノテーション一覧の件数: {len(annotation_list)}")
                if len(annotation_list) == UPPER_BOUND:
                    logger.warning(f"アノテーション一覧は{UPPER_BOUND}件で打ち切られている可能性があります。")
                all_annotation_list.extend(annotation_list)
            return all_annotation_list
        elif input_data_id_list is not None:
            for input_data_id in input_data_id_list:
                try:
                    annotation_list = self.get_annotation_list(
                        project_id, annotation_query, input_data_id=input_data_id
                    )
                except Exception:
                    logger.warning(f"入力データ'{input_data_id}'のアノテーションの一覧の取得に失敗しました。", exc_info=True)
                    continue

                logger.debug(f"入力データ'{input_data_id}'のアノテーション一覧の件数: {len(annotation_list)}")
                if len(annotation_list) == UPPER_BOUND:
                    logger.warning(f"アノテーション一覧は{UPPER_BOUND}件で打ち切られている可能性があります。")
                all_annotation_list.extend(annotation_list)
            return all_annotation_list
        else:
            annotation_list = self.get_annotation_list(project_id, annotation_query)
            if len(annotation_list) == UPPER_BOUND:
                logger.warning(f"アノテーション一覧は{UPPER_BOUND}件で打ち切られている可能性があります。")
            return annotation_list


def to_annotation_list_for_csv(annotation_list: List[SingleAnnotation]) -> List[SingleAnnotation]:
    """

    Args:
        annotation_list:

    Returns:

    """

    def to_new_annotation(annotation: Dict[str, Any]) -> Dict[str, Any]:
        detail = annotation["detail"]
        for key, value in detail.items():
            annotation[key] = value
        return annotation

    return [to_new_annotation(a) for a in annotation_list]


class ListAnnotation(AbstractCommandLineInterface):
    COMMON_MESSAGE = "annofabcli annotation list: error:"

    PRIOR_COLUMNS = [
        "project_id",
        "task_id",
        "input_data_id",
        "annotation_id",
        "label_id",
        "label_name_en",
        "data_holding_type",
        "created_datetime",
        "updated_datetime",
        "account_id",
        "user_id",
        "username",
        "data",
    ]

    DROPPED_COLUMNS = [
        "detail",
        "additional_data_list",
        "etag",
        "url",
    ]

    def drop_columns(self, columns: List[str]) -> List[str]:
        for c in self.DROPPED_COLUMNS:
            if c in columns:
                columns.remove(c)
        return columns

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)

    def main(self):
        args = self.args

        project_id = args.project_id
        main_obj = ListAnnotationMain(self.service, project_id=project_id)

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

        annotation_list = main_obj.get_all_annotation_list(
            project_id,
            annotation_query=annotation_query,
            task_id_list=task_id_list,
            input_data_id_list=input_data_id_list,
        )
        logger.debug(f"アノテーション一覧の件数: {len(annotation_list)}")

        if len(annotation_list) > 0:
            if self.str_format == FormatArgument.CSV.value:
                annotation_list_for_csv = to_annotation_list_for_csv(annotation_list)
                df = pandas.DataFrame(annotation_list_for_csv)
                columns = self.drop_columns(get_columns_with_priority(df, prior_columns=self.PRIOR_COLUMNS))
                self.print_csv(df[columns])
            else:
                self.print_according_to_format(annotation_list)
        else:
            logger.info(f"アノテーション一覧の件数が0件のため、出力しません。")


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAnnotation(service, facade, args).main()


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

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON],
        default=FormatArgument.CSV,
    )
    argument_parser.add_csv_format()

    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "list"
    subcommand_help = "アノテーションの一覧を出力します。"
    description = "アノテーションの一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
