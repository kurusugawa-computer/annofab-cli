
import sys
import argparse
import logging
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

import zipfile
from pathlib import Path
from annofabapi.parser import lazy_parse_simple_annotation_dir_by_task, lazy_parse_simple_annotation_zip_by_task, SimpleAnnotationParserGroupByTask, SimpleAnnotationParser
from annofabapi.dataclass.annotation import SimpleAnnotationDetail, AnnotationDetail, FullAnnotationData, AdditionalData


import annofabapi
import more_itertools
import pandas
from annofabapi.models import AdditionalDataDefinitionV1, SingleAnnotation, Task, LabelV1, AnnotationDataHoldingType,AdditionalDataDefinitionV1, AdditionalDataDefinitionType

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.visualize import AddProps, MessageLocale

import json

logger = logging.getLogger(__name__)


class ImportAnnotation(AbstractCommandLineInterface):
    """
    タスクの一覧を表示する
    """

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)


    @staticmethod
    def can_execute_put_annotation_directly(task: Task) -> bool:
        """
        `put_annotation` APIを、タスクの状態を変更せずに直接実行できるかどうか。
        過去に担当者が割り当たっている場合は、直接実行できない。

        Args:
            project_id:
            task_id:

        Returns:
            Trueならば、タスクの状態を変更せずに`put_annotation` APIを実行できる。
        """
        return len(task["histories_by_phase"]) != 0

    def get_label_info_from_label_name(self, label_name: str) -> Optional[LabelV1]:
        for label in self.visualize.specs_labels:
            label_name_en = self.visualize.get_label_name(label["label_id"], MessageLocale.EN)
            if label_name_en is not None and label_name_en == label_name:
                return label

        return None

    def _get_additional_data_from_attribute_name(self, attribute_name: str,  label_info: LabelV1) -> Optional[AdditionalDataDefinitionV1]:
        for additional_data in label_info["additional_data_definitions"]:
            additional_data_name_en = self.visualize.get_additional_data_name(additional_data["additional_data_definition_id"], MessageLocale.EN, label_id=label_info["label_id"])
            if additional_data_name_en is not None and additional_data_name_en == attribute_name:
                return additional_data

        return None


    @staticmethod
    def _get_data_holding_type_from_data(data: FullAnnotationData) -> AnnotationDataHoldingType:
        if data["_type"] in ["Segmentation", "SegmentationV2"]:
            return AnnotationDataHoldingType.OUTER
        else:
            return AnnotationDataHoldingType.INNER

    def _to_additional_data_list(self, attributes: Dict[str, Any], label_info: LabelV1) -> List[AdditionalData]:
        additional_data_list: List[AdditionalData] = []
        for key, value in attributes.items():
            specs_additional_data = self._get_additional_data_from_attribute_name(key, label_info)
            if specs_additional_data is None:
                logger.warning(f"attribute_name={key} が存在しません。")
                continue

            additional_data = AdditionalData(additional_data_definition_id=specs_additional_data["additional_data_definition_id"])
            additional_data_type = AdditionalDataDefinitionType(specs_additional_data["type"])
            if additional_data_type == AdditionalDataDefinitionType.FLAG:
                additional_data.flag = value
            elif additional_data_type == AdditionalDataDefinitionType.INTEGER:
                additional_data.integer = value
            elif additional_data_type in [AdditionalDataDefinitionType.TEXT, AdditionalDataDefinitionType.COMMENT, AdditionalDataDefinitionType.TRACKING, AdditionalDataDefinitionType.LINK]:
                additional_data.comment = value
            elif additional_data_type in [AdditionalDataDefinitionType.CHOICE, AdditionalDataDefinitionType.SELECT]:
                additional_data.choice = value
            else:
                logger.warning(f"additional_data_type={additional_data_type}が不正です。")
                continue

            additional_data_list.append(additional_data)

        return additional_data_list

    def _to_annotation_detail(self, obj: SimpleAnnotationDetail) -> Optional[AnnotationDetail]:
        """
        annotation_idは新しい値にする。

        Args:
            obj:

        Returns:

        """
        label_info = self.get_label_info_from_label_name(obj.label)
        additional_data_list: List[AdditionalData] = self._to_additional_data_list(obj.attributes, label_info)
        dest_obj = AnnotationDetail(
            label_id=label_info["label_id"],
            annotation_id=str(uuid.uuid4()),
            data_holding_type=self._get_data_holding_type_from_data(obj["data"]),
            data=obj["data"],
            additional_data_list=additional_data_list
        )
        # TODO 塗りつぶしファイルの登録
        return dest_obj


    def parser_to_request_body(self, parser: SimpleAnnotationParser) -> Dict[str, Any]:


    def put_annotation_for_input_data(self, project_id: str, parser: SimpleAnnotationParser):



    def put_annotation_for_task(self, project_id: str, task_parser: SimpleAnnotationParserGroupByTask):
        for parser in task_parser.parser_list:


    def execute_task(self, project_id: str, task_parser: SimpleAnnotationParserGroupByTask):
        task_id = task_parser.task_id

        task = self.service.wrapper.get_task_or_none(project_id, task_id)
        if task is None:
            logger.warning(f"task_id = '{task_id}' は存在しません。")
            return False

        if not self.can_execute_put_annotation_directly(task):
            # タスクを作業中にする
            pass

    def main(self):
        args = self.args
        if not self.validate(args):
            return

        project_id = args.project_id
        import_path = Path(getattr(args, "import"))

        if import_path.is_file() and zipfile.is_zipfile(str(import_path)):
            # Simpleアノテーションzipの読み込み
            for parser in lazy_parse_simple_annotation_zip_by_task(import_path):
                simple_annotation = parser.parse()
                print(simple_annotation)

        elif import_path.is_dir():
            # Simpleアノテーションzipを展開したディレクトリの読み込み
            iter_parser = lazy_parse_simple_annotation_dir(import_path)
            for parser in iter_parser:
                simple_annotation = parser.parse()
                print(simple_annotation)

        else:
            print(
                "インポート対象のパスが正しくありません",
                file=sys.stderr,
            )

def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ImportAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--import",
        type=str,
        required=True,
        help="Simpleアノテーションのzipファイル or ディレクトリ"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "import"
    subcommand_help = "アノテーションをインポートします。"
    description = "アノテーションをインポートします。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
