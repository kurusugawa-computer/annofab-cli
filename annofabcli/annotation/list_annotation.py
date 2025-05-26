from __future__ import annotations

import argparse
import logging
import sys
from typing import Any, Optional

import annofabapi
import pandas
from annofabapi.models import SingleAnnotation

import annofabcli
from annofabcli.annotation.annotation_query import AnnotationQueryForAPI, AnnotationQueryForCLI
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    get_list_from_args,
)
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import get_columns_with_priority
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


def remove_unnecessary_keys_from_annotation(annotation: dict[str, Any]) -> None:
    """
    アノテーション情報から不要なキーを取り除きます。
    システム内部用のプロパティなど、annofab-cliを使う上で不要な情報を削除します。

    Args:
        annotation: (IN/OUT) 入力データ情報。引数が変更されます。
    """
    body = annotation["detail"]["body"]
    if body["_type"] == "Outer":
        # 認証済一時URLはファイルなどに保存すると、セキュリティ的によくないので取り除く
        # CLIでetagを出力するユースケースないと思うので、etagも取り除く
        body.pop("url", None)
        body.pop("etag", None)


class ListAnnotationMain:
    def __init__(self, service: annofabapi.Resource, project_id: str) -> None:
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
    ) -> list[SingleAnnotation]:
        dict_query = {}
        if annotation_query is not None:
            dict_query.update(annotation_query.to_dict())

        if task_id is not None:
            dict_query.update({"task_id": task_id, "exact_match_task_id": True})

        if input_data_id is not None:
            dict_query.update({"input_data_id": input_data_id, "exact_match_input_data_id": True})

        annotation_list = self.service.wrapper.get_all_annotation_list(project_id, query_params={"query": dict_query, "v": "2"})
        return [self.visualize.add_properties_to_single_annotation(annotation) for annotation in annotation_list]

    def get_all_annotation_list(
        self,
        project_id: str,
        annotation_query: Optional[AnnotationQueryForAPI],
        *,
        task_id_list: Optional[list[str]],
        input_data_id_list: Optional[list[str]],
    ) -> list[SingleAnnotation]:
        assert task_id_list is None or input_data_id_list is None, "task_id_listとinput_data_listのどちらかはNoneにしてください。"

        all_annotation_list = []
        UPPER_BOUND = 10_000  # noqa: N806
        if task_id_list is not None:
            for task_id in task_id_list:
                try:
                    annotation_list = self.get_annotation_list(project_id, annotation_query, task_id=task_id)
                except Exception:
                    logger.warning(f"タスク(task_id='{task_id}')のアノテーションの一覧の取得に失敗しました。", exc_info=True)
                    continue
                logger.debug(f"タスク(task_id='{task_id}')のアノテーション一覧の件数: {len(annotation_list)}")
                if len(annotation_list) == UPPER_BOUND:
                    logger.warning(f"タスク(task_id='{task_id}')のアノテーション一覧は{UPPER_BOUND}件で打ち切られている可能性があります。")
                all_annotation_list.extend(annotation_list)
            return all_annotation_list
        elif input_data_id_list is not None:
            for input_data_id in input_data_id_list:
                try:
                    annotation_list = self.get_annotation_list(project_id, annotation_query, input_data_id=input_data_id)
                except Exception:
                    logger.warning(f"入力データ(input_data_id='{input_data_id}')のアノテーションの一覧の取得に失敗しました。", exc_info=True)
                    continue

                logger.debug(f"入力データ(input_data_id='{input_data_id}')のアノテーション一覧の件数: {len(annotation_list)}")
                if len(annotation_list) == UPPER_BOUND:
                    logger.warning(f"入力データ(input_data_id='{input_data_id}')のアノテーション一覧は{UPPER_BOUND}件で打ち切られている可能性があります。")
                all_annotation_list.extend(annotation_list)
            return all_annotation_list
        else:
            annotation_list = self.get_annotation_list(project_id, annotation_query)
            if len(annotation_list) == UPPER_BOUND:
                logger.warning(f"アノテーション一覧は{UPPER_BOUND}件で打ち切られている可能性があります。")
            return annotation_list


def to_annotation_list_for_csv(annotation_list: list[SingleAnnotation]) -> list[SingleAnnotation]:
    """

    Args:
        annotation_list:

    Returns:

    """

    def to_new_annotation(annotation: dict[str, Any]) -> dict[str, Any]:
        detail = annotation["detail"]
        for key, value in detail.items():
            annotation[f"detail.{key}"] = value
        annotation.pop("detail", None)
        return annotation

    return [to_new_annotation(a) for a in annotation_list]


class ListAnnotation(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation list: error:"

    PRIOR_COLUMNS = [  # noqa: RUF012
        "project_id",
        "task_id",
        "input_data_id",
        "updated_datetime",
        "detail.annotation_id",
        "detail.label_id",
        "detail.label_name_en",
        "detail.data_holding_type",
        "detail.account_id",
        "detail.user_id",
        "detail.username",
        "detail.created_datetime",
        "detail.updated_datetime",
        "detail.body",
        "detail.additional_data_list",
    ]

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace) -> None:
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)

    def main(self) -> None:
        args = self.args

        project_id = args.project_id
        main_obj = ListAnnotationMain(self.service, project_id=project_id)

        if args.annotation_query is not None:
            annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params={"v": "3"})
            try:
                dict_annotation_query = get_json_from_args(args.annotation_query)
                annotation_query_for_cli = AnnotationQueryForCLI.from_dict(dict_annotation_query)
                annotation_query = annotation_query_for_cli.to_query_for_api(annotation_specs)
            except ValueError as e:
                print(f"{self.COMMON_MESSAGE} argument '--annotation_query' の値が不正です。{e}", file=sys.stderr)  # noqa: T201
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
        # 不要なキーを取り除く
        for annotation in annotation_list:
            remove_unnecessary_keys_from_annotation(annotation)

        logger.debug(f"アノテーション {len(annotation_list)} 件を出力します。")

        if self.str_format == FormatArgument.CSV.value:
            annotation_list_for_csv = to_annotation_list_for_csv(annotation_list)
            df = pandas.DataFrame(annotation_list_for_csv)
            columns = get_columns_with_priority(df, prior_columns=self.PRIOR_COLUMNS)
            if len(df) == 0:
                # 列を作成するために、何らかの値を設定する
                df[self.PRIOR_COLUMNS] = None
            else:
                df = df[columns]
            self.print_csv(df)
        else:
            self.print_according_to_format(annotation_list)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "-aq",
        "--annotation_query",
        type=str,
        help="アノテーションの検索クエリをJSON形式で指定します。 ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
    )

    id_group = parser.add_mutually_exclusive_group()

    id_group.add_argument(
        "-t",
        "--task_id",
        nargs="+",
        help=("対象のタスクのtask_idを指定します。 ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。"),
    )

    id_group.add_argument(
        "-i",
        "--input_data_id",
        nargs="+",
        help=("対象の入力データのinput_data_idを指定します。 ``file://`` を先頭に付けると、input_data_idの一覧が記載されたファイルを指定できます。"),
    )

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON],
        default=FormatArgument.CSV,
    )

    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list"
    subcommand_help = "アノテーションの一覧を出力します。"
    description = "アノテーションの一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
