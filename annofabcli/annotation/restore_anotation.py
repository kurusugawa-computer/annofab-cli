import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from annofabapi.dataclass.annotation import Annotation, AnnotationDetail
from annofabapi.models import AnnotationDataHoldingType, ProjectMemberRole, TaskStatus
from annofabapi.parser import (
    SimpleAnnotationParser,
    SimpleAnnotationParserByTask,
    lazy_parse_simple_annotation_dir_by_task,
)
from annofabapi.utils import can_put_annotation

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class RestoreAnnotation(AbstractCommandLineInterface):
    """
    アノテーションをリストアする。
    """

    def _to_annotation_detail_for_request(
        self, project_id: str, parser: SimpleAnnotationParser, detail: AnnotationDetail
    ) -> AnnotationDetail:
        """
        Request Bodyに渡すDataClassに変換する。塗りつぶし画像があれば、それをS3にアップロードする。

        Args:
            project_id:
            parser:
            detail: (IN/OUT) １個のアノテーション情報

        Returns:

        """
        if detail.data_holding_type == AnnotationDataHoldingType.OUTER:
            detail.etag = None
            detail.url = None
            data_uri = detail.path

            if data_uri is not None:
                with parser.open_outer_file(data_uri) as f:
                    s3_path = self.service.wrapper.upload_data_to_s3(project_id, f, content_type="image/png")
                    detail.path = s3_path
                    logger.debug(f"{parser.task_id}/{parser.input_data_id}/{data_uri} をS3にアップロードしました。")
            else:
                logger.warning(f"annotattion_id={detail.annotation_id}: data_holding_typeが'outer'なのにpathがNoneです。")

        return detail

    def parser_to_request_body(self, project_id: str, parser: SimpleAnnotationParser) -> Dict[str, Any]:

        annotation: Annotation = Annotation.from_dict(  # type: ignore
            parser.load_json()
        )
        request_details: List[Dict[str, Any]] = []
        for detail in annotation.details:
            request_detail = self._to_annotation_detail_for_request(project_id, parser, detail)

            if request_detail is not None:
                # Enumをシリアライズするため、一度JSONにしてからDictに変換する
                request_details.append(json.loads(request_detail.to_json()))  # type: ignore

        request_body = {
            "project_id": project_id,
            "task_id": parser.task_id,
            "input_data_id": parser.input_data_id,
            "details": request_details,
        }

        return request_body

    def put_annotation_for_input_data(self, project_id: str, parser: SimpleAnnotationParser) -> bool:

        task_id = parser.task_id
        input_data_id = parser.input_data_id

        old_annotation, _ = self.service.api.get_editor_annotation(project_id, task_id, input_data_id)

        logger.info(f"task_id={task_id}, input_data_id={input_data_id} : アノテーションをリストアします。")
        request_body = self.parser_to_request_body(project_id, parser)

        updated_datetime = old_annotation["updated_datetime"] if old_annotation is not None else None
        request_body["updated_datetime"] = updated_datetime
        self.service.api.put_annotation(project_id, task_id, input_data_id, request_body=request_body)
        return True

    def put_annotation_for_task(self, project_id: str, task_parser: SimpleAnnotationParserByTask) -> int:

        logger.info(f"タスク'{task_parser.task_id}' のアノテーションをリストアします。")

        success_count = 0
        for parser in task_parser.lazy_parse():
            try:
                if self.put_annotation_for_input_data(project_id, parser):
                    success_count += 1
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(
                    f"task_id={parser.task_id}, input_data_id={parser.input_data_id} のアノテーションのリストアに失敗しました。: {e}"
                )

        logger.info(f"タスク'{task_parser.task_id}'の入力データ {success_count} 個に対してアノテーションをリストアしました。")
        return success_count

    def execute_task(self, project_id: str, task_parser: SimpleAnnotationParserByTask, my_account_id: str) -> bool:
        """
        1個のタスクに対してアノテーションを登録する。

        Args:
            project_id:
            task_parser:
            my_account_id: 自分自身のaccount_id

        Returns:
            1個以上の入力データのアノテーションを変更したか

        """
        task_id = task_parser.task_id
        if not self.confirm_processing(f"task_id={task_id} のアノテーションをリストアしますか？"):
            return False

        logger.info(f"task_id={task_id} に対して処理します。")

        task = self.service.wrapper.get_task_or_none(project_id, task_id)
        if task is None:
            logger.warning(f"task_id = '{task_id}' は存在しません。")
            return False

        if task["status"] in [TaskStatus.WORKING.value, TaskStatus.COMPLETE.value]:
            logger.info(f"タスク'{task_id}'は作業中または受入完了状態のため、アノテーションのリストアをスキップします。 status={task['status']}")
            return False

        if not can_put_annotation(task, my_account_id):
            logger.debug(f"タスク'{task_id}'は、過去に誰かに割り当てられたタスクで、現在の担当者が自分自身でないため、アノテーションのリストアをスキップします。")
            return False

        result_count = self.put_annotation_for_task(project_id, task_parser)
        return result_count > 0

    def main(self):
        args = self.args
        project_id = args.project_id
        annotation_dir_path = Path(args.annotation)

        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

        my_account_id = self.facade.get_my_account_id()

        # dumpしたアノテーションディレクトリの読み込み
        iter_task_parser = lazy_parse_simple_annotation_dir_by_task(annotation_dir_path)

        success_count = 0
        for task_parser in iter_task_parser:
            try:
                if len(task_id_list) > 0:
                    # コマンドライン引数で --task_idが指定された場合は、対象のタスクのみリストアする
                    if task_parser.task_id in task_id_list:
                        if self.execute_task(project_id, task_parser, my_account_id=my_account_id):
                            success_count += 1
                else:
                    # コマンドライン引数で --task_idが指定されていない場合はすべてをリストアする
                    if self.execute_task(project_id, task_parser, my_account_id=my_account_id):
                        success_count += 1

            except Exception as e:  # pylint: disable=broad-except
                logger.warning(f"task_id={task_parser.task_id} のアノテーションのリストアに失敗しました。: {e}")

        logger.info(f"{success_count} 個のタスクに対してアノテーションをリストアしました。")


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    RestoreAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--annotation", type=str, required=True, help="'annotation dump'コマンドの保存先ディレクトリのパスを指定してください。",
    )

    argument_parser.add_task_id(required=False)

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "restore"
    subcommand_help = "'annotation dump'コマンドで保存したファイルから、アノテーション情報をリストアします。"
    description = (
        "'annotation dump'コマンドで保存したファイルから、アノテーション情報をリストアします。"
        "ただし、作業中/完了状態のタスク、または「過去に割り当てられていて現在の担当者が自分自身でない」タスクはリストアできません。"
    )
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
