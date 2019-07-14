"""
検査コメントを付与してタスクを差し戻します。
"""

import argparse
import logging
import time
import uuid
from typing import Any, Dict, List, Optional  # pylint: disable=unused-import

import annofabapi
import annofabapi.utils
import requests
from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class Download(AbstractCommandLineInterface):

    TARGETS = ['task', 'inspection', 'history_event', 'simple_annotation', 'full_annotation']

    def download_latest_annotation(self, target: str, project_id: str, output: str,):
        if target == 'simple_annotation':
            return self.facade.download_latest_simple_annotation_archive_with_waiting(project_id, output)

        elif target == 'full_annotation':
            return self.facade.download_latest_simple_annotation_archive_with_waiting(project_id, output)

    def download(self, target: str, project_id: str, output: str, latest: bool = False):
        if target == 'task':
            self.service.wrapper.download_project_tasks_url(project_id, output)

        elif target == 'inspection':
            self.service.wrapper.download_project_inspections_url(project_id, output)

        elif target == 'history_event':
            self.service.wrapper.download_project_task_history_events_url(project_id, output)

        elif target == 'simple_annotation' or target == 'full_annotation':
            if latest:
                # アノテーション情報を最新化してからダウンロードする
                result = self.download_latest_annotation(target, project_id, output)
                if not result:
                    logger.error(f"アノテーションのダウンロードが失敗しました。 target = {target}")

            else:
                if target == 'simple_annotation':
                    self.service.wrapper.download_annotation_archive(project_id, output)

                elif target == 'full_annotation':
                    self.service.wrapper.download_full_annotation_archive(project_id, output)


    def main(self, args: argparse.Namespace):
        super().process_common_args(args, __file__, logger)
        self.download(args.target, args.project_id, args.output, latest=args.latest)


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    Download(service, facade).main(args)


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument('target', type=str, choices=Download.TARGETS,
                        help='ダウンロード対象の項目を指定します。')

    parser.add_argument('-p', '--project_id', type=str, required=True, help='対象のプロジェクトのproject_idを指定します。')

    parser.add_argument('-o', '--output', type=str, required=True, help='ダウンロード先を指定します。')

    parser.add_argument('--latest', action='store_true',
                        help='最新のアノテーションをダウンロードする場合は指定してください。'
                             'ただしアノテーション情報を更新するのに数分かかります。')

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "download"
    subcommand_help = "タスクや検査コメント、アノテーションなどをダウンロードします。"
    description = ("タスクや検査コメント、アノテーションなどをダウンロードします。")
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
