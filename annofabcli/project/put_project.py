from __future__ import annotations

import argparse
import logging
import sys
import uuid
from enum import Enum
from typing import Any, Optional

from annofabapi.models import InputDataType
from annofabapi.plugin import EditorPluginId, ExtendSpecsPluginId

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    CommandLine,
    build_annofabapi_resource_and_login,
    get_json_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class CustomProjectType(Enum):
    """
    カスタムプロジェクトの種類
    """

    THREE_DIMENSION = "3d"
    """3次元データ"""


class PutProject(CommandLine):
    def put_project(  # noqa: ANN201
        self,
        organization: str,
        title: str,
        input_data_type: InputDataType,
        *,
        project_id: Optional[str],
        overview: Optional[str],
        editor_plugin_id: Optional[str],
        custom_project_type: Optional[CustomProjectType],
        configuration: Optional[dict[str, Any]],
    ):
        new_project_id = project_id if project_id is not None else str(uuid.uuid4())
        if configuration is None:
            configuration = {}

        if input_data_type == InputDataType.CUSTOM and custom_project_type is not None:
            assert editor_plugin_id is None
            editor_plugin_id = EditorPluginId.THREE_DIMENSION.value
            configuration.update({"extended_specs_plugin_id": ExtendSpecsPluginId.THREE_DIMENSION.value})

        configuration.update({"plugin_id": editor_plugin_id})

        request_body = {
            "title": title,
            "organization_name": organization,
            "input_data_type": input_data_type.value,
            "overview": overview,
            "status": "active",
            "configuration": configuration,
        }
        new_project, _ = self.service.api.put_project(new_project_id, request_body=request_body)
        logger.info(
            f"'{organization}'組織に、project_id='{new_project['project_id']}'のプロジェクトを作成しました。 :: title='{new_project['title']}', input_data_type='{new_project['input_data_type']}'"
        )

    COMMON_MESSAGE = "annofabcli project put: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.input_data_type == InputDataType.CUSTOM.value:  # noqa: SIM102
            if args.plugin_id is None and args.custom_project_type is None:
                print(  # noqa: T201
                    f"{self.COMMON_MESSAGE} '--input_data_type custom' を指定した場合は、'--plugin_id' または '--custom_project_type' が必須です。",
                    file=sys.stderr,
                )
                return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        self.put_project(
            args.organization,
            args.title,
            InputDataType(args.input_data_type),
            project_id=args.project_id,
            overview=args.overview,
            editor_plugin_id=args.plugin_id,
            custom_project_type=CustomProjectType(args.custom_project_type) if args.custom_project_type is not None else None,
            configuration=get_json_from_args(args.configuration),
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PutProject(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-org", "--organization", type=str, required=True, help="プロジェクトの所属先組織")

    parser.add_argument("--title", type=str, required=True, help="作成するプロジェクトのタイトル")
    parser.add_argument(
        "--input_data_type",
        type=str,
        choices=[e.value for e in InputDataType],
        required=True,
        help=f"プロジェクトに登録する入力データの種類\n\n * {InputDataType.IMAGE.value} : 画像\n * {InputDataType.MOVIE.value} : 動画\n * {InputDataType.CUSTOM.value} : カスタム（点群など）",
    )

    parser.add_argument("-p", "--project_id", type=str, required=False, help="作成するプロジェクトのproject_id。未指定の場合はUUIDv4になります。")
    parser.add_argument("--overview", type=str, help="作成するプロジェクトの概要")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--plugin_id", type=str, help="アノテーションエディタプラグインのplugin_id")
    group.add_argument(
        "--custom_project_type",
        type=str,
        choices=[e.value for e in CustomProjectType],
        help="カスタムプロジェクトの種類。 ``--input_data_type custom`` を指定したときのみ有効です。"
        "指定した値に対応するエディタプラグインが適用されるため、 `--plugin_id`` と同時には指定できません。\n"
        " * 3d : 3次元データ",
    )

    parser.add_argument(
        "--configuration",
        type=str,
        help="プロジェクトの設定情報。JSON形式で指定します。"
        "JSONの構造については https://annofab.com/docs/api/#operation/putProject のリクエストボディを参照してください。\n"
        "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "put"
    subcommand_help = "プロジェクトを作成します。"
    epilog = "組織管理者、組織オーナを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
