"""
アノテーション一覧を出力する
"""
import argparse
import logging
from enum import Enum
from typing import Any, Dict, List, Optional

import annofabapi
import more_itertools
import pandas
from annofabapi.models import AdditionalDataDefinitionV1, SingleAnnotation

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


class GroupBy(Enum):
    TASK_ID = "task_id"
    INPUT_DATA_ID = "input_data_id"


class ListAnnotationCount(AbstractCommandLineInterface):
    """
    タスクの一覧を表示する
    """

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)

    @staticmethod
    def _modify_attribute_of_query(
        attribute_query: Dict[str, Any], additional_data_definition: AdditionalDataDefinitionV1
    ) -> Dict[str, Any]:
        if "choice_name_en" in attribute_query:
            choice_info = more_itertools.first_true(
                additional_data_definition["choices"],
                pred=lambda e: AnnofabApiFacade.get_choice_name_en(e) == attribute_query["choice_name_en"],
            )

            if choice_info is not None:
                attribute_query["choice"] = choice_info["choice_id"]
            else:
                logger.warning(f"choice_name_en = {attribute_query['choice_name_en']} の選択肢は存在しませんでした。")

        return attribute_query

    @staticmethod
    def _find_additional_data_with_name(
        additional_data_definitions: List[AdditionalDataDefinitionV1], name: str
    ) -> Optional[AdditionalDataDefinitionV1]:

        additional_data_definition = more_itertools.first_true(
            additional_data_definitions,
            pred=lambda e: AnnofabApiFacade.get_additional_data_definition_name_en(e) == name,
        )
        return additional_data_definition

    @staticmethod
    def _find_additional_data_with_id(
        additional_data_definitions: List[AdditionalDataDefinitionV1], definition_id: str
    ) -> Optional[AdditionalDataDefinitionV1]:

        additional_data_definition = more_itertools.first_true(
            additional_data_definitions, pred=lambda e: e["additional_data_definition_id"] == definition_id
        )
        return additional_data_definition

    def _modify_attributes_of_query(
        self, attributes_of_query: List[Dict[str, Any]], definitions: List[AdditionalDataDefinitionV1]
    ) -> List[Dict[str, Any]]:
        for attribute_query in attributes_of_query:
            definition_name = attribute_query.get("additional_data_definition_name_en")
            if definition_name is not None:
                additional_data_definition = self._find_additional_data_with_name(definitions, definition_name)
                if additional_data_definition is None:
                    logger.warning(
                        f"additional_data_definition_name_name_en = {attribute_query['additional_data_definition_name_en']} の属性は存在しませんでした。"  # noqa: E501
                    )
                    continue

                if additional_data_definition is not None:
                    attribute_query["additional_data_definition_id"] = additional_data_definition[
                        "additional_data_definition_id"
                    ]

            definition_id = attribute_query["additional_data_definition_id"]
            additional_data_definition = self._find_additional_data_with_id(definitions, definition_id)
            if additional_data_definition is None:
                logger.warning(
                    f"additional_data_definition_id = {attribute_query['additional_data_definition_id']} の属性は存在しませんでした。"  # noqa: E501
                )
                continue

            self._modify_attribute_of_query(attribute_query, additional_data_definition)

        return attributes_of_query

    def _modify_annotation_query(
        self, project_id: str, annotation_query: Dict[str, Any], task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        アノテーション検索クエリを修正する。
        * ``label_name_en`` から ``label_id`` に変換する。
        * ``additional_data_definition_name_en`` から ``additional_data_definition_id`` に変換する。
        * ``choice_name_en`` から ``choice`` に変換する。

        Args:
            project_id:
            annotation_query:
            task_id: 検索対象のtask_id

        Returns:
            修正したタスク検索クエリ

        """

        annotation_specs, _ = self.service.api.get_annotation_specs(project_id)
        specs_labels = annotation_specs["labels"]

        # label_name_en から label_idを設定
        if "label_name_en" in annotation_query:
            label_name_en = annotation_query["label_name_en"]
            label = more_itertools.first_true(
                specs_labels, pred=lambda e: AnnofabApiFacade.get_label_name_en(e) == label_name_en
            )
            if label is not None:
                annotation_query["label_id"] = label["label_id"]
            else:
                logger.warning(f"label_name_en: {label_name_en} の label_id が見つかりませんでした。")

        if annotation_query.keys() >= {"label_id", "attributes"}:
            label = more_itertools.first_true(
                specs_labels, pred=lambda e: e["label_id"] == annotation_query["label_id"]
            )
            if label is not None:
                self._modify_attributes_of_query(annotation_query["attributes"], label["additional_data_definitions"])
            else:
                logger.warning(f"label_id: {annotation_query['label_id']} の label_id が見つかりませんでした。")

        if task_id is not None:
            annotation_query["task_id"] = task_id
            annotation_query["exact_match_task_id"] = True

        return annotation_query

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
        self, project_id: str, annotation_query: Dict[str, Any], task_id: Optional[str] = None
    ) -> List[SingleAnnotation]:
        annotation_query = self._modify_annotation_query(project_id, annotation_query, task_id)
        logger.debug(f"annotation_query: {annotation_query}")
        annotations = self.service.wrapper.get_all_annotation_list(project_id, query_params={"query": annotation_query})
        return annotations

    def list_annotations(
        self, project_id: str, annotation_query: Dict[str, Any], group_by: GroupBy, task_id_list: List[str]
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
        annotation_query = annofabcli.common.cli.get_json_from_args(args.annotation_query)

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
        required=True,
        help="アノテーションの検索クエリをJSON形式で指定します。"
        "`file://`を先頭に付けると、JSON形式のファイルを指定できます。"
        "クエリのフォーマットは、[getAnnotationList API](https://annofab.com/docs/api/#operation/getAnnotationList)のクエリパラメータの`query`キー配下と同じです。"  # noqa: E501
        "さらに追加で、`label_name_en`, `additional_data_definition_name_en`, `choice_name_en`キーも指定できます。",  # noqa: E501
    )

    argument_parser.add_task_id(
        required=False,
        help_message=(
            "対象のタスクのtask_idを指定します。"
            "`file://`を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。"
            "指定した場合、`--annotation_query`のtask_id, exact_match_task_idが上書きされます"
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


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_count"
    subcommand_help = "task_idまたはinput_data_idで集約したアノテーションの個数を出力します。"
    description = "task_idまたはinput_data_idで集約したアノテーションの個数を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
