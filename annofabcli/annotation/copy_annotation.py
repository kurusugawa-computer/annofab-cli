import argparse
import logging
import re
from enum import Enum, auto
from typing import List, Optional, Dict, Any

import requests

import annofabapi
from annofabapi import Wrapper
from annofabapi.models import AnnotationQuery,AnnotationDataHoldingType, SingleAnnotation, Task
from annofabapi.utils import can_put_annotation, str_now
from annofabapi.wrapper import TaskFrameKey, Wrapper
from annofabapi.dataclass.annotation import  AnnotationDetail

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.annotation import delete_annotation, import_annotation
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.facade import convert_annotation_specs_labels_v2_to_v1
from annofabcli.common.visualize import AddProps

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
        self.deleteAnnotation=delete_annotation.DeleteAnnotation(service=self.service,facade=self.facade,args=self.args)
        self.importAnnotation=import_annotation.ImportAnnotation(service=self.service,facade=self.facade,args=self.args)

    class CopyTasksInfo:
        COMMON_MESSAGE = "annofabcli annotation import: error:"
        # 片方だけ追加・変更されたりすると困るので，カプセル化しておく
        __from_task_frame_keys: List[TaskFrameKey] = []
        __to_task_frame_keys: List[TaskFrameKey] = []

        def __init__(self, service: annofabapi.Resource):
            self.service = service

        class INPUT_TYPECHECK_ENUM(Enum):
            TASK_AND_FILE = auto()
            TASK_ONLY = auto()
            FILE_PATH = auto()
            INVALID = auto()

        def append(self, project_id: str, input_data: str,is_force:bool=False, validate_type=None):
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
                from_task_id,to_task_id = input_data.split(':')
                # task内に含まれるinput_data_idを全て取得
                # __from_task_frame_keysおよび__to_task_frame_keysにappendしていく
                from_task_or_none = self.service.wrapper.get_task_or_none(project_id=project_id , task_id=from_task_id)
                to_task_or_none = self.service.wrapper.get_task_or_none(project_id=project_id , task_id=to_task_id)
                if from_task_or_none==None :
                    # コピー「元」のタスクを参照しようとしてエラー
                    logger.error(f"{self.COMMON_MESSAGE} {self.INPUT_VALIDATE_404_ERROR_MESSAGE} ({from_task_id})")
                    return
                elif to_task_or_none==None:
                    # コピー「先」のタスクを参照しようとしてエラー
                    logger.error(f"{self.COMMON_MESSAGE} {self.INPUT_VALIDATE_404_ERROR_MESSAGE} ({to_task_id})")
                    return
                else:
                    # コピー先のタスクが存在して，かつ，コピー先のタスクが自分の割当でない場合
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

                    # 返却されたDictからid_listを取り出す
                    from_input_id_list = from_task_or_none["input_data_id_list"]
                    to_input_id_list = to_task_or_none["input_data_id_list"]
                    # TODO : もしかしてtupleにしたほうがスマート？
                    for from_input,to_input in zip(from_input_id_list, to_input_id_list):
                        self.__from_task_frame_keys.append(TaskFrameKey(project_id=project_id,task_id = from_task_id,input_data_id=from_input ))
                        self.__to_task_frame_keys.append(TaskFrameKey(project_id=project_id,task_id = to_task_id,input_data_id=to_input ))
                
            elif validate_type==self.INPUT_TYPECHECK_ENUM.FILE_PATH:
                # inputの内容が複数個・複数種類だけ連続するテキストファイルが渡される
                for line in get_list_from_args(input_data):
                    self.append(line)
            # 受け入れられない形式 
            elif validate_type==self.INPUT_TYPECHECK_ENUM.INVALID:
                logger.error(f"{self.COMMON_MESSAGE} argument --input: 入力されたタスクを正しく解釈できませんでした．({input_data})")
                return
            else:
                # 想定外
                logger.error(f"{self.COMMON_MESSAGE} argument --input: 想定外のエラーです．")
                return 

        def get_tasks(self):
            return zip(self.__from_task_frame_keys, self.__to_task_frame_keys)

        @classmethod
        def recognize_input_type(cls, input_data: str) -> bool:
            """
            引数のバリデーションをする．すなわち，inputが
            task1:task2
            task1/input1:task2/input2
            file:/input.txt
            の形式に該当するか否かをチェックする．
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

        is_overwrite = args.overwrite
        is_merge = args.merge
        is_force = args.force


        copy_tasks_info = self.CopyTasksInfo(self.service)
        copy_tasks_info.append(project_id, input_data, is_force)
        from_annotations = []
        
        # コピー先にすでにannotationがあるかをチェック
        # もしすでにアノテーションがある場合，サブコマンド引数によって挙動を変える
        for from_task, to_task in copy_tasks_info.get_tasks():
            from_task_id=from_task.task_id
            from_input_id=from_task.input_data_id
            to_task_id=to_task.task_id
            to_input_id=to_task.input_data_id


            #logger.debug(from_input_data_list)
            #inputごと，つまりタスク内の画像ごとの処理
                    
            annotation_query:AnnotationQuery=dict()
            annotation_query['task_id']=to_task_id
            annotation_query['input_data_id']=to_input_id
            query_params = {'query':annotation_query}

            from_annotations=self.service.api.get_editor_annotation(project_id=project_id,task_id=from_task_id,input_data_id=from_input_id)[0]
            to_annotations=self.service.api.get_editor_annotation(project_id=project_id,task_id=to_task_id,input_data_id=to_input_id)[0]
            
            #コピー先に一つでもアノテーションがあり，overwriteでもない場合
            if to_annotations and not is_overwrite:
                if is_merge:
                    logger.info(f"mergeが指定されたため，存在するアノテーションは上書きし，存在しない場合は追加します．")

                    if from_annotations['details'] : #コピー先にannotationがある
                        # mergeならコピーではなく新規追加する
                        # すでに存在するIDに関しては削除してから新規追加する
                        # 新規追加はput_input_dataにて行う
                        details = from_annotations['details']
                        try:
                            old_details=self.service.api.get_editor_annotation(project_id=project_id,task_id=to_task_id,input_data_id=to_input_id)[0]['details']
                            details+=old_details
                            updated_datetime=from_annotations['updated_datetime']

                            src_annotation, _ = self.service.api.get_editor_annotation(project_id, from_task_id, from_input_id)
                            src_annotation_details: List[Dict[str, Any]] = src_annotation["details"]

                            if len(src_annotation_details) == 0:
                                logger.debug("コピー元にアノテーションが１つもないため、アノテーションのコピーをスキップします。")
                                continue

                            old_dest_annotation, _ = self.service.api.get_editor_annotation(project_id, to_task_id, to_input_id)

                            from_annotations_id = [detail['annotation_id'] for detail in src_annotation['details']]
                            append_anno_list = []
                            if old_dest_annotation:
                                #for from_anno,to_anno in zip(from_annotations,to_annotations):
                                for detail in to_annotations['details']:
                                    if not detail['annotation_id'] in from_annotations_id:
                                        logger.debug(append_anno_list)
                                        append_anno_list.append(detail)

                            src_annotation_details.extend(append_anno_list)
                            updated_datetime = old_dest_annotation["updated_datetime"]
                            request_body = self.service.wrapper._Wrapper__create_request_body_for_copy_annotation(
                                project_id,
                                to_task_id,
                                to_input_id,
                                src_details=src_annotation_details,
                                account_id=self.service.api.account_id,
                                annotation_specs_relation=None # annotation_specs_relation,
                            )
                            request_body["updated_datetime"] = updated_datetime
                            self.service.api.put_annotation(project_id, to_task_id, to_input_id, request_body=request_body)
        
                        except Exception as e:
                            logger.debug(e)
                            logger.debug(f"task_id={to_task_id},input_data_id={to_input_id},request_body={self.to_request_body(project_id, to_task_id,to_input_id,details, updated_datetime)})")
                        continue
                else:
                    logger.debug(
                    f"コピー先タスク={to_task_id}/{to_input_id} : "
                    f"コピー先のタスクに既にアノテーションが存在するため、アノテーションの登録をスキップします。"
                    f"アノテーションをインポートする場合は、`--overwrite` または '--merge' を指定してください。"
                    )
                    continue
            else:
                for from_frame_key, to_frame_key in copy_tasks_info.get_tasks():
                    try:
                        #実際のコピー処理
                        self.service.wrapper.copy_annotation(
                            src=from_frame_key, dest=to_frame_key, annotation_specs_relation=None
                        )
                    except Exception as e:
                        logger.error(f"{e}")
                        logger.error(f"{from_frame_key},{to_frame_key}")

    def to_request_body(
        self,
        project_id, 
        task_id,
        input_data_id,
        details: Dict[str, Any] ,
        updated_datetime=None
    ) -> Dict[str, Any]:
        request_details: List[Dict[str, Any]] = []
        for detail in details :
            request_detail = AnnotationDetail(
                label_id=detail['label_id'],
                annotation_id=detail['annotation_id'],
                account_id=detail['account_id'],
                data_holding_type=detail['data_holding_type'],
                data=detail['data'],
                additional_data_list=detail['additional_data_list'],
                is_protected=False,
                etag=None,
                url=None,
                path=None,
                created_datetime=updated_datetime,
                updated_datetime=updated_datetime,
            )
            if detail['data_holding_type'] == 'outer':
                request_detail.path = detail['path']

            request_details.append(detail)

            request_body = {
                "project_id": project_id,
                "task_id": task_id,
                "input_data_id": input_data_id,
                "details":request_details,
                "updated_datetime": updated_datetime
            }
            return request_body
        else:
            return None

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
