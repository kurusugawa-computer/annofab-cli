import argparse
import logging
from enum import Enum
from typing import Optional

import annofabapi

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.annotation.dump_annotation import DumpAnnotation
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login
)

logger = logging.getLogger(__name__)


class ChangeBy(Enum):
    TASK = "task"
    INPUT_DATA = "input_data"


class ChangePropertiesOfAnnotation(AbstractCommandLineInterface):
    """
    アノテーションのプロパティを変更
    """

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.dump_annotation_obj = DumpAnnotation(service, facade, args)

    def main(self):
        args = self.args
        logger.debug(args)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangePropertiesOfAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    EXAMPLE_ANNOTATION_QUERY = (
        '{"label_name_en": "car", "attributes":[{"additional_data_definition_name_en": "occluded", "flag": true}]}'
    )

    parser.add_argument(
        "-aq",
        "--annotation_query",
        type=str,
        required=True,
        help="変更対象のアノテーションを検索する条件をJSON形式で指定します。"
        "``label_id`` または ``label_name_en`` のいずれかは必ず指定してください。"
        "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        f"(ex): ``{EXAMPLE_ANNOTATION_QUERY}``",
    )

    EXAMPLE_ATTRIBUTES = '[{"property_name": "is_protected", "new_value": true}]'
    parser.add_argument(
        "--properties",
        type=str,
        required=True,
        help="変更後のプロパティをJSON形式で指定します。" "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。" f"(ex): ``{EXAMPLE_ATTRIBUTES}``",
    )

    parser.add_argument("--force", action="store_true", help="完了状態のタスクのアノテーションのプロパティも変更します。")

    parser.add_argument(
        "--change_by",
        type=str,
        choices=[ChangeBy.TASK.value, ChangeBy.INPUT_DATA.value],
        default=ChangeBy.TASK.value,
        help="アノテーションプロパティの変更単位を指定してください。[Deprecated] 廃止される可能性があります。",
    )

    parser.add_argument(
        "--backup",
        type=str,
        required=False,
        help="アノテーションのバックアップを保存するディレクトリを指定してください。アノテーションの復元は ``annotation restore`` コマンドで実現できます。",
    )
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "change_properties"
    subcommand_help = "アノテーションのプロパティを変更します。"
    description = (
        "アノテーションのプロパティを一括で変更します。ただし、作業中状態のタスクのアノテーションのプロパティは変更できません。"
        "間違えてアノテーションプロパティを変更したときに復元できるようにするため、 ``--backup`` でバックアップ用のディレクトリを指定することを推奨します。"
    )
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
