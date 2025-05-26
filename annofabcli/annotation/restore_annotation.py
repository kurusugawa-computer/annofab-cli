from __future__ import annotations

import argparse
import copy
import logging
import multiprocessing
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Optional

import annofabapi
from annofabapi.dataclass.annotation import AnnotationDetailV1, AnnotationV1
from annofabapi.models import AnnotationDataHoldingType, ProjectMemberRole, TaskStatus
from annofabapi.parser import (
    SimpleAnnotationParser,
    SimpleAnnotationParserByTask,
    lazy_parse_simple_annotation_dir_by_task,
)
from annofabapi.utils import can_put_annotation

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

logger = logging.getLogger(__name__)


class RestoreAnnotationMain(CommandLineWithConfirm):
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        project_id: str,
        is_force: bool,
        all_yes: bool,
    ) -> None:
        self.service = service
        CommandLineWithConfirm.__init__(self, all_yes)

        self.project_id = project_id
        self.is_force = is_force

    def _to_annotation_detail_for_request(self, parser: SimpleAnnotationParser, detail: AnnotationDetailV1) -> AnnotationDetailV1:
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
                    s3_path = self.service.wrapper.upload_data_to_s3(self.project_id, f, content_type="image/png")
                    detail.path = s3_path
            else:
                logger.warning(f"annotation_id='{detail.annotation_id}' :: data_holding_typeが'outer'なのにpathがNoneです。")

        return detail

    def parser_to_request_body(self, parser: SimpleAnnotationParser) -> dict[str, Any]:
        # infer_missing=Trueを指定する理由：Optional型のキーが存在しない場合でも、AnnotationV1データクラスのインスタンスを生成できるようにするため
        # https://qiita.com/yuji38kwmt/items/c5b56f70da3b8a70ba31
        annotation: AnnotationV1 = AnnotationV1.from_dict(parser.load_json(), infer_missing=True)
        request_details: list[dict[str, Any]] = []
        for detail in annotation.details:
            request_detail = self._to_annotation_detail_for_request(parser, detail)

            if request_detail is not None:
                request_details.append(request_detail.to_dict(encode_json=True))

        request_body = {
            "project_id": self.project_id,
            "task_id": parser.task_id,
            "input_data_id": parser.input_data_id,
            "details": request_details,
        }

        return request_body

    def put_annotation_for_input_data(self, parser: SimpleAnnotationParser) -> bool:
        task_id = parser.task_id
        input_data_id = parser.input_data_id

        old_annotation, _ = self.service.api.get_editor_annotation(self.project_id, task_id, input_data_id)

        logger.info(f"task_id='{task_id}', input_data_id='{input_data_id}' :: アノテーションをリストアします。")
        request_body = self.parser_to_request_body(parser)

        updated_datetime = old_annotation["updated_datetime"] if old_annotation is not None else None
        request_body["updated_datetime"] = updated_datetime
        self.service.api.put_annotation(self.project_id, task_id, input_data_id, request_body=request_body)
        return True

    def put_annotation_for_task(self, task_parser: SimpleAnnotationParserByTask) -> int:
        logger.info(f"タスク'{task_parser.task_id}' のアノテーションをリストアします。")

        success_count = 0
        for parser in task_parser.lazy_parse():
            try:
                if self.put_annotation_for_input_data(parser):
                    success_count += 1
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    f"task_id='{parser.task_id}', input_data_id='{parser.input_data_id}' のアノテーションのリストアに失敗しました。",
                    exc_info=True,
                )

        return success_count

    def execute_task(self, task_parser: SimpleAnnotationParserByTask, task_index: Optional[int] = None) -> bool:
        """
        1個のタスクに対してアノテーションを登録する。

        Args:
            task_parser: タスクをパースするためのインスタンス。
                Simpleアノテーションではないのに型が`SimpleAnnotationParserByTask`である理由：SimpleAnnotationParserByTaskのメソッドを利用するため
            task_index: タスクのインデックス

        Returns:
            1個以上の入力データのアノテーションを変更したか

        """
        logger_prefix = f"{task_index + 1!s} 件目: " if task_index is not None else ""
        task_id = task_parser.task_id
        if not self.confirm_processing(f"task_id='{task_id}' のアノテーションをリストアしますか？"):
            return False

        logger.info(f"{logger_prefix}task_id='{task_id}' に対して処理します。")

        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"task_id = '{task_id}' は存在しません。")
            return False

        if task["status"] in [TaskStatus.WORKING.value, TaskStatus.COMPLETE.value]:
            logger.info(f"タスク'{task_id}'は作業中または受入完了状態のため、アノテーションのリストアをスキップします。 status={task['status']}")
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
                    f"タスク'{task_id}'は、過去に誰かに割り当てられたタスクで、現在の担当者が自分自身でないため、アノテーションのリストアをスキップします。"
                    f"担当者を自分自身に変更してアノテーションを登録する場合は `--force` を指定してください。"
                )
                return False

        result_count = self.put_annotation_for_task(task_parser)
        logger.info(f"{logger_prefix}タスク'{task_parser.task_id}'の入力データ {result_count} 個に対してアノテーションをリストアしました。")

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
            logger.warning(f"task_id='{task_parser.task_id}' のアノテーションのリストアに失敗しました。", exc_info=True)
            return False

    def main(  # noqa: ANN201
        self,
        annotation_dir: Path,
        target_task_ids: Optional[set[str]] = None,
        parallelism: Optional[int] = None,
    ):
        """`annotation_dir`にあるファイルからアノテーションをリストアします。

        Args:
            annotation_dir (Path): `annofabcli annotation dump`で出力したディレクトリ
            target_task_ids: リストア対象のtask_id
            parallelism: 並列度。Noneなら逐次処理
        """

        def get_iter_task_parser_from_task_ids(_iter_task_parser: Iterator[SimpleAnnotationParserByTask], _target_task_ids: set[str]) -> Iterator[SimpleAnnotationParserByTask]:
            for task_parser in _iter_task_parser:
                if task_parser.task_id in _target_task_ids:
                    _target_task_ids.remove(task_parser.task_id)
                    yield task_parser

        # Simpleアノテーションではないのに`lazy_parse_simple_annotation_dir_by_task`を実行した理由：SimpleAnnotationParseに関する関数を利用するため
        iter_task_parser = lazy_parse_simple_annotation_dir_by_task(annotation_dir)

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
                    logger.warning(f"task_id='{task_parser.task_id}' :: アノテーションのリストアに失敗しました。", exc_info=True)
                    continue
                finally:
                    task_count += 1

        if target_task_ids is not None and len(tmp_target_task_ids) > 0:
            logger.warning(f"'--task_id'で指定したタスクの内 {len(tmp_target_task_ids)} 件は、リストア対象のアノテーションデータに含まれていません。 :: {tmp_target_task_ids}")

        logger.info(f"{success_count} / {task_count} 件のタスクに対してアノテーションをリストアしました。")


class RestoreAnnotation(CommandLine):
    """
    アノテーションをリストアする。
    """

    COMMON_MESSAGE = "annofabcli annotation restore: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず '--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args

        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id

        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        task_id_list = set(annofabcli.common.cli.get_list_from_args(args.task_id)) if args.task_id is not None else None

        RestoreAnnotationMain(self.service, project_id=project_id, is_force=args.force, all_yes=args.yes).main(args.annotation, target_task_ids=task_id_list, parallelism=args.parallelism)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    RestoreAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--annotation",
        type=Path,
        required=True,
        help="'annotation dump'コマンドの保存先ディレクトリのパスを指定してください。",
    )

    argument_parser.add_task_id(required=False)

    parser.add_argument(
        "--force",
        action="store_true",
        help="過去に割り当てられていて現在の担当者が自分自身でない場合、タスクの担当者を自分自身に変更してからアノテーションをリストアします。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="並列度。指定しない場合は、逐次的に処理します。指定した場合は、``--yes`` も指定してください。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "restore"
    subcommand_help = "'annotation dump'コマンドの出力結果から、アノテーション情報をリストアします。"
    description = "'annotation dump'コマンドの出力結果から、アノテーション情報をリストアします。ただし、作業中/完了状態のタスクはリストアできません。"
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
