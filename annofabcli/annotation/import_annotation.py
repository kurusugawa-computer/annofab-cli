import argparse
import json
import logging
import sys
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import annofabapi
from annofabapi.dataclass.annotation import AdditionalData, AnnotationDetail, FullAnnotationData, SimpleAnnotationDetail
from annofabapi.models import (
    AdditionalDataDefinitionType,
    AdditionalDataDefinitionV1,
    AnnotationDataHoldingType,
    LabelV1,
    ProjectMemberRole,
    Task,
)
from annofabapi.parser import (
    SimpleAnnotationParser,
    SimpleAnnotationParserGroupByTask,
    lazy_parse_simple_annotation_dir_by_task,
    lazy_parse_simple_annotation_zip_by_task,
)

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.visualize import AddProps, MessageLocale

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

        logger.warning(f"アノテーション仕様に label_name={label_name} のラベルが存在しません。")
        return None

    def _get_additional_data_from_attribute_name(
        self, attribute_name: str, label_info: LabelV1
    ) -> Optional[AdditionalDataDefinitionV1]:
        for additional_data in label_info["additional_data_definitions"]:
            additional_data_name_en = self.visualize.get_additional_data_name(
                additional_data["additional_data_definition_id"], MessageLocale.EN, label_id=label_info["label_id"]
            )
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

            additional_data = AdditionalData(
                additional_data_definition_id=specs_additional_data["additional_data_definition_id"],
                flag=None,
                integer=None,
                choice=None,
                comment=None,
            )
            additional_data_type = AdditionalDataDefinitionType(specs_additional_data["type"])
            if additional_data_type == AdditionalDataDefinitionType.FLAG:
                additional_data.flag = value
            elif additional_data_type == AdditionalDataDefinitionType.INTEGER:
                additional_data.integer = value
            elif additional_data_type in [
                AdditionalDataDefinitionType.TEXT,
                AdditionalDataDefinitionType.COMMENT,
                AdditionalDataDefinitionType.TRACKING,
                AdditionalDataDefinitionType.LINK,
            ]:
                additional_data.comment = value
            elif additional_data_type in [AdditionalDataDefinitionType.CHOICE, AdditionalDataDefinitionType.SELECT]:
                additional_data.choice = value
            else:
                logger.warning(f"additional_data_type={additional_data_type}が不正です。")
                continue

            additional_data_list.append(additional_data)

        return additional_data_list

    def _to_annotation_detail(self, obj: SimpleAnnotationDetail) -> Optional[AnnotationDetail]:
        label_info = self.get_label_info_from_label_name(obj.label)
        if label_info is None:
            return None

        additional_data_list: List[AdditionalData] = self._to_additional_data_list(obj.attributes, label_info)
        dest_obj = AnnotationDetail(
            label_id=label_info["label_id"],
            annotation_id=str(uuid.uuid4()),
            account_id=self.service.api.login_user_id,
            data_holding_type=self._get_data_holding_type_from_data(obj.data),
            data=obj.data,
            additional_data_list=additional_data_list,
            is_protected=False,
            path=None,
            etag=None,
            url=None,
        )
        # TODO 塗りつぶしファイルの登録
        return dest_obj

    def parser_to_request_body(
        self, project_id: str, parser: SimpleAnnotationParser, old_annotation: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        simple_annotation = parser.parse()
        request_details: List[Dict[str, Any]] = []
        for d in simple_annotation.details:
            request_detail = self._to_annotation_detail(d)
            if request_detail is not None:
                # Enumをシリアライズするため、一度JSONにしてからDictに変換する
                request_details.append(json.loads(request_detail.to_json())) # type: ignore

        updated_datetime = old_annotation["updated_datetime"] if old_annotation is not None else None

        request_body = {
            "project_id": project_id,
            "task_id": parser.task_id,
            "input_data_id": parser.input_data_id,
            "details": request_details,
            "updated_datetime": updated_datetime,
        }

        return request_body

    def put_annotation_for_task(
        self, project_id: str, task_parser: SimpleAnnotationParserGroupByTask, overwrite: bool = False
    ):
        for parser in task_parser.parser_list:
            task_id = parser.task_id
            input_data_id = parser.input_data_id
            input_data = self.service.wrapper.get_input_data_or_none(project_id, input_data_id)
            if input_data is None:
                logger.warning(f"input_data_id = '{input_data_id}' は存在しません。")
                continue

            old_annotation, _ = self.service.api.get_editor_annotation(project_id, task_id, input_data_id)
            if old_annotation is not None and not overwrite:
                logger.info(f"task_id={task_id}, input_data_id={input_data_id} : すでにアノテーションが存在するため、アノテーションの登録をスキップします。")
                return

            logger.info(f"task_id={task_id}, input_data_id={input_data_id} : アノテーションを登録します。")
            request_body = self.parser_to_request_body(project_id, parser, old_annotation=old_annotation)
            self.service.api.put_annotation(project_id, task_id, input_data_id, request_body=request_body)

    def execute_task(self, project_id: str, task_parser: SimpleAnnotationParserGroupByTask, overwrite: bool = False):
        task_id = task_parser.task_id
        logger.info(f"task_id={task_id} に対して処理します。")

        task = self.service.wrapper.get_task_or_none(project_id, task_id)
        if task is None:
            logger.warning(f"task_id = '{task_id}' は存在しません。")
            return False

        if not self.can_execute_put_annotation_directly(task):
            # タスクを作業中にする
            pass

        self.put_annotation_for_task(project_id, task_parser, overwrite=overwrite)

    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli annotation import: error:"
        annotation_path = Path(args.annotation)
        if not annotation_path.exists():
            print(
                f"{COMMON_MESSAGE} argument --annotation: ZIPファイルまたはディレクトリが存在しません。'{str(annotation_path)}'",
                file=sys.stderr,
            )
            return False

        elif annotation_path.is_file() and not zipfile.is_zipfile(str(annotation_path)):
            print(f"{COMMON_MESSAGE} argument --annotation: ZIPファイルまたはディレクトリを指定してください。", file=sys.stderr)
            return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            return

        project_id = args.project_id
        annotation_path = Path(args.annotation)

        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        if annotation_path.is_file():
            # Simpleアノテーションzipの読み込み
            for task_parser in lazy_parse_simple_annotation_zip_by_task(annotation_path):
                self.execute_task(project_id, task_parser, overwrite=args.overwrite)

        else:
            # Simpleアノテーションzipを展開したディレクトリの読み込み
            for task_parser in lazy_parse_simple_annotation_dir_by_task(annotation_path):
                self.execute_task(project_id, task_parser, overwrite=args.overwrite)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ImportAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument("--annotation", type=str, required=True, help="Simpleアノテーションのzipファイル or ディレクトリ")

    parser.add_argument(
        "--overwrite", action="store_true", help="指定した場合、すでに存在するアノテーションを上書きします（入力データ単位）。指定しなければ、アノテーションの登録をスキップします。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "import"
    subcommand_help = "アノテーションをインポートします。"
    description = "アノテーションをインポートします。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
