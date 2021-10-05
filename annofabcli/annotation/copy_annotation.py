from enum import Enum, auto
import re

import argparse
import logging
from typing import Optional, List

import annofabapi

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.visualize import AddProps
from annofabapi.wrapper import TaskFrameKey, Wrapper
from annofabcli.annotation import copy_annotation, delete_annotation

logger = logging.getLogger(__name__)


class CopyAnnotationMain:
    def __init__(self, service: annofabapi.Resource, project_id: str):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.visualize = AddProps(self.service, project_id)


class CopyAnnotation(AbstractCommandLineInterface):
    INPUT_VALIDATE_404_ERROR_MESSAGE = "argument --input: タスクの画像IDを取得しようとしましたが，404エラーが返却されました．指定されたタスクは存在しない可能性があります"

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)

    class CopyTasksInfo:
        COMMON_MESSAGE = "annofabcli annotation import: error:"
        # 片方だけ変更されたりすると困るので，カプセル化しておく
        __from_task_frame_keys: List[TaskFrameKey] = []
        __to_task_frame_keys: List[TaskFrameKey] = []

        def __init__(self, service: annofabapi.Resource):
            self.service = service

        class INPUT_TYPECHECK_ENUM(Enum):
            TASK_AND_FILE = auto()
            TASK_ONLY = auto()
            FILE_PATH = auto()
            INVALID = auto()

        def append(self, project_id: str, input_data: str, validate_type=None):
            """
            input引数，バリデーションタイプから適切にリストを構成する
            """
            #validate_typeの指定がなければ検査する
            if validate_type == None:
                validate_type = self.recognize_input_type(input_data)
            if validate_type == self.INPUT_TYPECHECK_ENUM.TASK_AND_FILE:
                # task1/input1:task3:input3の形式
                # 分割・各変数に代入する
                from_task_and_input,to_task_and_input = input_data.split(':')
                from_task,from_input = from_task_and_input.split('/')
                to_task,to_input = to_task_and_input.split('/')
                self.__from_task_frame_keys = [TaskFrameKey(project_id=project_id,task_id = from_task,input_data_id=from_input )]
                self.__to_task_frame_keys = [TaskFrameKey(project_id=project_id,task_id = to_task,input_data_id=to_input )]
            elif validate_type==self.INPUT_TYPECHECK_ENUM.TASK_ONLY:
                # task1:task3の形式
                from_task,to_task = input_data.split(':')
                # task内に含まれるinput_data_idを全て取得
                # __from_task_frame_keysおよび__to_task_frame_keysにappendしていく
                from_task_or_none = self.service.wrapper.get_task_or_none(project_id=project_id , task_id=from_task)
                to_task_or_none = self.service.wrapper.get_task_or_none(project_id=project_id , task_id=to_task)
                if from_task_or_none==None :
                    # コピー「元」のタスクを参照しようとしてエラー
                    logger.error(f"{self.COMMON_MESSAGE} {self.INPUT_VALIDATE_404_ERROR_MESSAGE} ({from_task})")
                    return
                elif to_task_or_none==None:
                    # コピー「先」のタスクを参照しようとしてエラー
                    logger.error(f"{self.COMMON_MESSAGE} {self.INPUT_VALIDATE_404_ERROR_MESSAGE} ({to_task})")
                    return
                else:
                    # 返却されたDictからid_listを取り出す
                    from_input_id_list = from_task_or_none["input_data_id_list"]
                    to_input_id_list = to_task_or_none["input_data_id_list"]
                    # TODO : もしかしてtupleにしたほうがスマート？
                    for from_input,to_input in zip(from_input_id_list, to_input_id_list):
                        self.__from_task_frame_keys.append(TaskFrameKey(project_id=project_id,task_id = from_task,input_data_id=from_input ))
                        self.__to_task_frame_keys.append(TaskFrameKey(project_id=project_id,task_id = to_task,input_data_id=to_input ))
                
            elif validate_type==self.INPUT_TYPECHECK_ENUM.FILE_PATH:
                # inputの内容が複数個・複数種類だけ連続するテキストファイルが渡される
                for line in get_list_from_args(input_data):
                    self.append(line)
            # 受け入れられない形式 
            elif validate_type==self.INPUT_TYPECHECK_ENUM.INVALID:
                logger.error(f"{self.COMMON_MESSAGE} argument --input: 入力されたタスクを正しく解釈できませんでした({input_data})")
                return
            else:
                # 想定外
                pass

        def get_tasks(self):
            return zip(self.__from_task_frame_keys, self.__to_task_frame_keys)

        @classmethod
        def recognize_input_type(cls, input_data: str) -> bool:
            """
            引数のバリデーションをする．
            inputについて，
            task1:task2
            task1/input1:task2/input2
            file:/input.txt
            のいづれかの形式を保持しているかをチェックする．
            """
            if type(get_list_from_args([input_data])) == "list" and input_data:
                return cls.INPUT_TYPECHECK_ENUM.FILE_PATH
            if re.match(r"^(\w|-)+\/(\w|-)+:(\w|-)+\/(\w|-)+$", input_data):
                return cls.INPUT_TYPECHECK_ENUM.TASK_AND_FILE
            elif re.match(r"^(\w|-)+:(\w|-)+$", input_data):
                return cls.INPUT_TYPECHECK_ENUM.TASK_ONLY
            else:
                return cls.INPUT_TYPECHECK_ENUM.INVALID

    def main(self):
        args = self.args
        project_id = args.project_id
        input_data = args.input

        overwrite_mode = args.overwrite
        merge_mode = args.merge
        force_mode = args.force


        copy_tasks_info = self.CopyTasksInfo(self.service)
        copy_tasks_info.append(project_id, input_data)

        logger.debug(self)

        for from_frame_key, to_frame_key in copy_tasks_info.get_tasks():
            try:
                # コピー先にすでにannotationがある場合，サブコマンド引数によって挙動を変える
                # overwrite, mergeの共通処理
                if self.get_all_annotation_list(project_id=project_id):
                    # overwrite
                    if overwrite_mode:
                        # 元のアノテーションを削除
                        # deleteAnnotation.delete_annotation_for_task(
                        #     to_frame_key.project_id, to_frame_key.task_id, force=True
                        # )
                        pass
                    # merge
                    elif merge_mode:
                        pass
                # force
                self.service.wrapper.copy_annotation(
                    src=from_frame_key, dest=to_frame_key, annotation_specs_relation=None
                )
            except Exception as e:
                logger.error(f"{e}")
                logger.error(f"{from_frame_key},{to_frame_key}")


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
