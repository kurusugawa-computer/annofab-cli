"""
アノテーション一覧を出力する
"""
import argparse
import logging
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union  # pylint: disable=unused-import

import annofabapi
import more_itertools
from annofabapi.models import AdditionalDataDefinition, Task

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


class GroupBy(Enum):
    TASK_ID = 'tasi_id'
    INPUT_DATA_ID = 'input_data_id'


class ListAnnotationCount(AbstractCommandLineInterface):
    """
    タスクの一覧を表示する
    """
    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)

    @staticmethod
    def _modify_attribute_of_query(attribute_query: Dict[str, Any],
                                   additional_data_definition: AdditionalDataDefinition) -> Dict[str, Any]:
        if 'choice_name_en' in attribute_query:
            choice_info = more_itertools.first_true(
                additional_data_definition['choices'],
                pred=lambda e: AnnofabApiFacade.get_choice_name_en(e) == attribute_query['choice_name_en'])

            if choice_info is not None:
                attribute_query['choice'] = choice_info['choice_id']
            else:
                logger.warning(f"choice_name_en = {attribute_query['choice_name_en']} の選択肢は存在しませんでした。")

        return attribute_query

    def _modify_attributes_of_query(self, attributes_of_query: List[Dict[str, Any]],
                                    additional_data_definitions: List[AdditionalDataDefinition]
                                   ) -> List[Dict[str, Any]]:
        for attribute_query in attributes_of_query:
            if 'additional_data_definition_name_en' in attribute_query:
                additional_data_definition = more_itertools.first_true(
                    additional_data_definitions, pred=lambda e: AnnofabApiFacade.get_additional_data_definition_name_en(
                        e) == attribute_query['additional_data_definition_name_en'])
                if additional_data_definition is None:
                    logger.warning(
                        f"additional_data_definition_name_name_en = {attribute_query['additional_data_definition_name_en']} の属性は存在しませんでした。"
                    )
                    continue

                if additional_data_definition is not None:
                    attribute_query['additional_data_definition_id'] = additional_data_definition[
                        'additional_data_definition_id']

            additional_data_definition = more_itertools.first_true(
                additional_data_definitions, pred=lambda e: e['additional_data_definition_id'] == attribute_query[
                    'additional_data_definition_id'])
            if additional_data_definition is None:
                logger.warning(
                    f"additional_data_definition_id = {attribute_query['additional_data_definition_id']} の属性は存在しませんでした。"
                )
                continue

            self._modify_attribute_of_query(attribute_query, additional_data_definition)

        return attributes_of_query

    def _modify_annotation_query(self, project_id: str, annotation_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        タスク検索クエリを修正する。
        * ``label_name_en`` から ``label_id`` に変換する。
        * ``additional_data_definition_name_en`` から ``additional_data_definition_id`` に変換する。
        * ``choice_name_en`` から ``choice`` に変換する。

        Args:
            task_query: タスク検索クエリ（変更される）

        Returns:
            修正したタスク検索クエリ

        """

        annotation_specs, _ = self.service.api.get_annotation_specs(project_id)
        specs_labels = annotation_specs['labels']

        # label_name_en から label_idを設定
        if 'label_name_en' in annotation_query:
            label_name_en = annotation_query['label_name_en']
            label = more_itertools.first_true(specs_labels,
                                              pred=lambda e: AnnofabApiFacade.get_label_name_en(e) == label_name_en)
            if label is not None:
                annotation_query['label_id'] = label['label_id']
            else:
                logger.warning(f"label_name_en: {label_name_en} の label_id が見つかりませんでした。")

        if annotation_query.keys() >= {'label_id', 'attributes'}:
            attributes = annotation_query['attributes']
            label = more_itertools.first_true(specs_labels,
                                              pred=lambda e: e['label_id'] == annotation_query['label_id'])
            if label is not None:
                self._modify_attributes_of_query(annotation_query['attributes'], label['additional_data_definitions'])
            else:
                logger.warning(f"label_id: {annotation_query['label_id']} の label_id が見つかりませんでした。")

        return annotation_query

    def get_annotations(self, project_id: str, annotation_query: Dict[str, Any]) -> List[Task]:
        task_query = self._modify_annotation_query(project_id, annotation_query)
        logger.debug(f"annotation_query: {annotation_query}")
        annotations = self.service.wrapper.get_all_annotation_list(project_id, query_params={'query': annotation_query})
        return annotations

    def list_annotations(self, project_id: str, annotation_query: Dict[str, Any]):
        """
        アノテーション一覧を出力する
        """

        annotations = self.get_annotations(project_id, annotation_query)

        logger.debug(f"アノテーション一覧の件数: {len(annotations)}")
        if len(annotations) == 10000:
            logger.warning("アノテーション一覧は10,000件で打ち切られている可能性があります。")

        # annofabcli.utils.print_according_to_format(target=tasks, arg_format=FormatArgument(arg_format), output=output,
        #                                            csv_format=csv_format)

    def main(self):
        args = self.args
        annotation_query = annofabcli.common.cli.get_json_from_args(args.annotation_query)

        self.list_annotations(args.project_id, annotation_query=annotation_query)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    ListAnnotationCount(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        '--annotation_query', type=str, required=True, help='アノテーションの検索クエリをJSON形式で指定します。'
        '`file://`を先頭に付けると、JSON形式のファイルを指定できます。'
        'クエリのフォーマットは、[getAnnotationList API](https://annofab.com/docs/api/#operation/getAnnotationList)のクエリパラメータの`query`キー配下と同じです。'
        'さらに追加で、`label_name_en`(label_idに対応), `additional_data_definition_name_en`(additional_data_definition_id)に対応する キーも指定できます。'
    )

    parser.add_argument('--group_by', type=str, choices=[GroupBy.TASK_ID.value, GroupBy.INPUT_DATA_ID.value],
                        default=GroupBy.TASK_ID.value, help='アノテーションの個数をどの単位で集約するかを指定してます。')

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON, FormatArgument.TASK_ID_LIST],
        default=FormatArgument.CSV)
    argument_parser.add_output()
    argument_parser.add_csv_format()

    argument_parser.add_query()
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_count"
    subcommand_help = "task_idまたはinput_data_idで集約したアノテーションの個数を出力します。"
    description = ("task_idまたはinput_data_idで集約したアノテーションの個数を出力します。AnnoFabの制約上、10,000件までしか出力されません。")

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
