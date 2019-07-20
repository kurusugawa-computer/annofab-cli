# coding: utf-8

"""
アノテーション仕様を出力する
"""

import argparse
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple  # pylint: disable=unused-import

from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class PrintSpecs(AbstractCommandLineInterface):
    """
    アノテーション仕様を出力する
    """

    def print_specs(self, project_id: str, arg_format: str):
        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])

        annotation_specs = self.service.api.get_annotation_specs(project_id)[0]
        labels = annotation_specs['labels']

        if arg_format == 'text':
            self._print_text_format_labels(labels)
        elif arg_format == 'pretty_json':
            print(json.dumps(labels, indent=2, ensure_ascii=False))
        elif arg_format == 'json':
            print(json.dumps(labels))

    def _print_text_format_labels(self, labels):
        for label in labels:
            print('\t'.join(
                [
                    label['label_id'],
                    label['annotation_type'],
                ] + [m['message'] for m in label['label_name']['messages']]
            ))
            for additional_data_definition in label['additional_data_definitions']:
                print('\t'.join(
                    [
                        '',
                        additional_data_definition['additional_data_definition_id'],
                        additional_data_definition['type'],
                    ] + [m['message'] for m in additional_data_definition['name']['messages']]
                ))
                if 'choice' == additional_data_definition['type']:
                    for choice in additional_data_definition['choices']:
                        print('\t'.join(
                            [
                                '',
                                '',
                                choice['choice_id'],
                                '',
                            ] + [m['message'] for m in choice['name']['messages']]
                        ))

    def main(self, args):
        super().process_common_args(args, __file__, logger)

        self.print_specs(args.project_id, args.format)


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument('project_id', type=str, help='対象のプロジェクトのproject_id')

    parser.add_argument(
        '-f', '--format', type=str, choices=['text', 'pretty_json', 'json'],
        default='text', help='出力フォーマット '
        'text: 人が見やすい内容, '
        'pretty_json: インデントされたJSON, '
        'json: フラットなJSON'
    )

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    PrintSpecs(service, facade).main(args)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = 'print_specs'

    subcommand_help = ('アノテーション仕様を出力する')

    description = ('アノテーション仕様を出力する')

    epilog = 'チェッカーまたはオーナロールを持つユーザで実行してください。'

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
