import argparse
import copy
import logging
from typing import Any, Dict, List, Optional

import annofabapi
import more_itertools
import pandas
from annofabapi.models import AdditionalDataDefinitionV1, SingleAnnotation

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import convert_annotation_specs_labels_v2_to_v1
from annofabcli.common.utils import get_columns_with_priority
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


class ListAnnotationMain:
    def __init__(self, service: annofabapi.Resource, project_id: str):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.visualize = AddProps(self.service, project_id)

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

    def modify_annotation_query(self, project_id: str, annotation_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        アノテーション検索クエリに以下のように修正する。
        * ``label_name_en`` から ``label_id`` に変換する。
        * ``additional_data_definition_name_en`` から ``additional_data_definition_id`` に変換する。
        * ``choice_name_en`` から ``choice`` に変換する。

        Args:
            project_id:
            annotation_query:

        Returns:
            修正したタスク検索クエリ

        """
        # [REMOVE_V2_PARAM]
        annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params={"v": "2"})
        specs_labels = convert_annotation_specs_labels_v2_to_v1(
            labels_v2=annotation_specs["labels"], additionals_v2=annotation_specs["additionals"]
        )

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

        return annotation_query

    def get_annotation_list(
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
        return [self.visualize.add_properties_to_single_annotation(annotation) for annotation in annotation_list]

    def get_all_annotation_list(
        self, project_id: str, annotation_query: Optional[Dict[str, Any]], task_id_list: Optional[str] = None
    ) -> List[SingleAnnotation]:
        all_annotation_list = []
        UPPER_BOUND = 10_000
        if task_id_list is not None:
            for task_id in task_id_list:
                annotation_list = self.get_annotation_list(project_id, annotation_query, task_id=task_id)
                logger.debug(f"タスク {task_id} のアノテーション一覧の件数: {len(annotation_list)}")
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
            cli_annotation_query = annofabcli.common.cli.get_json_from_args(args.annotation_query)
            annotation_query = main_obj.modify_annotation_query(project_id, cli_annotation_query)
        else:
            annotation_query = None

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None

        super().validate_project(project_id, project_member_roles=None)

        annotation_list = main_obj.get_all_annotation_list(
            project_id, annotation_query=annotation_query, task_id_list=task_id_list
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

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON],
        default=FormatArgument.CSV,
    )
    argument_parser.add_csv_format()

    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list"
    subcommand_help = "アノテーションの一覧を出力します。"
    description = "アノテーションの一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
