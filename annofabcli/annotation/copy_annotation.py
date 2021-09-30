from enum import Enum,auto
import re

import argparse
import logging
from typing import Optional

import annofabapi

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.visualize import AddProps
from annofabapi.wrapper import TaskFrameKey,Wrapper

logger = logging.getLogger(__name__)


class CopyAnnotationMain:
    def __init__(self, service: annofabapi.Resource, project_id: str):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.visualize = AddProps(self.service, project_id)


class CopyAnnotation(AbstractCommandLineInterface):
    COMMON_MESSAGE = "annofabcli annotation import: error:"
    INPUT_VALIDATE_404_ERROR_MESSAGE = "argument --input: タスクの画像IDを取得しようとしましたが，404エラーが返却されました．指定されたタスクは存在しない可能性があります"

    class INPUT_TYPECHECK_ENUM(Enum):
        TASK_AND_FILE=auto()
        TASK_ONLY=auto()
        FILE_PATH=auto()
        INVALID=auto()


    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)
    @classmethod
    def recognize_input_type(cls, args: argparse.Namespace) -> bool:
        """
            引数のバリデーションをする．
            inputについて，
            task1:task2
            task1/input1:task2/input2
            file:/input.txt
            のいづれかの形式を保持しているかをチェックする．
        """ 
        input_data = args.input
        if re.match(r'^(\w|-)+\/(\w|-)+:(\w|-)+\/(\w|-)+$',input_data):
            return cls.INPUT_TYPECHECK_ENUM.TASK_AND_FILE
        elif re.match(r'^(\w|-)+:(\w|-)+$',input_data):
            return cls.INPUT_TYPECHECK_ENUM.TASK_ONLY
        elif re.match(r'file:\/\/(\w|\.)+$',input_data):
            return cls.INPUT_TYPECHECK_ENUM.FILE_PATH
        else:
            return cls.INPUT_TYPECHECK_ENUM.INVALID



    def main(self):
        args = self.args
        validate_result = CopyAnnotation.recognize_input_type(args)
        logger.debug(validate_result)
        
        project_id = args.project_id
        input_data = args.input

        from_frame_keys:list[TaskFrameKey]=[]
        to_frame_keys:list[TaskFrameKey]=[]

        if validate_result == self.INPUT_TYPECHECK_ENUM.TASK_AND_FILE:
            # task1/input1:task3:input3の形式
            from_task_and_input,to_task_and_input = input_data.split(':')
            from_task,from_input = from_task_and_input.split('/')
            to_task,to_input = to_task_and_input.split('/')
            from_frame_keys = [TaskFrameKey(project_id=project_id,task_id = from_task,input_data_id=from_input )]
            to_frame_keys = [TaskFrameKey(project_id=project_id,task_id = to_task,input_data_id=to_input )]
        elif validate_result==self.INPUT_TYPECHECK_ENUM.TASK_ONLY:
            # task1:task3の形式
            from_task,to_task = input_data.split(':')
            #task内に含まれるinput_data_idを全て取得して，from_frame_keysおよびto_frame_keysにappendしていく
            from_task_or_none = self.service.wrapper.get_task_or_none(project_id=project_id , task_id=from_task)
            to_task_or_none = self.service.wrapper.get_task_or_none(project_id=project_id , task_id=to_task)
            if from_task_or_none==None :
                logger.error(f"{self.COMMON_MESSAGE} {self.INPUT_VALIDATE_404_ERROR_MESSAGE} ({from_task})")
                return
            elif to_task_or_none==None:
                #コピー先のタスクを参照しようとしてエラー
                logger.error(f"{self.COMMON_MESSAGE} {self.INPUT_VALIDATE_404_ERROR_MESSAGE} ({to_task})")
                return
            else:
                from_input_id_list = from_task_or_none["input_data_id_list"]
                to_input_id_list = to_task_or_none["input_data_id_list"]
                for from_input,to_input in zip(from_input_id_list, to_input_id_list):
                    from_frame_keys.append(TaskFrameKey(project_id=project_id,task_id = from_task,input_data_id=from_input ))
                    to_frame_keys.append(TaskFrameKey(project_id=project_id,task_id = to_task,input_data_id=to_input ))

        elif validate_result==self.INPUT_TYPECHECK_ENUM.FILE_PATH:
            # 以下のように，複数のinput形式が連続するファイルであることが考えられるので，全てに対応する
            # task1:task3
            # task2/input2:task4/input4
            pass
        elif validate_result==self.INPUT_TYPECHECK_ENUM.INVALID:
            logger.error(f"{self.COMMON_MESSAGE} argument --input: 入力されたタスクを正しく解釈できませんでした( {input_data} )")
            return 
        else:
            #想定外
            pass
        for from_frame_key,to_frame_key in zip(from_frame_keys,to_frame_keys):
            try:
                self.service.wrapper.copy_annotation(src=from_frame_key,dest=to_frame_key, annotation_specs_relation=None)
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
