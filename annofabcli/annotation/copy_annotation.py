import argparse
import logging
import sys
from abc import ABC
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

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
    src_task_id: str
    dest_task_id: str


@dataclass(frozen=True)
class CopyTargetByTask(CopyTarget):
    pass


@dataclass(frozen=True)
class CopyTargetByInputData(CopyTarget):
    src_input_data_id: str
    dest_input_data_id: str


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


class CopyAnnotationMain(AbstractCommandLineWithConfirmInterface):
    def __init__(self, service: annofabapi.Resource, *, all_yes: bool, overwrite: bool, merge: bool, force: bool):
        self.COMMON_MESSAGE = "annofabcli annotation copy: error:"
        self.INPUT_VALIDATE_404_ERROR_MESSAGE = (
            "argument --input: タスクの画像IDを取得しようとしましたが，404エラーが返却されました．指定されたタスクは存在しない可能性があります"
        )

        self.service = service
        self.overwrite = overwrite
        self.merge = merge
        self.force = force

        AbstractCommandLineWithConfirmInterface.__init__(self, all_yes)

    def copy_annotation_by_task(self, project_id: str, copy_target: CopyTargetByTask):
        """タスク単位でアノテーションをコピーする"""
        src_task = copy_target.src_task_id
        dest_task = copy_target.dest_task_id
        src_tasks = self.service.wrapper.get_task_or_none(project_id=project_id, task_id=src_task)
        dest_tasks = self.service.wrapper.get_task_or_none(project_id=project_id, task_id=dest_task)

        if src_tasks is None or dest_tasks is None:
            logger.error(f"{self.COMMON_MESSAGE} {self.INPUT_VALIDATE_404_ERROR_MESSAGE} ({src_task} {dest_task})")
            return
        else:
            for src_input, dest_input in zip(src_tasks["input_data_id_list"], dest_tasks["input_data_id_list"]):
                self.copy_annotation_by_input_data(
                    project_id,
                    CopyTargetByInputData(
                        src_task_id=src_task,
                        dest_task_id=dest_task,
                        src_input_data_id=src_input,
                        dest_input_data_id=dest_input,
                    ),
                )

    def copy_annotation_by_input_data(self, project_id: str, copy_target: CopyTargetByInputData):
        """入力データ単位でアノテーションをコピーする"""
        src_task = copy_target.src_task_id
        src_input = copy_target.src_input_data_id
        dest_task = copy_target.dest_task_id
        dest_input = copy_target.dest_input_data_id

        src_anno_details: List[Dict[str, Any]] = self.service.api.get_editor_annotation(
            project_id=project_id, task_id=src_task, input_data_id=src_input
        )[0]["details"]
        dest_anno_details: List[Dict[str, Any]] = self.service.api.get_editor_annotation(
            project_id=project_id, task_id=dest_task, input_data_id=dest_input
        )[0]["details"]
        if dest_anno_details:  # コピー先に一つでもアノテーションがあり，overwriteオプションがない場合
            if self.merge:  # mergeなら，
                # コピー元にidがないがコピー先にidがあるものはそのまま何もしない
                # コピー元にも，コピー先にもidがあるアノテーションはコピー元のもので上書き
                # コピー元にidがあるがコピー先にはidがないものは新規追加(put_input_data)にて行う
                logger.info(f"mergeが指定されたため，存在するアノテーションは上書きし，存在しない場合は追加します．")
                # to_annotation_detailからfrom_annotation_idと同じidのものをfrom_annotation_detailsに追加
                append_annotation_details = filter(
                    lambda item: not (
                        item["annotation_id"] in [detail["annotation_id"] for detail in src_anno_details]
                    ),
                    dest_anno_details,
                )
                src_anno_details.extend(append_annotation_details)
            elif self.overwrite:
                # コピー先のannotaitonを無視してput_annotationすればoverwrite扱いになる
                logger.info("overwriteが指定されたため，すでに存在するアノテーションを削除してコピーします。")
            else:
                logger.debug(
                    f"コピー先タスク={dest_task}/{dest_input} : "
                    f"コピー先のタスクに既にアノテーションが存在するため、アノテーションの登録をスキップします。"
                    f"アノテーションをインポートする場合は、`--overwrite` または '--merge' を指定してください。"
                )
                return
        request_body = self.service.wrapper._create_request_body_for_copy_annotation(
            project_id,
            dest_task,
            dest_input,
            src_details=src_anno_details,
            account_id=self.service.api.account_id,
            annotation_specs_relation=None,
        )
        to_annotation, _ = self.service.api.get_editor_annotation(project_id, dest_task, dest_input)
        request_body["updated_datetime"] = to_annotation["updated_datetime"]
        self.service.api.put_annotation(project_id, dest_task, dest_input, request_body=request_body)

    def copy_annotations(self, project_id: str, copy_target_list: List[CopyTarget], is_force: bool):
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
                src_task = copy_target.src_task_id
                dest_task = copy_target.dest_task_id
                if not self.confirm_processing(f"{src_task}タスクのアノテーションを{dest_task}タスクにコピーしますか？"):
                    return False
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
    def main(self):
        args = self.args
        project_id = args.project_id
        str_copy_target_list = get_list_from_args(args.input)

        copy_target_list: list[CopyTarget] = []
        for str_copy_target in str_copy_target_list:
            try:
                copy_target = parse_copy_target(str_copy_target)
                copy_target_list.append(copy_target)
            except ValueError as e:
                logger.warning(e)

        if len(str_copy_target_list) != len(copy_target_list):
            print(f"{self.COMMON_MESSAGE} argument '--input' 値が不正です。", file=sys.stderr)
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        main_obj = CopyAnnotationMain(
            self.service, all_yes=self.all_yes, overwrite=args.overwrite, merge=args.merge, force=args.force
        )
        main_obj.copy_annotations(project_id, copy_target_list, args.force)


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
