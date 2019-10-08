"""
アノテーション仕様を出力する
"""

import argparse
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple  # pylint: disable=unused-import

import more_itertools
from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument

logger = logging.getLogger(__name__)


class PrintAnnotationSpecsLabel(AbstractCommandLineInterface):
    """
    アノテーション仕様を出力する
    """
    def print_annotation_specs_label(self, project_id: str, arg_format: str, output: Optional[str] = None,
                                     old_updated_datetime: Optional[str] = None, before: Optional[int] = None):
        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])

        annotation_specs = self.service.api.get_annotation_specs(project_id)[0]
        labels = annotation_specs['labels']

        if arg_format == 'text':
            self._print_text_format_labels(labels)

        elif arg_format in [FormatArgument.JSON.value, FormatArgument.PRETTY_JSON.value]:
            annofabcli.utils.print_according_to_format(target=labels, arg_format=FormatArgument(arg_format),
                                                       output=output)

    def get_old_annotaion_specs_from_updated_datetime(self, project_id: str, old_updated_datetime: str):
        histories, _ = self.service.api.get_annotation_specs_histories(project_id)
        history = more_itertools.first_true(histories, pred=lambda e: e['updated_datetime'] == old_updated_datetime)
        annotation_specs = self.service.wrapper.get_annotation_specs_from_url(project_id, history['url'])
        return annotation_specs

    def get_old_annotaion_specs_from_index(self, project_id: str, before: int):
        histories, _ = self.service.api.get_annotation_specs_histories(project_id)

        history = more_itertools.first_true(histories, pred=lambda e: e['updated_datetime'] == old_updated_datetime)
        annotation_specs = self.service.wrapper.get_annotation_specs_from_url(project_id, history['url'])
        return annotation_specs

    def get_name_list(messages: List[Dict[str, Any]]):
        """
        日本語名、英語名のリスト（サイズ2）を取得する。日本語名が先頭に格納されている。
        """
        ja_name = [e["message"] for e in messages if e["lang"] == "ja-JP"][0]
        en_name = [e["message"] for e in messages if e["lang"] == "en-US"][0]
        return [ja_name, en_name]

    @staticmethod
    def _print_text_format_labels(labels):
        for label in labels:
            print('\t'.join([
                label['label_id'],
                label['annotation_type'],
            ] + PrintAnnotationSpecsLabel.get_name_list(label['label_name']['messages'])))
            for additional_data_definition in label['additional_data_definitions']:
                print('\t'.join([
                    '',
                    additional_data_definition['additional_data_definition_id'],
                    additional_data_definition['type'],
                ] + PrintAnnotationSpecsLabel.get_name_list(additional_data_definition['name']['messages'])))
                if additional_data_definition['type'] in ['choice', 'select']:
                    for choice in additional_data_definition['choices']:
                        print('\t'.join([
                            '',
                            '',
                            choice['choice_id'],
                            '',
                        ] + PrintAnnotationSpecsLabel.get_name_list(choice['name']['messages'])))

    def main(self):
        args = self.args
        self.print_annotation_specs_label(args.project_id, arg_format=args.format, output=args.output,
                                          old_updated_datetime=args.old_updated_datetime, before=args.before)


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    # 過去のアノテーション仕様を参照するためのオプション
    old_annotation_specs_group = parser.add_mutually_exclusive_group()
    old_annotation_specs_group.add_argument(
        '--old_updated_datetime', type=str, help=("出力したい過去のアノテーション仕様の更新日時を指定してください。 "
                                                  "更新日時は`annotation_specs history`コマンドで確認できます。 "
                                                  "ex) `2019-09-25T13:22:22.679+09:00`. "
                                                  "指定しない場合は、最新のアノテーション仕様が出力されます。 "))

    old_annotation_specs_group.add_argument(
        '--before', type=int, help=("出力したい過去のアノテーション仕様が、いくつか前のアノテーション仕様であるかを指定してください。  "
                                    "たとえば`1`を指定した場合、最新より1個前のアノテーション仕様を出力します。 "
                                    "指定しない場合は、最新のアノテーション仕様が出力されます。 "))

    parser.add_argument(
        '-f', '--format', type=str, choices=['text', FormatArgument.PRETTY_JSON.value, FormatArgument.JSON.value],
        default='text', help=f'出力フォーマット '
        'text: 人が見やすい形式, '
        f'{FormatArgument.PRETTY_JSON.value}: インデントされたJSON, '
        f'{FormatArgument.JSON.value}: フラットなJSON')

    argument_parser.add_output()
    argument_parser.add_query()

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
