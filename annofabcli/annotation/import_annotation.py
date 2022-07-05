from __future__ import annotations

import argparse
import copy
import logging
import multiprocessing
import sys
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

import annofabapi
from annofabapi.dataclass.annotation import AdditionalData, AnnotationDetail
from annofabapi.models import (
    AdditionalDataDefinitionType,
    AdditionalDataDefinitionV1,
    AnnotationDataHoldingType,
    DefaultAnnotationType,
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
from annofabapi.utils import can_put_annotation, str_now
from dataclasses_json import DataClassJsonMixin
from more_itertools import first_true

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    AbstractCommandLineWithConfirmInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.visualize import AddProps, MessageLocale

logger = logging.getLogger(__name__)


@dataclass
class ImportedSimpleAnnotationDetail(DataClassJsonMixin):
    """
    ``annofabapi.dataclass.annotation.SimpleAnnotationDetail`` に対応するインポート用のDataClass。
    """

    label: str
    """アノテーション仕様のラベル名(英語)"""

    data: Dict[str, Any]
    """"""

    attributes: Optional[Dict[str, Union[str, bool, int]]] = None
    """属性情報。キーは属性の名前、値は属性の値。 """

    annotation_id: Optional[str] = None
    """アノテーションID"""


@dataclass
class ImportedSimpleAnnotation(DataClassJsonMixin):
    """
    ``annofabapi.dataclass.annotation.SimpleAnnotation`` に対応するインポート用のDataClass。
    """

    details: List[ImportedSimpleAnnotationDetail]
    """矩形、ポリゴン、全体アノテーションなど個々のアノテーションの配列。"""


class ImportAnnotationMain(AbstractCommandLineWithConfirmInterface):
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        project_id: str,
        all_yes: bool,
        is_force: bool,
        is_merge: bool,
        is_overwrite: bool,
    ):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        AbstractCommandLineWithConfirmInterface.__init__(self, all_yes)

        self.project_id = project_id
        self.is_force = is_force
        self.is_merge = is_merge
        self.is_overwrite = is_overwrite
        self.visualize = AddProps(service, project_id)

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

    @classmethod
    def _get_3dpc_segment_data_uri(cls, annotation_data: Dict[str, Any]) -> str:
        """
        3DセグメントのURIを取得する

        Notes:
            3dpc editorに依存したコード。annofab側でSimple Annotationのフォーマットが改善されたら、このコードを削除する
        """
        data_uri = annotation_data["data"]
        # この時点で data_uriは f"./{input_data_id}/{annotation_id}"
        # paraser.open_data_uriメソッドに渡す値は、先頭のinput_data_idは不要なので、これを取り除く
        path = Path(data_uri)
        return str(path.relative_to(path.parts[0]))

    @classmethod
    def _is_3dpc_segment_label(cls, label_info: Dict[str, Any]) -> bool:
        if label_info["annotation_type"] != DefaultAnnotationType.CUSTOM.value:
            return False

        metadata = label_info["metadata"]
        if metadata.get("type") == "SEGMENT":
            return True
        return False

    @classmethod
    def _get_data_holding_type_from_data(cls, label_info: Dict[str, Any]) -> AnnotationDataHoldingType:

        annotation_type = label_info["annotation_type"]
        if annotation_type in [DefaultAnnotationType.SEGMENTATION.value, DefaultAnnotationType.SEGMENTATION_V2.value]:
            return AnnotationDataHoldingType.OUTER

        # TODO: 3dpc editorに依存したコード。annofab側でSimple Annotationのフォーマットが改善されたら、このコードを削除する
        if annotation_type == DefaultAnnotationType.CUSTOM.value:
            if cls._is_3dpc_segment_label(label_info):
                return AnnotationDataHoldingType.OUTER
        return AnnotationDataHoldingType.INNER

    def _to_additional_data_list(self, attributes: Dict[str, Any], label_info: LabelV1) -> List[AdditionalData]:
        additional_data_list: List[AdditionalData] = []
        for key, value in attributes.items():
            specs_additional_data = self._get_additional_data_from_attribute_name(key, label_info)
            if specs_additional_data is None:
                logger.warning(f"アノテーション仕様に attribute_name={key} が存在しません。")
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
        self, parser: SimpleAnnotationParser, detail: ImportedSimpleAnnotationDetail, now_datetime: str
    ) -> Optional[AnnotationDetail]:
        """
        Request Bodyに渡すDataClassに変換する。塗りつぶし画像があれば、それをS3にアップロードする。

        Args:
            parser:
            detail:

        Returns:
            変換できない場合はNoneを返す

        """
        label_info = self.get_label_info_from_label_name(detail.label)
        if label_info is None:
            return None

        def _get_annotation_id(arg_label_info: LabelV1) -> str:
            if detail.annotation_id is not None:
                return detail.annotation_id
            else:
                if arg_label_info["annotation_type"] == DefaultAnnotationType.CLASSIFICATION.value:
                    # 全体アノテーションの場合、annotation_idはlabel_idである必要がある
                    return arg_label_info["label_id"]
                else:
                    return str(uuid.uuid4())

        if detail.attributes is not None:
            additional_data_list = self._to_additional_data_list(detail.attributes, label_info)
        else:
            additional_data_list = []

        data_holding_type = self._get_data_holding_type_from_data(label_info)

        dest_obj = AnnotationDetail(
            label_id=label_info["label_id"],
            annotation_id=_get_annotation_id(label_info),
            account_id=self.service.api.account_id,
            data_holding_type=data_holding_type,
            data=detail.data,
            additional_data_list=additional_data_list,
            is_protected=False,
            etag=None,
            url=None,
            path=None,
            created_datetime=now_datetime,
            updated_datetime=now_datetime,
        )

        if data_holding_type == AnnotationDataHoldingType.OUTER:
            # TODO: 3dpc editorに依存したコード。annofab側でSimple Annotationのフォーマットが改善されたら、このコードを削除する
            data_uri = (
                detail.data["data_uri"]
                if not self._is_3dpc_segment_label(label_info)
                else self._get_3dpc_segment_data_uri(detail.data)
            )
            with parser.open_outer_file(data_uri) as f:
                s3_path = self.service.wrapper.upload_data_to_s3(self.project_id, f, content_type="image/png")
                dest_obj.path = s3_path

        return dest_obj

    def parser_to_request_body(
        self,
        parser: SimpleAnnotationParser,
        details: List[ImportedSimpleAnnotationDetail],
        old_annotation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        request_details: List[Dict[str, Any]] = []
        now_datetime = str_now()
        for detail in details:
            request_detail = self._to_annotation_detail_for_request(parser, detail, now_datetime=now_datetime)

            if request_detail is not None:
                request_details.append(request_detail.to_dict(encode_json=True))

        updated_datetime = old_annotation["updated_datetime"] if old_annotation is not None else None

        request_body = {
            "project_id": self.project_id,
            "task_id": parser.task_id,
            "input_data_id": parser.input_data_id,
            "details": request_details,
            "updated_datetime": updated_datetime,
        }

        return request_body

    def parser_to_request_body_with_merge(
        self,
        parser: SimpleAnnotationParser,
        details: List[ImportedSimpleAnnotationDetail],
        old_annotation: Dict[str, Any],
    ) -> Dict[str, Any]:

        old_details = old_annotation["details"]
        old_dict_detail = {}
        INDEX_KEY = "_index"
        for index, old_detail in enumerate(old_details):
            # 一時的にインデックスを格納
            old_detail.update({INDEX_KEY: index})
            old_dict_detail[old_detail["annotation_id"]] = old_detail

        new_request_details: List[Dict[str, Any]] = []
        now_datetime = str_now()
        for detail in details:
            request_detail = self._to_annotation_detail_for_request(parser, detail, now_datetime=now_datetime)

            if request_detail is None:
                continue

            if detail.annotation_id in old_dict_detail:
                # アノテーションを上書き
                old_detail = old_dict_detail[detail.annotation_id]
                old_details[old_detail[INDEX_KEY]] = request_detail.to_dict(encode_json=True)
            else:
                # アノテーションの追加
                new_request_details.append(request_detail.to_dict(encode_json=True))

        request_body = {
            "project_id": self.project_id,
            "task_id": parser.task_id,
            "input_data_id": parser.input_data_id,
            "details": old_details + new_request_details,
            "updated_datetime": old_annotation["updated_datetime"],
        }

        return request_body

    def put_annotation_for_input_data(self, parser: SimpleAnnotationParser) -> bool:

        task_id = parser.task_id
        input_data_id = parser.input_data_id

        simple_annotation: ImportedSimpleAnnotation = ImportedSimpleAnnotation.from_dict(parser.load_json())
        if len(simple_annotation.details) == 0:
            logger.debug(
                f"task_id={task_id}, input_data_id={input_data_id} : インポート元にアノテーションデータがないため、アノテーションの登録をスキップします。"
            )
            return False

        input_data = self.service.wrapper.get_input_data_or_none(self.project_id, input_data_id)
        if input_data is None:
            logger.warning(f"task_id= '{task_id}, input_data_id = '{input_data_id}' は存在しません。")
            return False

        old_annotation, _ = self.service.api.get_editor_annotation(self.project_id, task_id, input_data_id)
        if len(old_annotation["details"]) > 0:
            if not self.is_overwrite and not self.is_merge:
                logger.debug(
                    f"task_id={task_id}, input_data_id={input_data_id} : "
                    f"インポート先のタスクに既にアノテーションが存在するため、アノテーションの登録をスキップします。"
                    f"アノテーションをインポートする場合は、`--overwrite` または '--merge' を指定してください。"
                )
                return False

        logger.info(f"task_id={task_id}, input_data_id={input_data_id} : アノテーションを登録します。")
        if self.is_merge:
            request_body = self.parser_to_request_body_with_merge(
                parser, simple_annotation.details, old_annotation=old_annotation
            )
        else:
            request_body = self.parser_to_request_body(parser, simple_annotation.details, old_annotation=old_annotation)

        self.service.api.put_annotation(self.project_id, task_id, input_data_id, request_body=request_body)
        return True

    def put_annotation_for_task(self, task_parser: SimpleAnnotationParserByTask) -> int:

        logger.info(f"タスク'{task_parser.task_id}'に対してアノテーションを登録します。")

        success_count = 0
        for parser in task_parser.lazy_parse():
            try:
                if self.put_annotation_for_input_data(parser):
                    success_count += 1
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    f"task_id={parser.task_id}, input_data_id={parser.input_data_id} の" f"アノテーションのインポートに失敗しました。",
                    exc_info=True,
                )

        return success_count

    def execute_task(self, task_parser: SimpleAnnotationParserByTask, task_index: Optional[int] = None) -> bool:
        """
        1個のタスクに対してアノテーションを登録する。

        Args:
            task_parser:

        Returns:
            1個以上の入力データのアノテーションを変更したか

        """
        task_id = task_parser.task_id
        if not self.confirm_processing(f"task_id={task_id} のアノテーションをインポートしますか？"):
            return False

        logger_prefix = f"{str(task_index+1)} 件目: " if task_index is not None else ""
        logger.info(f"{logger_prefix}task_id={task_id} に対して処理します。")

        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"task_id = '{task_id}' は存在しません。")
            return False

        if task["status"] in [TaskStatus.WORKING.value, TaskStatus.COMPLETE.value]:
            logger.info(f"タスク'{task_id}'は作業中または受入完了状態のため、インポートをスキップします。 status={task['status']}")
            return False

        old_account_id: Optional[str] = None
        changed_operator = False
        if self.is_force:
            if not can_put_annotation(task, self.service.api.account_id):
                logger.debug(f"タスク'{task_id}' の担当者を自分自身に変更します。")
                old_account_id = task["account_id"]
                task = self.service.wrapper.change_task_operator(
                    self.project_id,
                    task_id,
                    operator_account_id=self.service.api.account_id,
                    last_updated_datetime=task["updated_datetime"],
                )
                changed_operator = True

        else:
            if not can_put_annotation(task, self.service.api.account_id):
                logger.debug(
                    f"タスク'{task_id}'は、過去に誰かに割り当てられたタスクで、現在の担当者が自分自身でないため、アノテーションのインポートをスキップします。"
                    f"担当者を自分自身に変更してアノテーションを登録する場合は `--force` を指定してください。"
                )
                return False

        result_count = self.put_annotation_for_task(task_parser)
        logger.info(f"{logger_prefix}タスク'{task_parser.task_id}'の入力データ {result_count} 個に対してアノテーションをインポートしました。")

        if changed_operator:
            logger.debug(f"タスク'{task_id}' の担当者を元に戻します。")
            self.service.wrapper.change_task_operator(
                self.project_id,
                task_id,
                operator_account_id=old_account_id,
                last_updated_datetime=task["updated_datetime"],
            )

        return result_count > 0

    def execute_task_wrapper(
        self,
        tpl: tuple[int, SimpleAnnotationParserByTask],
    ) -> bool:
        task_index, task_parser = tpl
        try:
            return self.execute_task(task_parser, task_index=task_index)
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"task_id={task_parser.task_id} のアノテーションのインポートに失敗しました。", exc_info=True)
            return False

    def main(
        self,
        iter_task_parser: Iterator[SimpleAnnotationParserByTask],
        target_task_ids: Optional[set[str]] = None,
        parallelism: Optional[int] = None,
    ):
        def get_iter_task_parser_from_task_ids(
            _iter_task_parser: Iterator[SimpleAnnotationParserByTask], _target_task_ids: set[str]
        ) -> Iterator[SimpleAnnotationParserByTask]:
            for task_parser in _iter_task_parser:
                if task_parser.task_id in _target_task_ids:
                    _target_task_ids.remove(task_parser.task_id)
                    yield task_parser

        if target_task_ids is not None:
            # コマンドライン引数で --task_idが指定された場合は、対象のタスクのみインポートする
            # tmp_target_task_idsが関数内で変更されるので、事前にコピーする
            tmp_target_task_ids = copy.deepcopy(target_task_ids)
            iter_task_parser = get_iter_task_parser_from_task_ids(iter_task_parser, tmp_target_task_ids)

        success_count = 0
        task_count = 0
        if parallelism is not None:
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(self.execute_task_wrapper, enumerate(iter_task_parser))
                success_count = len([e for e in result_bool_list if e])
                task_count = len(result_bool_list)

        else:
            for task_index, task_parser in enumerate(iter_task_parser):
                try:
                    result = self.execute_task(task_parser, task_index=task_index)
                    if result:
                        success_count += 1
                except Exception:
                    logger.warning(f"task_id={task_parser.task_id} のアノテーションのインポートに失敗しました。", exc_info=True)
                    continue
                finally:
                    task_count += 1

        if target_task_ids is not None and len(tmp_target_task_ids) > 0:
            logger.warning(
                f"'--task_id'で指定したタスクの内 {len(tmp_target_task_ids)} 件は、インポート対象のアノテーションデータに含まれていません。 :: {tmp_target_task_ids}"  # noqa: E501
            )

        logger.info(f"{success_count} / {task_count} 件のタスクに対してアノテーションをインポートしました。")


class ImportAnnotation(AbstractCommandLineInterface):
    """
    アノテーションをインポートする
    """

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)

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

        elif not (zipfile.is_zipfile(str(annotation_path)) or annotation_path.is_dir()):
            print(f"{COMMON_MESSAGE} argument --annotation: ZIPファイルまたはディレクトリを指定してください。", file=sys.stderr)
            return False

        if args.parallelism is not None and not args.yes:
            print(
                f"{COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず '--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id
        annotation_path: Path = args.annotation

        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        target_task_ids = (
            set(annofabcli.common.cli.get_list_from_args(args.task_id)) if args.task_id is not None else None
        )

        # Simpleアノテーションの読み込み
        if annotation_path.is_dir():
            iter_task_parser = lazy_parse_simple_annotation_dir_by_task(annotation_path)
        elif zipfile.is_zipfile(str(annotation_path)):
            iter_task_parser = lazy_parse_simple_annotation_zip_by_task(annotation_path)
        else:
            logger.warning(f"annotation_path: '{annotation_path}' は、zipファイルまたはディレクトリではありませんでした。")
            return

        main_obj = ImportAnnotationMain(
            self.service,
            project_id=project_id,
            all_yes=self.all_yes,
            is_merge=args.merge,
            is_overwrite=args.overwrite,
            is_force=args.force,
        )

        main_obj.main(iter_task_parser, target_task_ids=target_task_ids, parallelism=args.parallelism)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ImportAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--annotation",
        type=Path,
        required=True,
        help="Simpleアノテーションと同じフォルダ構成のzipファイル or ディレクトリのパスを指定してください。" "タスクの状態が作業中/完了の場合はインポートしません。",
    )

    argument_parser.add_task_id(required=False)

    overwrite_merge_group = parser.add_mutually_exclusive_group()

    overwrite_merge_group.add_argument(
        "--overwrite",
        action="store_true",
        help="アノテーションが存在する場合、 ``--overwrite`` を指定していれば、すでに存在するアノテーションを削除してインポートします。" "指定しなければ、アノテーションのインポートをスキップします。",
    )

    overwrite_merge_group.add_argument(
        "--merge",
        action="store_true",
        help="アノテーションが存在する場合、 ``--merge`` を指定していればアノテーションをannotation_id単位でマージしながらインポートします。"
        "annotation_idが一致すればアノテーションを上書き、一致しなければアノテーションを追加します。"
        "指定しなければ、アノテーションのインポートをスキップします。",
    )

    parser.add_argument(
        "--force", action="store_true", help="過去に割り当てられていて現在の担当者が自分自身でない場合、タスクの担当者を自分自身に変更してからアノテーションをインポートします。"
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        help="並列度。指定しない場合は、逐次的に処理します。指定した場合は、``--yes`` も指定してください。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "import"
    subcommand_help = "アノテーションをインポートします。"
    description = (
        "アノテーションをインポートします。アノテーションのフォーマットは、Simpleアノテーションと同じフォルダ構成のzipファイルまたはディレクトリです。ただし、作業中/完了状態のタスクはインポートできません。"
    )
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
