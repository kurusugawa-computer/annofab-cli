"""
アノテーションラベルの色(RGB)を出力する
"""

import argparse
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple  # pylint: disable=unused-import

import annofabapi

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.utils import build_annofabapi_resource_and_login
from annofabcli.common.cli import AbstractCommandLineInterface
from annofabapi.models import ProjectMemberRole

logger = logging.getLogger(__name__)


class PrintLabelColor(AbstractCommandLineInterface):
    """
    アノテーションラベルの色(RGB)を出力する
    """

    @staticmethod
    def get_rgb(label: Dict[str, Any]) -> Tuple[int, int, int]:
        color = label["color"]
        return color["red"], color["green"], color["blue"]

    def print_label_color(self, project_id: str):
        """
        今のアノテーション仕様から、label名とRGBを紐付ける
        Args:
            args:

        Returns:
        """

        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])

        annotation_specs = self.service.api.get_annotation_specs(project_id)[0]
        labels = annotation_specs["labels"]

        label_color_dict = {self.facade.get_label_name_en(l): self.get_rgb(l) for l in labels}

        print(json.dumps(label_color_dict, indent=2))

    def main(self, args):
        super().process_common_args(args, __file__, logger)

        self.print_label_color(args.project_id)


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument('project_id', type=str, help='対象のプロジェクトのproject_id')

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    PrintLabelColor(service, facade).main(args)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "print_label_color"

    subcommand_help = ("アノテーション仕様から、label_nameとRGBを対応付けたJSONを出力する。" "出力された内容は、`write_annotation_image`ツールに利用する。")

    description = ("アノテーション仕様から、label_nameとRGBを対応付けたJSONを出力する。"
                   "出力された内容は、`write_annotation_image`ツールに利用する。"
                   "出力内容は`Dict[LabelName, [R,G,B]]`である.")

    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.utils.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
