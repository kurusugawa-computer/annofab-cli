# coding: utf-8
"""
アノテーション仕様を出力する
"""

import argparse
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple  # pylint: disable=unused-import

from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument

logger = logging.getLogger(__name__)


class PrintAnnotationSpecsLabel(AbstractCommandLineInterface):
    """
    アノテーション仕様を出力する
    """
    def print_annotation_specs_label(self, project_id: str, arg_format: str, output: Optional[str] = None):
        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])

        annotation_specs = self.service.api.get_annotation_specs(project_id)[0]
        labels = annotation_specs['labels']

        if arg_format == 'text':
            self._print_text_format_labels(labels)

        elif arg_format in [FormatArgument.JSON.value, FormatArgument.PRETTY_JSON.value]:
            annofabcli.utils.print_according_to_format(target=labels, arg_format=FormatArgument(arg_format),
                                                       output=output)

    @staticmethod
    def _print_text_format_labels(labels):
        for label in labels:
            print('\t'.join([
                label['label_id'],
                label['annotation_type'],
            ] + [m['message'] for m in label['label_name']['messages']]))
            for additional_data_definition in label['additional_data_definitions']:
                print('\t'.join([
                    '',
                    additional_data_definition['additional_data_definition_id'],
                    additional_data_definition['type'],
                ] + [m['message'] for m in additional_data_definition['name']['messages']]))
                if additional_data_definition['type'] == 'choice':
                    for choice in additional_data_definition['choices']:
                        print('\t'.join([
                            '',
                            '',
                            choice['choice_id'],
                            '',
                        ] + [m['message'] for m in choice['name']['messages']]))

    def main(self):
        args = self.args
        self.print_annotation_specs_label(args.project_id, args.format)


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument('-p', '--project_id', type=str, required=True, help='対象のプロジェクトのproject_idを指定します。')

    parser.add_argument(
        '-f', '--format', type=str, choices=['text', FormatArgument.PRETTY_JSON.value, FormatArgument.JSON.value],
        default='text', help=f'出力フォーマット '
        'text: 人が見やすい内容, '
        '{FormatArgument.PRETTY_JSON.value}: インデントされたJSON, '
        '{FormatArgument.JSON.value}: フラットなJSON')

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    PrintAnnotationSpecsLabel(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = 'list_label'

    subcommand_help = ('アノテーション仕様のラベル情報を出力する')

    description = ('アノテーション仕様のラベル情報を出力する')

    epilog = 'チェッカーまたはオーナロールを持つユーザで実行してください。'

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
