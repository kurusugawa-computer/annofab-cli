import argparse
import logging
import re
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

import annofabapi
from annofabapi.utils import can_put_annotation
from annofabapi.wrapper import TaskFrameKey

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


class CopyAnnotationMain:
    def __init__(self, service: annofabapi.Resource, project_id: str):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.visualize = AddProps(self.service, project_id)


class CopyAnnotation(AbstractCommandLineInterface):
    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)

    class CopyTasksInfo:
        def __init__(self, service: annofabapi.Resource):
            self.service = service
            self.COMMON_MESSAGE = "annofabcli annotation import: error:"
            self.INPUT_VALIDATE_404_ERROR_MESSAGE = (
                "argument --input: タスクの画像IDを取得しようとしましたが，404エラーが返却されました．指定されたタスクは存在しない可能性があります"
            )
            # from_task_frame_keysとto_task_frame_keysは要素同士が一対一対応で，どちらか片方だけ追加・変更・削除されたくないリスト
            # 外部からアクセスされると困るため，カプセル化しておく
            self.__task_frame_keys: List[Tuple[TaskFrameKey, TaskFrameKey]] = []

        class InputTypeCheckEnum(Enum):
            TaskAndFile = auto()
            TaskOnly = auto()
            FilePath = auto()
            Invalid = auto()

        def append(self, project_id: str, input_data: str, is_force: bool = False, validate_type=None):
            """
            input引数，バリデーションタイプから適切にリストを構成する
            """
            # validate_typeの指定がなければ検査する
            if validate_type is None:
                validate_type = self.recognize_input_type(input_data)

            if validate_type == self.InputTypeCheckEnum.TaskAndFile:
                # task1/input1:task3:input3の形式
                from_task_and_input, to_task_and_input = input_data.split(":")
                from_task_data_id, from_input_data_id = from_task_and_input.split("/")
                to_task_data_id, to_input_data_id = to_task_and_input.split("/")

                append_tuple = (
                    TaskFrameKey(project_id=project_id, task_id=from_task_data_id, input_data_id=from_input_data_id),
                    TaskFrameKey(project_id=project_id, task_id=to_task_data_id, input_data_id=to_input_data_id),
                )

                self.__task_frame_keys.append(append_tuple)
            elif validate_type == self.InputTypeCheckEnum.TaskOnly:
                # task1:task3の形式
                from_task_id, to_task_id = input_data.split(":")
                # task内に含まれるinput_data_idを全て取得
                from_task_or_none = self.service.wrapper.get_task_or_none(project_id=project_id, task_id=from_task_id)
                to_task_or_none = self.service.wrapper.get_task_or_none(project_id=project_id, task_id=to_task_id)
                if from_task_or_none is None:
                    # コピー「元」のタスクを参照しようとしてエラー
                    logger.error(f"{self.COMMON_MESSAGE} {self.INPUT_VALIDATE_404_ERROR_MESSAGE} ({from_task_id})")
                    return
                elif to_task_or_none is None:
                    # コピー「先」のタスクを参照しようとしてエラー
                    logger.error(f"{self.COMMON_MESSAGE} {self.INPUT_VALIDATE_404_ERROR_MESSAGE} ({to_task_id})")
                    return
                else:
                    # 返却されたDictからid_listを取り出す
                    for from_input_data_id, to_input_data_id in zip(
                        from_task_or_none["input_data_id_list"], to_task_or_none["input_data_id_list"]
                    ):
                        append_tuple = (
                            TaskFrameKey(project_id=project_id, task_id=from_task_id, input_data_id=from_input_data_id),
                            TaskFrameKey(project_id=project_id, task_id=to_task_id, input_data_id=to_input_data_id),
                        )
                        self.__task_frame_keys.append(append_tuple)

            elif validate_type == self.InputTypeCheckEnum.FilePath:
                # inputの内容が複数個・複数種類だけ連続するテキストファイルが渡される
                for line in get_list_from_args([input_data]):
                    line_validate_type = self.recognize_input_type(line)
                    self.append(project_id, line, is_force, line_validate_type)
            # 受け入れられない形式
            elif validate_type == self.InputTypeCheckEnum.Invalid:
                logger.error(f"{self.COMMON_MESSAGE} argument --input: 入力されたタスクを正しく解釈できませんでした．({input_data})")
                return
            else:
                # 想定外
                logger.error(f"{self.COMMON_MESSAGE} argument --input: 想定外のエラーです．")
                return

        def get_tasks(self):
            return self.__task_frame_keys

        @classmethod
        def recognize_input_type(cls, input_data: str) -> InputTypeCheckEnum:
            """
            引数のバリデーションをする．すなわち，inputが
            task1:task2
            task1/input1:task2/input2
            file:/input.txt
            の形式に該当するか否かをチェックする．
            """
            if not input_data:
                return cls.InputTypeCheckEnum.Invalid
            get_list_from_args_result = get_list_from_args([input_data])
            if not get_list_from_args_result[0] == input_data:
                return cls.InputTypeCheckEnum.FilePath
            if re.match(r"^(\w|-)+\/(\w|-)+:(\w|-)+\/(\w|-)+$", input_data):
                # task1/input1:task3:input3の形式
                return cls.InputTypeCheckEnum.TaskAndFile
            elif re.match(r"^(\w|-)+:(\w|-)+$", input_data):
                # task1:task3の形式
                return cls.InputTypeCheckEnum.TaskOnly
            else:
                return cls.InputTypeCheckEnum.Invalid

    def main(self):
        args = self.args
        project_id = args.project_id
        raw_input = args.input
        is_overwrite = args.overwrite
        is_merge = args.merge
        is_force = args.force

        copy_tasks_info = self.CopyTasksInfo(self.service)
        copy_tasks_info.append(project_id, raw_input, is_force)
        for from_task, to_task in copy_tasks_info.get_tasks():
            from_task_id = from_task.task_id
            from_input_id = from_task.input_data_id
            to_task_id = to_task.task_id
            to_input_id = to_task.input_data_id
            # 権限がない可能性を排除する
            # コピー先のタスクが存在して，かつ，コピー先のタスクが自分の割当でない場合
            to_task_or_none = self.service.wrapper.get_task_or_none(project_id=project_id, task_id=to_task_id)
            if to_task_or_none is None:
                # コピー「先」のタスクを参照しようとしてエラー
                logger.error(f"{self.COMMON_MESSAGE} {self.INPUT_VALIDATE_404_ERROR_MESSAGE} ({to_task_id})")
                return False
            if not can_put_annotation(to_task_or_none, self.service.api.account_id):
                if is_force:
                    logger.debug(f"`--force` が指定されているため，タスク'{to_task_id}' の担当者を自分自身に変更します。")
                    self.service.wrapper.change_task_operator(
                        project_id, to_task_id, operator_account_id=self.service.api.account_id
                    )
                else:
                    logger.debug(
                        f"タスク'{to_task_id}'は、過去に誰かに割り当てられたタスクで、現在の担当者が自分自身でないため、アノテーションのコピーをスキップします。"
                        f"担当者を自分自身に変更してアノテーションを登録する場合は `--force` を指定してください。"
                    )
                    return False
            from_annotations, _ = self.service.api.get_editor_annotation(
                project_id=project_id, task_id=from_task_id, input_data_id=from_input_id
            )
            to_annotations, _ = self.service.api.get_editor_annotation(
                project_id=project_id, task_id=to_task_id, input_data_id=to_input_id
            )
            from_annotation_details: List[Dict[str, Any]] = from_annotations["details"]
            to_annotation_details: List[Dict[str, Any]] = to_annotations["details"]
            if not from_annotation_details:
                logger.debug("コピー元にアノテーションが１つもないため、アノテーションのコピーをスキップします。")
                continue
            # コピー先にすでにannotationがあるかをチェックし，もしすでにアノテーションがある場合，サブコマンド引数によって挙動を変える
            if to_annotations and not is_overwrite:  # コピー先に一つでもアノテーションがあり，overwriteオプションがある場合
                if is_merge and to_annotation_details:  # mergeなら，
                    # コピー元にidがないがコピー先にidがあるものはそのまま何もしない
                    # コピー元にも，コピー先にもidがあるアノテーションはコピー元のもので上書き
                    # コピー元にidがあるがコピー先にはidがないものは新規追加(put_input_data)にて行う
                    logger.info(f"mergeが指定されたため，存在するアノテーションは上書きし，存在しない場合は追加します．")
                    # from_annnotation_detailsからid情報だけを得る
                    from_annotation_detail_id_list = [detail["annotation_id"] for detail in from_annotation_details]
                    # to_annotation_detailの中からfrom_annotation_idと同じidを持つものをfrom_annotation_detailsに追加
                    append_annotation_details = filter(
                        lambda item, from_annotation_detail_id_list_=from_annotation_detail_id_list: not (
                            item["annotation_id"] in from_annotation_detail_id_list_
                        ),
                        to_annotation_details,
                    )
                    from_annotation_details.extend(append_annotation_details)
                    request_body = self.service.wrapper._create_request_body_for_copy_annotation(
                        project_id,
                        to_task_id,
                        to_input_id,
                        src_details=from_annotation_details,
                        account_id=self.service.api.account_id,
                        annotation_specs_relation=None,
                    )
                    request_body["updated_datetime"] = to_annotations["updated_datetime"]
                    self.service.api.put_annotation(project_id, to_task_id, to_input_id, request_body=request_body)
                else:
                    logger.debug(
                        f"コピー先タスク={to_task_id}/{to_input_id} : "
                        f"コピー先のタスクに既にアノテーションが存在するため、アノテーションの登録をスキップします。"
                        f"アノテーションをインポートする場合は、`--overwrite` または '--merge' を指定してください。"
                    )
                    continue
            else:
                for from_frame_key, to_frame_key in copy_tasks_info.get_tasks():
                    # inputからinputへのコピー
                    self.service.wrapper.copy_annotation(src=from_frame_key, dest=to_frame_key)
        return True


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
        "--force", action="store_true", help="過去に割り当てられていて現在の担当者が自分自身でない場合、タスクの担当者を自分自身に変更してからアノテーションをコピーします。"
    )
    help_message = """アノテーションのコピー元タスクと，コピー先タスクを指定します。
    入力データ単位でコピーする場合
        task1:task3 task2:task4
        入力データは、タスク内の順序に対応しています。
        たとえば上記のコマンドだと、「task1の1番目の入力データのアノテーション」を「task3の1番目の入力データ」にコピーします。
    ファイル単位でコピーする場合
        task1/input1:task3/input3  task2/input2:task4/input4
    ファイルの指定
        file://input.txt
    """
    parser.add_argument("--input", type=str, required=True, help=help_message)
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "copy"
    subcommand_help = "debug help of copy subcommand"
    description = "debug description of copy subcommand"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
