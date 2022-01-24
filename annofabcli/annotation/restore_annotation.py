import argparse
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

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
                logger.warning(f"annotation_id={detail.annotation_id}: data_holding_typeが'outer'なのにpathがNoneです。")

        return detail

    def parser_to_request_body(self, project_id: str, parser: SimpleAnnotationParser) -> Dict[str, Any]:
        # infer_missing=Trueを指定する理由：Optional型のキーが存在しない場合でも、Annotationデータクラスのインスタンスを生成できるようにするため
        # https://qiita.com/yuji38kwmt/items/c5b56f70da3b8a70ba31
        annotation: Annotation = Annotation.from_dict(parser.load_json(), infer_missing=True)
        request_details: List[Dict[str, Any]] = []
        for detail in annotation.details:
            request_detail = self._to_annotation_detail_for_request(project_id, parser, detail)

            if request_detail is not None:
                request_details.append(request_detail.to_dict(encode_json=True))

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
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    f"task_id={parser.task_id}, input_data_id={parser.input_data_id} のアノテーションのリストアに失敗しました。",
                    exc_info=True,
                )

        logger.info(f"タスク'{task_parser.task_id}'の入力データ {success_count} 個に対してアノテーションをリストアしました。")
        return success_count

    def execute_task(self, project_id: str, task_parser: SimpleAnnotationParserByTask, force: bool) -> bool:
        """
        1個のタスクに対してアノテーションを登録する。

        Args:
            project_id:
            task_parser:
            force:

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

        old_account_id: Optional[str] = None
        changed_operator = False
        if force:
            if not can_put_annotation(task, self.service.api.account_id):
                logger.debug(f"タスク'{task_id}' の担当者を自分自身に変更します。")
                self.service.wrapper.change_task_operator(
                    project_id, task_id, operator_account_id=self.service.api.account_id
                )
                changed_operator = True
                old_account_id = task["account_id"]

        else:
            if not can_put_annotation(task, self.service.api.account_id):
                logger.debug(
                    f"タスク'{task_id}'は、過去に誰かに割り当てられたタスクで、現在の担当者が自分自身でないため、アノテーションのリストアをスキップします。"
                    f"担当者を自分自身に変更してアノテーションを登録する場合は `--force` を指定してください。"
                )
                return False

        result_count = self.put_annotation_for_task(project_id, task_parser)
        if changed_operator:
            logger.debug(f"タスク'{task_id}' の担当者を元に戻します。")
            old_account_id = task["account_id"]
            self.service.wrapper.change_task_operator(project_id, task_id, operator_account_id=old_account_id)

        return result_count > 0

    def main(self):
        args = self.args
        project_id = args.project_id
        annotation_dir_path = Path(args.annotation)

        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

        # dumpしたアノテーションディレクトリの読み込み
        iter_task_parser = lazy_parse_simple_annotation_dir_by_task(annotation_dir_path)

        success_count = 0
        for task_parser in iter_task_parser:
            try:
                if len(task_id_list) > 0:
                    # コマンドライン引数で --task_idが指定された場合は、対象のタスクのみリストアする
                    if task_parser.task_id in task_id_list:
                        if self.execute_task(project_id, task_parser, force=args.force):
                            success_count += 1
                else:
                    # コマンドライン引数で --task_idが指定されていない場合はすべてをリストアする
                    if self.execute_task(project_id, task_parser, force=args.force):
                        success_count += 1

            except Exception:  # pylint: disable=broad-except
                logger.warning(f"task_id={task_parser.task_id} のアノテーションのリストアに失敗しました。", exc_info=True)

        logger.info(f"{success_count} 個のタスクに対してアノテーションをリストアしました。")


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    RestoreAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--annotation",
        type=str,
        required=True,
        help="'annotation dump'コマンドの保存先ディレクトリのパスを指定してください。",
    )

    argument_parser.add_task_id(required=False)

    parser.add_argument(
        "--force", action="store_true", help="過去に割り当てられていて現在の担当者が自分自身でない場合、タスクの担当者を自分自身に変更してからアノテーションをリストアします。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "restore"
    subcommand_help = "'annotation dump'コマンドで保存したファイルから、アノテーション情報をリストアします。"
    description = "'annotation dump'コマンドで保存したファイルから、アノテーション情報をリストアします。ただし、作業中/完了状態のタスクはリストアできません。"
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
