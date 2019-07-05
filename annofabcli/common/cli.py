"""
Command Line Interfaceの共通部分
"""

import argparse
from typing import List, Optional  # pylint: disable=unused-import

import annofabapi

import annofabcli
from annofabcli import AnnofabApiFacade
import abc
import logging
from annofabcli.common.exceptions import AuthorizationError


# TODO argsparser系のメソッドを作成する

class AbstractCommandLineInterface(abc.ABC):
    """
    CLI用の抽象クラス
    """

    #: annofabapi.Resourceインスタンス
    service: annofabapi.Resource

    #: AnnofabApiFacadeインスタンス
    facade: annofabcli.AnnofabApiFacade

    #: Trueならば、処理中に現れる問い合わせに対して、常に'yes'と回答したものとして処理する。
    all_yes: bool = False

    #: サブコマンドpyファイルで設定されたlogger
    logger: logging.Logger

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade):
        self.service = service
        self.facade = facade

    def process_common_args(self, args: argparse.Namespace, py_filepath: str, logger: logging.Logger):
        """
        共通のコマンドライン引数を処理する。
        Args:
            args: コマンドライン引数
            py_filepath: Python Filepath. この名前を元にログファイル名が決まる。


        """
        self.logger = logger
        annofabcli.utils.load_logging_config_from_args(args, py_filepath)
        self.all_yes = args.yes

        logger.info(f"args: {args}")


    @abc.abstractmethod
    def main(self, args: argparse.Namespace):
        pass


    def validate_project(self, project_id, required_owner:bool = False):
        """
        プロジェクトに対する権限が付与されているかを確認する。
        Args:
            project_id:　

        """
        self.project_title = self.facade.get_project_title(project_id)
        self.logger.info(f"project_title = {self.project_title}, project_id = {project_id}")

        if required_owner:
            if not self.facade.my_role_is_owner(project_id):
                raise AuthorizationError(self.project_title, ["owner"])


    def confirm_processing_task(self, task_id: str, confirm_message: str) -> bool:
        """
        タスクに対して処理するかどうか問い合わせる。
        `all_yes`属性も設定する。

        Args:
            task_id: 処理するtask_id
            confirm_message: 確認メッセージ

        Returns:
            Trueならば対象のタスクを処理する。

        """
        if self.all_yes:
            return True

        yes, all_yes = annofabcli.utils.prompt_yesno(confirm_message)

        if not yes:
            self.logger.info(f"task_id = {task_id} をスキップします。")
            return False

        if all_yes:
            self.all_yes = True

        return True
