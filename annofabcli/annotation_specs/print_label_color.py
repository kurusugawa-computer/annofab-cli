"""
アノテーションラベルの色(RGB)を出力する
"""

import argparse
import logging
from typing import Any, Dict, Tuple

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    FormatArgument,
    build_annofabapi_resource_and_login,
)

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
        """
        # [REMOVE_V2_PARAM]
        annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params={"v": "2"})
        labels = annotation_specs["labels"]

        label_color_dict = {self.facade.get_label_name_en(label): self.get_rgb(label) for label in labels}

        self.print_according_to_format(label_color_dict)

    def main(self):
        args = self.args

        self.print_label_color(args.project_id)


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    argument_parser.add_format(
        choices=[FormatArgument.JSON, FormatArgument.PRETTY_JSON], default=FormatArgument.PRETTY_JSON
    )

    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PrintLabelColor(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_label_color"

    subcommand_help = "label_name(英名)とRGBの関係をJSONで出力します。"

    description = (
        "label_name(英名)とRGBの関係をJSONで出力します。"
        "出力された内容は、`write_annotation_image`ツールに利用します。"
        "出力内容は`Dict[LabelName, [R,G,B]]`です。"
    )

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
