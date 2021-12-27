from __future__ import annotations
import copy
import argparse
import logging
import sys
from abc import ABC
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import annofabapi
from annofabapi.utils import can_put_annotation

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    AbstractCommandLineWithConfirmInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CopyTarget(ABC):
    pass

@dataclass(frozen=True)
class CopyTargetByTask(CopyTarget):
    src_task_id: str
    dest_task_id: str


@dataclass(frozen=True)
class CopyTargetByInputData(CopyTarget):
    src_task_id: str
    dest_task_id: str
    src_input_data_id: str
    dest_input_data_id: str

CopyTarget = Union[CopyTargetByTask, CopyTargetByInputData]

def parse_copy_target(str_copy_target: str) -> CopyTarget:
    """
    コピー対象の文字列をパースします。
    以下の文字列をサポートします。
    * `task1:task2`
    * `task1/input5:task2/input6`
    """

    def _parse_with_slash(target: str) -> Tuple[str, Optional[str]]:
        tmp = target.split("/")
        if len(tmp) == 1:
            return (tmp[0], None)
        elif len(tmp) == 2:
            return (tmp[0], tmp[1])
        else:
            raise ValueError(f"'{str_copy_target}' の形式が間違っています。")

    tmp_array = str_copy_target.split(":")
    if len(tmp_array) != 2:
        raise ValueError(f"'{str_copy_target}' の形式が間違っています。")

    str_src = tmp_array[0]
    str_dest = tmp_array[1]

    src = _parse_with_slash(str_src)
    dest = _parse_with_slash(str_dest)

    if src[1] is not None and dest[1] is not None:
        return CopyTargetByInputData(
            src_task_id=src[0], src_input_data_id=src[1], dest_task_id=dest[0], dest_input_data_id=dest[1]
        )
    elif src[1] is None and dest[1] is None:
        return CopyTargetByTask(src_task_id=src[0], dest_task_id=dest[0])
    else:
        raise ValueError(f"'{str_copy_target}' の形式が間違っています。")


def get_copy_target_list(str_copy_target_list: list[str]) -> list[CopyTarget]:
    copy_target_list = []
    for str_copy_target in str_copy_target_list:
        try:
            copy_target = parse_copy_target(str_copy_target)
            copy_target_list.append(copy_target)
        except ValueError as e:
            logger.warning(e)
    return copy_target_list

class CopyAnnotationMain(AbstractCommandLineWithConfirmInterface):
    def __init__(self, service: annofabapi.Resource, *, all_yes: bool, overwrite: bool, merge: bool, force: bool):

        self.service = service
        self.overwrite = overwrite
        self.merge = merge
        self.force = force

        AbstractCommandLineWithConfirmInterface.__init__(self, all_yes)

    def copy_annotation_by_task(self, project_id: str, copy_target: CopyTargetByTask):
        """タスク単位でアノテーションをコピーする"""
        src_task = self.service.wrapper.get_task_or_none(project_id=project_id, task_id=copy_target.src_task_id)
        dest_task = self.service.wrapper.get_task_or_none(project_id=project_id, task_id=copy_target.dest_task_id)

        if src_task is None:
            logger.warning(f"コピー元のタスク '{copy_target.src_task_id}' は存在しません。")
            return

        if dest_task is None:
            logger.warning(f"コピー先のタスク '{copy_target.dest_task_id}' は存在しません。")
            return

        for src_input, dest_input in zip(src_task["input_data_id_list"], dest_task["input_data_id_list"]):
            self.copy_annotation_by_input_data(
                project_id,
                CopyTargetByInputData(
                    src_task_id=copy_target.src_task_id,
                    dest_task_id=copy_target.dest_task_id,
                    src_input_data_id=src_input,
                    dest_input_data_id=dest_input,
                ),
            )

    def _merge_annotation(src_details:list[dict[str,Any]], dest_details:list[dict[str,Any]]) -> list[dict[str,Any]]:
        details = copy.deepcopy(dest_details)

        # annotation_idが重複してたときに上書きできるように、annotation_idからindexを取得できるようにする
        dest_annotation_id_dict = {e["annotation_id"]:i for i, e in enumerate(details)}


        for src_anno in src_details:
            annotation_id = src_anno["annotation_id"]

            if src_anno["annotation_id"] in dest_annotation_id_dict:
                index = dest_annotation_id_dict[annotation_id]
                details[index] = src_anno
            else:
                details.append(src_anno)
        return details

    def copy_annotation_by_input_data(self, project_id: str, copy_target: CopyTargetByInputData):
        """入力データ単位でアノテーションをコピーする"""
        src_annotation, _  = self.service.api.get_editor_annotation(
            project_id=project_id, task_id=copy_target.src_task_id, input_data_id=copy_target.src_input_data_id
        )
        src_anno_details = src_annotation["details"]

        dest_annotation, _ = self.service.api.get_editor_annotation(
            project_id=project_id, task_id=copy_target.dest_task_id, input_data_id=copy_target.dest_input_data_id
        )
        dest_anno_details = dest_annotation["details"]

        anno_details = []
        if self.overwrite or len(dest_anno_details) == 0:
            # `--overwrite`が指定されたか、コピー先のアノテーションが0件のとき
            anno_details = src_anno_details
        elif self.merge:
            anno_details = self._merge_annotation(src_anno_details, dest_anno_details)
        else:
            logger.debug(
                f"コピー先 '{copy_target.dest_task_id}/{copy_target.dest_input_data_id}' にアノテーションが存在するため、アノテーションのコピーをスキップします。"
                f"アノテーションをコピーする場合は、`--overwrite` または '--merge' を指定してください。"
            )
            return

        request_body = self.service.wrapper._create_request_body_for_copy_annotation(
            project_id,
            copy_target.dest_task_id,
            copy_target.dest_input_data_id,
            src_details=anno_details,
        )
        request_body["updated_datetime"] = dest_annotation["updated_datetime"]
        self.service.api.put_annotation(project_id, copy_target.dest_task_id, copy_target.dest_input_data_id, request_body=request_body)

    def copy_annotations(self, project_id: str, copy_target_list: list[CopyTarget], *, is_force: bool):
        for copy_target in copy_target_list:
            # 変数準備
            dest_task_id = copy_target.dest_task_id
            dest_task = self.service.wrapper.get_task_or_none(project_id, dest_task_id)
            if dest_task is None:
                # コピー先のタスクを取得できない
                logger.error(f"{self.COMMON_MESSAGE} {self.INPUT_VALIDATE_404_ERROR_MESSAGE} ({dest_task_id})")
                continue

            # 担当者割り当て変更チェック
            changed_operator = False
            original_operator: str
            if not can_put_annotation(dest_task, self.service.api.account_id):
                if is_force:
                    logger.debug(f"`--force` が指定されているため，タスク'{dest_task_id}' の担当者を自分自身に変更します。")
                    changed_operator = True
                    original_operator = dest_task["account_id"]
                    self.service.wrapper.change_task_operator(project_id, dest_task_id, self.service.api.account_id)
                else:
                    logger.debug(
                        f"タスク'{dest_task_id}'は、過去に誰かに割り当てられたタスクで、現在の担当者が自分自身でないため、アノテーションのコピーをスキップします。"
                        f"担当者を自分自身に変更してアノテーションを登録する場合は `--force` を指定してください。"
                    )
                    continue

            # コピー処理
            if isinstance(copy_target, CopyTargetByTask):
                if not self.confirm_processing(f"タスク'{copy_target.src_task_id}'のアノテーションを、タスク'{copy_target.dest_task_id}'にコピーしますか？"):
                    continue
                self.copy_annotation_by_task(project_id, copy_target)

            elif isinstance(copy_target, CopyTargetByInputData):
                src_task = copy_target.src_task_id
                src_input = copy_target.src_input_data_id
                dest_task = copy_target.dest_task_id
                dest_input = copy_target.dest_input_data_id
                if not self.confirm_processing(
                    f"{src_task}タスクの{src_input}アノテーションを{dest_task}タスクの{dest_input}にコピーしますか？"
                ):
                    return False
                self.copy_annotation_by_input_data(project_id, copy_target)

            # オペレータをもとに戻す
            if changed_operator:
                self.service.wrapper.change_task_operator(project_id, dest_task_id, original_operator)
        return True


class CopyAnnotation(AbstractCommandLineInterface):
    COMMON_MESSAGE = "annofabcli annotation copy: error:"

    def main(self):
        args = self.args
        project_id = args.project_id
        str_copy_target_list = get_list_from_args(args.input)

        copy_target_list = get_copy_target_list(str_copy_target_list)
        if len(str_copy_target_list) != len(copy_target_list):
            print(f"{self.COMMON_MESSAGE} argument '--input' 値が不正です。", file=sys.stderr)
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        main_obj = CopyAnnotationMain(
            self.service, all_yes=self.all_yes, overwrite=args.overwrite, merge=args.merge, force=args.force
        )
        main_obj.copy_annotations(project_id, copy_target_list, is_force=args.force)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CopyAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    overwrite_merge_group = parser.add_mutually_exclusive_group()
    overwrite_merge_group.add_argument(
        "--overwrite",
        action="store_true",
        help="アノテーションが存在する場合、 ``--overwrite`` を指定していれば、すでに存在するアノテーションを削除してコピーします。" "指定しなければ、アノテーションのコピーをスキップします。",
    )
    overwrite_merge_group.add_argument(
        "--merge",
        action="store_true",
        help="アノテーションが存在する場合、 ``--merge`` を指定していればアノテーションをannotation_id単位でマージしながらコピーします。"
        "annotation_idが一致すればアノテーションを上書き、一致しなければアノテーションを追加します。"
        "指定しなければ、アノテーションのコピーをスキップします。",
    )
    parser.add_argument(
        "--force", action="store_true", help="過去に割り当てられていて現在の担当者が自分自身でない場合、タスクの担当者を一時的に自分自身に変更してからアノテーションをコピーします。"
    )
    help_message = """アノテーションのコピー元タスクと，コピー先タスクを指定します。
    入力データ単位でコピーする場合
        from_task_id:to_task_id
        入力データは、タスク内の順序に対応しています。
        たとえば上記のコマンドだと、「from_taskの1番目の入力データのアノテーション」を「to_taskの1番目の入力データ」にコピーします。
    アノテーション単位でコピーする場合
        from_task_id/from_annotation_id:to_task_id/to_annotation_id
    ファイルの指定
        file://task.txt
    """
    parser.add_argument("--input", type=str, nargs="+", required=True, help=help_message)
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "copy"
    subcommand_help = "コピー元およびコピー先の入力を指定して，アノテーションをコピーします．"
    description = "コピー元およびコピー先の入力を指定して，アノテーションをコピーします．"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
