import argparse
import json
import logging
import sys
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import annofabapi
from annofabapi.dataclass.annotation import AdditionalData, AnnotationDetail, FullAnnotationData
from annofabapi.models import (
    AdditionalDataDefinitionType,
    AdditionalDataDefinitionV1,
    AnnotationDataHoldingType,
    LabelV1,
    ProjectMemberRole,
    TaskStatus,
)
from annofabapi.parser import (
    SimpleAnnotationParser,
    SimpleAnnotationParserByTask,
    lazy_parse_simple_annotation_dir_by_task,
    lazy_parse_simple_annotation_zip_by_task,
)
from annofabapi.utils import can_put_annotation
from dataclasses_json import dataclass_json
from more_itertools import first_true

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.visualize import AddProps, MessageLocale

logger = logging.getLogger(__name__)


@dataclass_json
@dataclass
class ImportedSimpleAnnotationDetail:
    """
    ``annofabapi.dataclass.annotation.SimpleAnnotationDetail`` に対応するインポート用のDataClass。
    """

    label: str
    """アノテーション仕様のラベル名(英語)"""

    annotation_id: Optional[str]
    """アノテーションID"""

    data: Dict[str, Any]
    """"""

    attributes: Dict[str, Union[str, bool, int]]
    """属性情報。キーは属性の名前、値は属性の値。 """


@dataclass_json
@dataclass
class ImportedSimpleAnnotation:
    """
    ``annofabapi.dataclass.annotation.SimpleAnnotation`` に対応するインポート用のDataClass。
    """

    details: List[ImportedSimpleAnnotationDetail]
    """矩形、ポリゴン、全体アノテーションなど個々のアノテーションの配列。"""


class ImportAnnotation(AbstractCommandLineInterface):
    """
    アノテーションをインポートする
    """

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)

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

    def _get_choice_id_from_name(self, name: str, choices: List[Dict[str, Any]]) -> Optional[str]:
        choice_info = first_true(choices, pred=lambda e: self.facade.get_choice_name_en(e) == name)
        if choice_info is not None:
            return choice_info["choice_id"]
        else:
            return None

    @staticmethod
    def _get_data_holding_type_from_data(data: FullAnnotationData) -> AnnotationDataHoldingType:
        if data["_type"] in ["Segmentation", "SegmentationV2"]:
            return AnnotationDataHoldingType.OUTER
        else:
            return AnnotationDataHoldingType.INNER

    @staticmethod
    def _create_annotation_id(data: FullAnnotationData, label_id: str) -> str:
        if data["_type"] == "Classification":
            return label_id
        else:
            return str(uuid.uuid4())

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
                additional_data.choice = self._get_choice_id_from_name(value, specs_additional_data["choices"])
            else:
                logger.warning(f"additional_data_type={additional_data_type}が不正です。")
                continue

            additional_data_list.append(additional_data)

        return additional_data_list

    def _to_annotation_detail_for_request(
        self, project_id: str, parser: SimpleAnnotationParser, detail: ImportedSimpleAnnotationDetail
    ) -> Optional[AnnotationDetail]:
        """
        Request Bodyに渡すDataClassに変換する。塗りつぶし画像があれば、それをS3にアップロードする。

        Args:
            project_id:
            parser:
            detail:

        Returns:

        """
        label_info = self.get_label_info_from_label_name(detail.label)
        if label_info is None:
            return None

        additional_data_list: List[AdditionalData] = self._to_additional_data_list(detail.attributes, label_info)
        data_holding_type = self._get_data_holding_type_from_data(detail.data)

        dest_obj = AnnotationDetail(
            label_id=label_info["label_id"],
            annotation_id=detail.annotation_id if detail.annotation_id is not None else str(uuid.uuid4()),
            account_id=self.service.api.login_user_id,
            data_holding_type=data_holding_type,
            data=detail.data,
            additional_data_list=additional_data_list,
            is_protected=False,
            etag=None,
            url=None,
            path=None,
            created_datetime=None,
            updated_datetime=None,
        )

        if data_holding_type == AnnotationDataHoldingType.OUTER:
            data_uri = detail.data["data_uri"]
            with parser.open_outer_file(data_uri) as f:
                s3_path = self.service.wrapper.upload_data_to_s3(project_id, f, content_type="image/png")
                dest_obj.path = s3_path
                logger.debug(f"{parser.task_id}/{parser.input_data_id}/{data_uri} をS3にアップロードしました。")

        return dest_obj

    def parser_to_request_body(
        self,
        project_id: str,
        parser: SimpleAnnotationParser,
        details: List[ImportedSimpleAnnotationDetail],
        old_annotation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        request_details: List[Dict[str, Any]] = []
        for detail in details:
            request_detail = self._to_annotation_detail_for_request(project_id, parser, detail)

            if request_detail is not None:
                # Enumをシリアライズするため、一度JSONにしてからDictに変換する
                request_details.append(json.loads(request_detail.to_json()))  # type: ignore

        updated_datetime = old_annotation["updated_datetime"] if old_annotation is not None else None

        request_body = {
            "project_id": project_id,
            "task_id": parser.task_id,
            "input_data_id": parser.input_data_id,
            "details": request_details,
            "updated_datetime": updated_datetime,
        }

        return request_body

    def put_annotation_for_input_data(
        self, project_id: str, parser: SimpleAnnotationParser, overwrite: bool = False
    ) -> bool:

        task_id = parser.task_id
        input_data_id = parser.input_data_id

        simple_annotation: ImportedSimpleAnnotation = ImportedSimpleAnnotation.from_dict(  # type: ignore
            parser.load_json()
        )
        if len(simple_annotation.details) == 0:
            logger.debug(
                f"task_id={task_id}, input_data_id={input_data_id} : インポート元にアノテーションデータがないため、アノテーションの登録をスキップします。"
            )
            return False

        input_data = self.service.wrapper.get_input_data_or_none(project_id, input_data_id)
        if input_data is None:
            logger.warning(f"task_id= '{task_id}, input_data_id = '{input_data_id}' は存在しません。")
            return False

        old_annotation, _ = self.service.api.get_editor_annotation(project_id, task_id, input_data_id)
        if len(old_annotation["details"]) > 0 and not overwrite:
            logger.debug(
                f"task_id={task_id}, input_data_id={input_data_id} : "
                f"インポート先のタスクに既にアノテーションが存在するため、アノテーションの登録をスキップします。"
            )
            return False

        logger.info(f"task_id={task_id}, input_data_id={input_data_id} : アノテーションを登録します。")
        request_body = self.parser_to_request_body(
            project_id, parser, simple_annotation.details, old_annotation=old_annotation
        )

        self.service.api.put_annotation(project_id, task_id, input_data_id, request_body=request_body)
        return True

    def put_annotation_for_task(
        self, project_id: str, task_parser: SimpleAnnotationParserByTask, overwrite: bool
    ) -> int:

        logger.info(f"タスク'{task_parser.task_id}'に対してアノテーションを登録します。")

        success_count = 0
        for parser in task_parser.lazy_parse():
            try:
                if self.put_annotation_for_input_data(project_id, parser, overwrite=overwrite):
                    success_count += 1
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(
                    f"task_id={parser.task_id}, input_data_id={parser.input_data_id} のアノテーションインポートに失敗しました。: {e}"
                )

        logger.info(f"タスク'{task_parser.task_id}'の入力データ {success_count} 個に対してアノテーションをインポートしました。")
        return success_count

    def execute_task(
        self, project_id: str, task_parser: SimpleAnnotationParserByTask, my_account_id: str, overwrite: bool = False
    ) -> bool:
        """
        1個のタスクに対してアノテーションを登録する。

        Args:
            project_id:
            task_parser:
            my_account_id: 自分自身のアカウントID
            overwrite:

        Returns:
            1個以上の入力データのアノテーションを変更したか

        """
        task_id = task_parser.task_id
        if not self.confirm_processing(f"task_id={task_id} のアノテーションをインポートしますか？"):
            return False

        logger.info(f"task_id={task_id} に対して処理します。")

        task = self.service.wrapper.get_task_or_none(project_id, task_id)
        if task is None:
            logger.warning(f"task_id = '{task_id}' は存在しません。")
            return False

        if task["status"] in [TaskStatus.WORKING.value, TaskStatus.COMPLETE.value]:
            logger.info(f"タスク'{task_id}'は作業中または受入完了状態のため、インポートをスキップします。 status={task['status']}")
            return False

        if not can_put_annotation(task, my_account_id):
            logger.debug(f"タスク'{task_id}'は、過去に誰かに割り当てられたタスクで、現在の担当者が自分自身でないため、アノテーションのインポートをスキップします。")
            return False

        result_count = self.put_annotation_for_task(project_id, task_parser, overwrite)
        return result_count > 0

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

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        my_account_id = self.facade.get_my_account_id()

        # Simpleアノテーションの読み込み
        if annotation_path.is_file():
            iter_task_parser = lazy_parse_simple_annotation_zip_by_task(annotation_path)
        else:
            iter_task_parser = lazy_parse_simple_annotation_dir_by_task(annotation_path)

        success_count = 0
        for task_parser in iter_task_parser:
            try:
                if len(task_id_list) > 0:
                    # コマンドライン引数で --task_idが指定された場合は、対象のタスクのみインポートする
                    if task_parser.task_id in task_id_list:
                        if self.execute_task(
                            project_id, task_parser, overwrite=args.overwrite, my_account_id=my_account_id
                        ):
                            success_count += 1
                else:
                    # コマンドライン引数で --task_idが指定されていない場合はすべてをインポートする
                    if self.execute_task(
                        project_id, task_parser, overwrite=args.overwrite, my_account_id=my_account_id
                    ):
                        success_count += 1

            except Exception as e:  # pylint: disable=broad-except
                logger.warning(f"task_id={task_parser.task_id} のアノテーションインポートに失敗しました。: {e}")

        logger.info(f"{success_count} 個のタスクに対してアノテーションをインポートしました。")


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ImportAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--annotation",
        type=str,
        required=True,
        help="Simpleアノテーションと同じフォルダ構成のzipファイル or ディレクトリのパスを指定してください。" "タスクの状態が作業中/完了の場合はインポートしません。",
    )

    argument_parser.add_task_id(required=False)

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="指定した場合、すでに存在するアノテーションを上書きします（入力データ単位）。" "指定しなければ、アノテーションのインポートをスキップします。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "import"
    subcommand_help = "アノテーションをインポートします。"
    description = (
        "アノテーションをインポートします。"
        "アノテーションのフォーマットは、Simpleアノテーション(v2)と同じフォルダ構成のzipファイルまたはディレクトリです。"
        "ただし、作業中/完了状態のタスク、または「過去に割り当てられていて現在の担当者が自分自身でない」タスクはリストアできません。"
    )
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
