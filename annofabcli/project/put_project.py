from __future__ import annotations

import argparse
import logging
import uuid
from typing import Optional

from annofabapi.models import InputDataType

import annofabcli
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class PutProject(AbstractCommandLineInterface):
    def put_project(
        self,
        organization: str,
        title: str,
        input_data_type: InputDataType,
        *,
        project_id: Optional[str],
        overview: Optional[str],
        plugin_id: Optional[str],
    ):

        new_project_id = project_id if project_id is not None else str(uuid.uuid4())

        request_body = {
            "title": title,
            "organization_name": organization,
            "input_data_type": input_data_type.value,
            "overview": overview,
            "status": "active",
            "configuration": {"plugin_id": plugin_id},
        }
        new_project, _ = self.service.api.put_project(new_project_id, request_body=request_body)
        logger.info(
            f"project_id='{new_project['project_id']}'のプロジェクトを作成しました。 :: "
            f"title='{new_project['title']}', input_data_type='{new_project['input_data_type']}'"
        )

    def main(self):
        args = self.args
        self.put_project(
            args.organization,
            args.title,
            InputDataType(args.input_data_type),
            project_id=args.project_id,
            overview=args.overview,
            plugin_id=args.plugin_id,
        )


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PutProject(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument("-org", "--organization", type=str, required=True, help="プロジェクトの所属先組織")

    parser.add_argument("--title", type=str, required=True, help="作成するプロジェクトのタイトル")
    parser.add_argument(
        "--input_data_type",
        type=str,
        choices=[e.value for e in InputDataType],
        required=True,
        help="プロジェクトに登録する入力データの種類\n\n"
        f" * {InputDataType.IMAGE.value} : 画像\n"
        f" * {InputDataType.MOVIE.value} : 動画\n"
        f" * {InputDataType.CUSTOM.value} : カスタム（点群など）",
    )

    parser.add_argument(
        "-p", "--project_id", type=str, required=False, help="作成するプロジェクトのproject_id。未指定の場合はUUIDv4になります。"
    )
    parser.add_argument("--overview", type=str, help="作成するプロジェクトの概要")
    parser.add_argument(
        "--plugin_id", type=str, help="アノテーションエディタプラグインのplugin_id。``--input_data_type custom`` を指定した場合は必須です。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "put"
    subcommand_help = "プロジェクトを作成します。"
    epilog = "組織管理者、組織オーナを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
