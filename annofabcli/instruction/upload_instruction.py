import argparse
import logging
import urllib.parse
from typing import Any, Callable, Dict, List, Optional, Tuple, Union  # pylint: disable=unused-import

import annofabapi
from annofabapi.models import InputData, Task, TaskId, ProjectMemberRole

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument
from annofabcli.common.visualize import AddProps





from pathlib import Path
import argparse
import configparser
import json
import logging
import logging.config
import logging.handlers
import netrc
import os
import pyquery
import time
import uuid

import yaml

import annofabapi


logger = logging.getLogger(__name__)


class UploadInstruction(AbstractCommandLineInterface):
    """
    作業ガイドをアップロードする
    """

    #: 入力データIDの平均長さ
    average_input_data_id_length: int = 36

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)
        self.average_input_data_id_length = args.averate_input_data_id_length

    def upload_html_to_instruction(self, project_id: str, html_path: Path):
        pq_html = pyquery.PyQuery(filename=str(html_path))
        pq_img = pq_html('img')

        # 画像をすべてアップロードして、img要素のsrc属性値を annofab urlに変更する
        for img_elm in pq_img:
            src_value: str = img_elm.attrib.get('src')
            if src_value is None:
                continue

            if src_value.startswith('http:') or src_value.startswith('https:') or src_value.startswith('data:'):
                continue

            if src_value[0] == '/':
                img_path = Path(src_value)
            else:
                img_path = html_path.parent / src_value

            if img_path.exists():
                image_id = str(uuid.uuid4())
                instruction_image_id = self.service.wrapper.upload_instruction_image(project_id, image_id, str(img_path))
                img_url = (f'https://annofab.com/projects/{project_id}/instruction-images/'
                           f'{instruction_image_id}')

                logger.debug(f"image uploaded. file={img_path}, image_id={instruction_image_id}")
                img_elm.attrib['src'] = img_url
                time.sleep(1)

            else:
                logger.warning(f"image does not exist. path={img_path}")

        # 作業ガイドの更新(body element)
        html_data = pq_html('body').html()
        self.service.api.put_instruction(project_id, request_body=html_data)
        logger.info('作業ガイドを更新しました。')

    def main(self):
        args = self.args

        self.upload_html_to_instruction(args.project_id, Path(args.html))


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    UploadInstruction(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    # TODO body要素内のみ？
    parser.add_argument('--html', type='str', required=True,
                        help='作業ガイドとして登録するHTMLファイルのパスを指定します。')

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "upload_html"
    subcommand_help = "HTMLファイルを作業ガイドとして登録します。"
    description = ("HTMLファイルを作業ガイドとして登録します。"
                   "img要素のsrc属性がローカルの画像を参照している場合（http, https, dataスキーマが付与されていない）、"
                   "画像もアップロードします。")
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)

