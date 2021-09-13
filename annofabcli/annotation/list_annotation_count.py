import argparse
import copy
import logging
from enum import Enum
from typing import Any, Dict, List, Optional

import annofabapi
import pandas
from annofabapi.models import SingleAnnotation

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.annotation.list_annotation import ListAnnotationMain
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


class GroupBy(Enum):
    TASK_ID = "task_id"
    INPUT_DATA_ID = "input_data_id"


class ListAnnotationCount(AbstractCommandLineInterface):
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

    def get_annotations(
        self, project_id: str, annotation_query: Optional[Dict[str, Any]], task_id: Optional[str] = None
    ) -> List[SingleAnnotation]:
        if annotation_query is not None:
            new_annotation_query = copy.deepcopy(annotation_query)
        else:
            new_annotation_query = {}

        if task_id is not None:
            new_annotation_query.update({"task_id": task_id, "exact_match_task_id": True})

        logger.debug(f"annotation_query: {new_annotation_query}")
        annotation_list = self.service.wrapper.get_all_annotation_list(
            project_id, query_params={"query": new_annotation_query}
        )
        return annotation_list

    def list_annotations(
        self, project_id: str, annotation_query: Optional[Dict[str, Any]], group_by: GroupBy, task_id_list: List[str]
    ):
        """
        アノテーション一覧を出力する
        """

        super().validate_project(project_id, project_member_roles=None)

        all_annotations = []
        if len(task_id_list) > 0:
            for task_id in task_id_list:
                annotations = self.get_annotations(project_id, annotation_query, task_id)
                logger.debug(f"タスク {task_id} のアノテーション一覧の件数: {len(annotations)}")
                if len(annotations) == 10000:
                    logger.warning("アノテーション一覧は10,000件で打ち切られている可能性があります。")
                all_annotations.extend(annotations)
        else:
            annotations = self.get_annotations(project_id, annotation_query)
            if len(annotations) == 10000:
                logger.warning("アノテーション一覧は10,000件で打ち切られている可能性があります。")
            all_annotations.extend(annotations)

        logger.debug(f"アノテーション一覧の件数: {len(all_annotations)}")
        if len(all_annotations) > 0:
            df = self.aggregate_annotations(all_annotations, group_by)
            self.print_csv(df)
        else:
            logger.info(f"アノテーション一覧が0件のため出力しません。")
            return

    def main(self):
        args = self.args
        project_id = args.project_id

        if args.annotation_query is not None:
            cli_annotation_query = annofabcli.common.cli.get_json_from_args(args.annotation_query)
            annotation_query = self.list_annotation_main_obj.modify_annotation_query(project_id, cli_annotation_query)
        else:
            annotation_query = None

        group_by = GroupBy(args.group_by)
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        self.list_annotations(
            args.project_id, annotation_query=annotation_query, group_by=group_by, task_id_list=task_id_list
        )


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
        help="アノテーションの検索クエリをJSON形式で指定します。"
        " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        "クエリのフォーマットは、[getAnnotationList API](https://annofab.com/docs/api/#operation/getAnnotationList)のクエリパラメータの ``query`` キー配下と同じです。"  # noqa: E501
        "さらに追加で、 ``label_name_en`` , ``additional_data_definition_name_en`` , ``choice_name_en`` キーも指定できます。",  # noqa: E501
    )

    argument_parser.add_task_id(
        required=False,
        help_message=(
            "対象のタスクのtask_idを指定します。"
            " ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。"
            "指定した場合、``--annotation_query`` のtask_id, exact_match_task_idが上書きされます"
        ),
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
