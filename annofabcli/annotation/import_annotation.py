from __future__ import annotations

import argparse
import copy
import logging
import multiprocessing
import sys
import uuid
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

import annofabapi
import ulid
from annofabapi.models import (
    AdditionalDataDefinitionType,
    DefaultAnnotationType,
    ProjectMemberRole,
    TaskStatus,
)
from annofabapi.parser import (
    SimpleAnnotationParser,
    SimpleAnnotationParserByTask,
    lazy_parse_simple_annotation_dir_by_task,
    lazy_parse_simple_annotation_zip_by_task,
)
from annofabapi.plugin import EditorPluginId, ThreeDimensionAnnotationType
from annofabapi.pydantic_models.input_data_type import InputDataType
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor, get_choice
from annofabapi.utils import can_put_annotation
from dataclasses_json import DataClassJsonMixin

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.type_util import assert_noreturn
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


@dataclass
class ImportedSimpleAnnotationDetail(DataClassJsonMixin):
    """
    ``annofabapi.dataclass.annotation.SimpleAnnotationDetail`` に対応するインポート用のDataClass。
    """

    label: str
    """アノテーション仕様のラベル名(英語)"""

    data: dict[str, Any]
    """"""

    attributes: Optional[dict[str, Union[str, bool, int]]] = None
    """属性情報。キーは属性の名前、値は属性の値。 """

    annotation_id: Optional[str] = None
    """アノテーションID"""


@dataclass
class ImportedSimpleAnnotation(DataClassJsonMixin):
    """
    ``annofabapi.dataclass.annotation.SimpleAnnotation`` に対応するインポート用のDataClass。
    """

    details: list[ImportedSimpleAnnotationDetail]
    """矩形、ポリゴン、全体アノテーションなど個々のアノテーションの配列。"""


def is_image_segmentation_label(label_info: dict[str, Any]) -> bool:
    """
    ラベルの種類が、画像プロジェクトのセグメンテーションかどうか
    """
    annotation_type = label_info["annotation_type"]
    return annotation_type in {DefaultAnnotationType.SEGMENTATION.value, DefaultAnnotationType.SEGMENTATION_V2.value}


def is_3dpc_segment_label(label_info: dict[str, Any]) -> bool:
    """
    3次元のセグメントかどうか
    """
    # 理想はプラグイン情報を見て、3次元アノテーションの種類かどうか判定した方がよい
    # が、当分は文字列判定だけでも十分なので、文字列で判定する
    return label_info["annotation_type"] in {
        ThreeDimensionAnnotationType.INSTANCE_SEGMENT.value,
        ThreeDimensionAnnotationType.SEMANTIC_SEGMENT.value,
    }


def is_3dpc_project(project: dict[str, Any]) -> bool:
    """3次元プロジェクトか否か"""
    editor_plugin_id = project["configuration"]["plugin_id"]
    return project["input_data_type"] == InputDataType.CUSTOM.value and editor_plugin_id == EditorPluginId.THREE_DIMENSION.value


def create_annotation_id(label_info: dict[str, Any], project: dict[str, Any]) -> str:
    """
    デフォルトのアノテーションIDを生成します。
    """
    if is_3dpc_project(project):
        # 3次元エディタ画面ではULIDが発行されるので、それに合わせる
        return str(ulid.new())
    elif label_info["annotation_type"] == DefaultAnnotationType.CLASSIFICATION.value:
        # 全体アノテーションの場合、annotation_idはlabel_idである必要がある
        return label_info["label_id"]
    else:
        return str(uuid.uuid4())


def get_3dpc_segment_data_uri(annotation_data: dict[str, Any]) -> str:
    """
    3DセグメントのURIを取得する

    Notes:
        3dpc editorに依存したコード。annofab側でSimple Annotationのフォーマットが改善されたら、このコードを削除する
    """
    data_uri = annotation_data["data"]
    # この時点で data_uriは f"./{input_data_id}/{annotation_id}"
    # parser.open_data_uriメソッドに渡す値は、先頭のinput_data_idは不要なので、これを取り除く
    path = Path(data_uri)
    return str(path.relative_to(path.parts[0]))


class AnnotationConverter:
    """
    Simpleアノテーションを、`put_annotation` API(v2)のリクエストボディに変換するクラスです。

    Args:
        project: プロジェクト情報
        annotation_specs: アノテーション仕様情報(v3)
        is_strict: Trueの場合、存在しない属性名や属性値の型不一致があった場合に例外を発生させる
        service: Annofab APIにアクセスするためのサービスオブジェクト。外部アノテーションをアップロードするのに利用する。
    """

    def __init__(self, project: dict[str, Any], annotation_specs: dict[str, Any], *, service: annofabapi.Resource, is_strict: bool = False) -> None:
        self.project = project
        self.project_id = project["project_id"]
        self.annotation_specs = annotation_specs
        self.annotation_specs_accessor = AnnotationSpecsAccessor(annotation_specs)
        self.is_strict = is_strict
        self.service = service

    def _convert_attribute_value(  # noqa: PLR0911, PLR0912
        self,
        attribute_value: Union[str, int, bool],  # noqa: FBT001
        additional_data_type: AdditionalDataDefinitionType,
        attribute_name: str,
        choices: list[dict[str, Any]],
        *,
        log_message_suffix: str,
    ) -> Optional[dict[str, Any]]:
        if additional_data_type == AdditionalDataDefinitionType.FLAG:
            if not isinstance(attribute_value, bool):
                message = f"属性'{attribute_name}'に対応する属性値の型は bool である必要があります。 :: attribute_value='{attribute_value}', additional_data_type='{additional_data_type}'  :: {log_message_suffix}"  # noqa: E501
                logger.warning(message)
                if self.is_strict:
                    raise ValueError(message)
                return None
            return {"_type": "Flag", "value": attribute_value}

        elif additional_data_type == AdditionalDataDefinitionType.INTEGER:
            if not isinstance(attribute_value, int):
                message = f"属性'{attribute_name}'に対応する属性値の型は int である必要があります。 :: attribute_value='{attribute_value}', additional_data_type='{additional_data_type}'  :: {log_message_suffix}"  # noqa: E501
                logger.warning(message)
                if self.is_strict:
                    raise ValueError(message)
                return None
            return {"_type": "Integer", "value": attribute_value}

        # 以降の属性は、属性値の型はstr型であるが、型をチェックしない。
        # str型に変換しても、特に期待していない動作にならないと思われるため
        elif additional_data_type == AdditionalDataDefinitionType.COMMENT:
            return {"_type": "Comment", "value": str(attribute_value)}

        elif additional_data_type == AdditionalDataDefinitionType.TEXT:
            return {"_type": "Text", "value": str(attribute_value)}

        elif additional_data_type == AdditionalDataDefinitionType.TRACKING:
            return {"_type": "Tracking", "value": str(attribute_value)}

        elif additional_data_type == AdditionalDataDefinitionType.LINK:
            if attribute_value == "":
                # `annotation_id`に空文字を設定すると、エディタ画面ではエラーになるため、Noneを返す
                return None
            return {"_type": "Link", "annotation_id": str(attribute_value)}

        elif additional_data_type == AdditionalDataDefinitionType.CHOICE:
            if attribute_value == "":
                return None
            try:
                choice = get_choice(choices, choice_name=str(attribute_value))
            except ValueError:
                logger.warning(f"アノテーション仕様の属性'{attribute_name}'に選択肢名(英語)が'{attribute_value}'である選択肢情報は存在しないか、複数存在します。 :: {log_message_suffix}")
                if self.is_strict:
                    raise
                return None

            return {"_type": "Choice", "choice_id": choice["choice_id"]}
        elif additional_data_type == AdditionalDataDefinitionType.SELECT:
            if attribute_value == "":
                return None
            try:
                choice = get_choice(choices, choice_name=str(attribute_value))
            except ValueError:
                logger.warning(f"アノテーション仕様の属性'{attribute_name}'に選択肢名(英語)が'{attribute_value}'である選択肢情報は存在しないか、複数存在します。 :: {log_message_suffix}")
                if self.is_strict:
                    raise
                return None

            return {"_type": "Select", "choice_id": choice["choice_id"]}

        else:
            assert_noreturn(additional_data_type)

    def convert_attributes(self, attributes: dict[str, Any], *, label_name: Optional[str] = None, log_message_suffix: str = "") -> list[dict[str, Any]]:
        """
        インポート対象のアノテーションJSONに格納されている`attributes`を`AdditionalDataListV2`のlistに変換します。

        Args:
            attributes: インポート対象のアノテーションJSONに格納されている`attributes`
            label_name: `attributes`に紐づくラベルの名前。指定した場合は、指定したラベルに紐づく属性を探します。
            log_message_suffix: ログメッセージのサフィックス

        Raises:
            ValueError: `self.is_strict`がTrueの場合：存在しない属性名が指定されたり、属性値の型が適切でない
        """
        additional_data_list: list[dict[str, Any]] = []

        label = self.annotation_specs_accessor.get_label(label_name=label_name) if label_name is not None else None

        for attribute_name, attribute_value in attributes.items():
            try:
                specs_additional_data = self.annotation_specs_accessor.get_attribute(attribute_name=attribute_name, label=label)
            except ValueError:
                logger.warning(f"アノテーション仕様に属性名(英語)が'{attribute_name}'である属性情報が存在しないか、複数存在します。 :: {log_message_suffix}")
                if self.is_strict:
                    raise
                continue

            additional_data = {
                "definition_id": specs_additional_data["additional_data_definition_id"],
                "value": self._convert_attribute_value(
                    attribute_value,
                    AdditionalDataDefinitionType(specs_additional_data["type"]),
                    attribute_name,
                    specs_additional_data["choices"],
                    log_message_suffix=log_message_suffix,
                ),
            }

            additional_data_list.append(additional_data)

        return additional_data_list

    def convert_annotation_detail(
        self,
        parser: SimpleAnnotationParser,
        detail: ImportedSimpleAnnotationDetail,
        *,
        log_message_suffix: str = "",
    ) -> dict[str, Any]:
        """
        アノテーションJSONに記載された1個のアノテーション情報を、`put_annotation` APIに渡す形式に変換する。
        Outerアノテーションならば、AWS S3に外部ファイルをアップロードします。


        Args:
            parser:
            detail: インポート対象の1個のアノテーション情報

        Returns:
            `put_annotation` API（v2）のリクエストボディに格納するアノテーション情報（`AnnotationDetailV2Input`）

        Raises:
            ValueError: 存在しないラベル名が指定された場合（`self.is_strict`がFalseでもraiseされる９

        """
        log_message_suffix = f"task_id='{parser.task_id}', input_data_id='{parser.input_data_id}', label_name='{detail.label}', annotation_id='{detail.annotation_id}'"

        try:
            label_info = self.annotation_specs_accessor.get_label(label_name=detail.label)
        except ValueError:
            logger.warning(f"アノテーション仕様にラベル名(英語)が'{detail.label}'であるラベル情報が存在しないか、または複数存在します。 :: {log_message_suffix}")
            raise

        if detail.attributes is not None:
            additional_data_list = self.convert_attributes(detail.attributes, label_name=detail.label, log_message_suffix=log_message_suffix)
        else:
            additional_data_list = []

        result = {
            "_type": "Create",
            "label_id": label_info["label_id"],
            "annotation_id": detail.annotation_id if detail.annotation_id is not None else create_annotation_id(label_info, self.project),
            "additional_data_list": additional_data_list,
            "editor_props": {},
        }

        if is_3dpc_segment_label(label_info):
            # TODO: 3dpc editorに依存したコード。annofab側でSimple Annotationのフォーマットが改善されたら、このコードを削除する
            with parser.open_outer_file(get_3dpc_segment_data_uri(detail.data)) as f:
                s3_path = self.service.wrapper.upload_data_to_s3(self.project_id, f, content_type="application/json")
                result["body"] = {"_type": "Outer", "path": s3_path}

        elif is_image_segmentation_label(label_info):
            with parser.open_outer_file(detail.data["data_uri"]) as f:
                s3_path = self.service.wrapper.upload_data_to_s3(self.project_id, f, content_type="image/png")
                result["body"] = {"_type": "Outer", "path": s3_path}

        else:
            result["body"] = {"_type": "Inner", "data": detail.data}
        return result

    def convert_annotation_details(
        self,
        parser: SimpleAnnotationParser,
        details: list[ImportedSimpleAnnotationDetail],
        old_details: list[dict[str, Any]],
        *,
        updated_datetime: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        アノテーションJSONに記載されたアノテーション情報を、`put_annotation` APIに渡す形式に変換します。

        Args:
            parser: アノテーションJSONをパースするためのクラス
            details: インポート対象のアノテーション情報
            old_details: 既存のアノテーション情報。既存のアノテーション情報に加えて、インポート対象のアノテーションを登録するためのリクエストボディを作成します。
            updated_datetime: 更新日時
        """
        old_dict_detail = {}
        INDEX_KEY = "_index"  # noqa: N806
        for index, old_detail in enumerate(old_details):
            old_detail.update({"_type": "Update", "body": None})

            # 一時的にインデックスを格納
            old_detail.update({INDEX_KEY: index})
            old_dict_detail[old_detail["annotation_id"]] = old_detail

        new_request_details: list[dict[str, Any]] = []
        for detail in details:
            try:
                log_message_suffix = f"task_id='{parser.task_id}', input_data_id='{parser.input_data_id}', label_name='{detail.label}', annotation_id='{detail.annotation_id}'"

                request_detail = self.convert_annotation_detail(parser, detail, log_message_suffix=log_message_suffix)
            except Exception as e:
                logger.warning(
                    f"アノテーション情報を`putAnnotation`APIのリクエストボディへ変換するのに失敗しました。 :: {e!r} :: {log_message_suffix}",
                )
                if self.is_strict:
                    raise
                continue

            if detail.annotation_id in old_dict_detail:
                # アノテーションを上書き
                old_detail = old_dict_detail[detail.annotation_id]
                request_detail["_type"] = "Update"
                old_details[old_detail[INDEX_KEY]] = request_detail
            else:
                # アノテーションの追加
                new_request_details.append(request_detail)

        new_details = old_details + new_request_details

        request_body = {
            "project_id": self.project_id,
            "task_id": parser.task_id,
            "input_data_id": parser.input_data_id,
            "details": new_details,
            "updated_datetime": updated_datetime,
            "format_version": "2.0.0",
        }

        return request_body


class ImportAnnotationMain(CommandLineWithConfirm):
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        project_id: str,
        all_yes: bool,
        is_force: bool,
        is_merge: bool,
        is_overwrite: bool,
        converter: AnnotationConverter,
    ) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)
        CommandLineWithConfirm.__init__(self, all_yes)

        self.project_id = project_id
        self.is_force = is_force
        self.is_merge = is_merge
        self.is_overwrite = is_overwrite
        self.converter = converter

    def put_annotation_for_input_data(self, parser: SimpleAnnotationParser) -> bool:
        task_id = parser.task_id
        input_data_id = parser.input_data_id

        simple_annotation: ImportedSimpleAnnotation = ImportedSimpleAnnotation.from_dict(parser.load_json())
        if len(simple_annotation.details) == 0:
            logger.debug(f"task_id='{task_id}', input_data_id='{input_data_id}' :: インポート元にアノテーションデータがないため、アノテーションの登録をスキップします。")
            return False

        input_data = self.service.wrapper.get_input_data_or_none(self.project_id, input_data_id)
        if input_data is None:
            logger.warning(f"input_data_id='{input_data_id}'という入力データは存在しません。 :: task_id='{task_id}'")
            return False

        old_annotation, _ = self.service.api.get_editor_annotation(self.project_id, task_id, input_data_id, query_params={"v": "2"})
        if len(old_annotation["details"]) > 0:  # noqa: SIM102
            if not self.is_overwrite and not self.is_merge:
                logger.debug(
                    f"task_id='{task_id}', input_data_id='{input_data_id}' :: "
                    f"インポート先のタスク内の入力データに既にアノテーションが存在するため、アノテーションの登録をスキップします。"
                    f"アノテーションをインポートする場合は、`--overwrite` または '--merge' を指定してください。"
                )
                return False

        logger.info(f"task_id='{task_id}', input_data_id='{input_data_id}' :: {len(simple_annotation.details)} 件のアノテーションを登録します。")
        if self.is_merge:
            request_body = self.converter.convert_annotation_details(parser, simple_annotation.details, old_details=old_annotation["details"], updated_datetime=old_annotation["updated_datetime"])
        else:
            request_body = self.converter.convert_annotation_details(parser, simple_annotation.details, old_details=[], updated_datetime=old_annotation["updated_datetime"])

        self.service.api.put_annotation(self.project_id, task_id, input_data_id, request_body=request_body, query_params={"v": "2"})
        return True

    def put_annotation_for_task(self, task_parser: SimpleAnnotationParserByTask) -> int:
        success_count = 0
        for parser in task_parser.lazy_parse():
            try:
                if self.put_annotation_for_input_data(parser):
                    success_count += 1
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    f"task_id='{parser.task_id}', input_data_id='{parser.input_data_id}' のアノテーションのインポートに失敗しました。",
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
        if not self.confirm_processing(f"task_id='{task_id}' のアノテーションをインポートしますか？"):
            return False

        logger_prefix = f"{task_index + 1!s} 件目: " if task_index is not None else ""
        logger.info(f"{logger_prefix}task_id='{task_id}' に対して処理します。")

        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"task_id='{task_id}'であるタスクは存在しません。")
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

        else:  # noqa: PLR5501
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
            logger.warning(f"task_id='{task_parser.task_id}' のアノテーションのインポートに失敗しました。", exc_info=True)
            return False

    def main(  # noqa: ANN201
        self,
        iter_task_parser: Iterator[SimpleAnnotationParserByTask],
        target_task_ids: Optional[set[str]] = None,
        parallelism: Optional[int] = None,
    ):
        def get_iter_task_parser_from_task_ids(_iter_task_parser: Iterator[SimpleAnnotationParserByTask], _target_task_ids: set[str]) -> Iterator[SimpleAnnotationParserByTask]:
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
                    logger.warning(f"task_id='{task_parser.task_id}' のアノテーションのインポートに失敗しました。", exc_info=True)
                    continue
                finally:
                    task_count += 1

        if target_task_ids is not None and len(tmp_target_task_ids) > 0:
            logger.warning(f"'--task_id'で指定したタスクの内 {len(tmp_target_task_ids)} 件は、インポート対象のアノテーションデータに含まれていません。 :: {tmp_target_task_ids}")

        logger.info(f"{success_count} / {task_count} 件のタスクに対してアノテーションをインポートしました。")


class ImportAnnotation(CommandLine):
    """
    アノテーションをインポートする
    """

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace) -> None:
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)

    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli annotation import: error:"  # noqa: N806
        annotation_path = Path(args.annotation)
        if not annotation_path.exists():
            print(  # noqa: T201
                f"{COMMON_MESSAGE} argument --annotation: ZIPファイルまたはディレクトリが存在しません。'{annotation_path!s}'",
                file=sys.stderr,
            )
            return False

        elif not (zipfile.is_zipfile(str(annotation_path)) or annotation_path.is_dir()):
            print(f"{COMMON_MESSAGE} argument --annotation: ZIPファイルまたはディレクトリを指定してください。", file=sys.stderr)  # noqa: T201
            return False

        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず '--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id
        annotation_path: Path = args.annotation

        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        target_task_ids = set(annofabcli.common.cli.get_list_from_args(args.task_id)) if args.task_id is not None else None

        # Simpleアノテーションの読み込み
        if annotation_path.is_dir():
            iter_task_parser = lazy_parse_simple_annotation_dir_by_task(annotation_path)
        elif zipfile.is_zipfile(str(annotation_path)):
            iter_task_parser = lazy_parse_simple_annotation_zip_by_task(annotation_path)
        else:
            logger.warning(f"annotation_path: '{annotation_path}' は、zipファイルまたはディレクトリではありませんでした。")
            return

        annotation_specs_v3, _ = self.service.api.get_annotation_specs(project_id, query_params={"v": "3"})
        project, _ = self.service.api.get_project(project_id)
        converter = AnnotationConverter(project=project, annotation_specs=annotation_specs_v3, is_strict=args.strict, service=self.service)

        main_obj = ImportAnnotationMain(
            self.service,
            project_id=project_id,
            all_yes=self.all_yes,
            is_merge=args.merge,
            is_overwrite=args.overwrite,
            is_force=args.force,
            converter=converter,
        )

        main_obj.main(iter_task_parser, target_task_ids=target_task_ids, parallelism=args.parallelism)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ImportAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--annotation",
        type=Path,
        required=True,
        help="Simpleアノテーションと同じフォルダ構成のzipファイル or ディレクトリのパスを指定してください。タスクの状態が作業中/完了の場合はインポートしません。",
    )

    argument_parser.add_task_id(required=False)

    overwrite_merge_group = parser.add_mutually_exclusive_group()

    overwrite_merge_group.add_argument(
        "--overwrite",
        action="store_true",
        help="アノテーションが存在する場合、 ``--overwrite`` を指定していれば、すでに存在するアノテーションを削除してインポートします。指定しなければ、アノテーションのインポートをスキップします。",
    )

    overwrite_merge_group.add_argument(
        "--merge",
        action="store_true",
        help="アノテーションが存在する場合、 ``--merge`` を指定していればアノテーションをannotation_id単位でマージしながらインポートします。"
        "annotation_idが一致すればアノテーションを上書き、一致しなければアノテーションを追加します。"
        "指定しなければ、アノテーションのインポートをスキップします。",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="過去に割り当てられていて現在の担当者が自分自身でない場合、タスクの担当者を自分自身に変更してからアノテーションをインポートします。",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="アノテーションJSONに、存在しないラベル名や属性名など適切でない記載が場合、そのアノテーションJSONの登録をスキップします。"
        "デフォルトでは、適切でない箇所のみスキップして、できるだけアノテーションを登録するようにします。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="並列度。指定しない場合は、逐次的に処理します。指定した場合は、``--yes`` も指定してください。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "import"
    subcommand_help = "アノテーションをインポートします。"
    description = "アノテーションをインポートします。アノテーションのフォーマットは、Simpleアノテーションと同じフォルダ構成のzipファイルまたはディレクトリです。ただし、作業中/完了状態のタスクはインポートできません。"  # noqa: E501
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
