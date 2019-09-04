import argparse
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Union  # pylint: disable=unused-import
import uuid
import annofabapi
from annofabapi.models import OrganizationMember, ProjectMember, ProjectMemberRole, OrganizationMemberRole

import annofabcli
import copy
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login


logger = logging.getLogger(__name__)


class CopyProject(AbstractCommandLineInterface):
    """
    プロジェクトをコピーする
    """
    @staticmethod
    def find_member(members: List[Dict[str, Any]], account_id: str) -> Optional[Dict[str, Any]]:
        for m in members:
            if m["account_id"] == account_id:
                return m

        return None

    def copy_project(self, src_project_id: str, dest_project_id: str, dest_title: str,
                     dest_overview: Optional[str] = None, copy_options: Optional[Dict[str, bool]] = None, wait_for_completion:bool = False):
        """
        プロジェクトメンバを、別のプロジェクトにコピーする。

        Args:
            src_project_id: コピー元のproject_id
            dest_project_id: コピー先のproject_id
            delete_dest: Trueならばコピー先にしか存在しないプロジェクトメンバを削除する。

        """

        self.validate_project(src_project_id, project_member_roles=[ProjectMemberRole.OWNER], organization_member_roles=[OrganizationMemberRole.ADMINISTRATOR, OrganizationMemberRole.OWNER])

        src_project_title = self.facade.get_project_title(src_project_id)

        confirm_message = f"{src_project_title} ({src_project_id} を、{dest_title} ({dest_project_id}) にコピーしますか？"
        if not self.confirm_processing(confirm_message):
            return

        if copy_options is not None:
            query_params: Dict[str, Any] = copy.deepcopy(copy_options)
        else:
            query_params: Dict[str, Any]  = {}

        query_params.update({
            "dest_project_id": dest_project_id,
            "dest_title": dest_title,
            "dest_overview": dest_overview
        })

        self.service.api.initiate_project_copy(src_project_id, query_params=query_params)
        logger.info(f"プロジェクトのコピーを実施しています。")


    def main(self):
        args = self.args
        dest_project_id = args.dest_project_id if args.dest_project_id is not None else uuid.uuid4()
        self.copy_project(args.src_project_id, args.dest_project_id, delete_dest=args.delete_dest)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    CopyProject(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id(help_message='コピー元のプロジェクトのproject_idを指定してください。')


    parser.add_argument('--dest_project_id', type=str,
                        help='新しいプロジェクトのproject_idを指定してください。省略した場合は UUIDv4 フォーマットになります。')
    parser.add_argument('--dest_title', type=str, required=True, help="新しいプロジェクトのタイトルを指定してください。")
    parser.add_argument('--dest_overview', type=str, help="新しいプロジェクトの概要を指定してください。")

    parser.add_argument('--copy_inputs', action='store_true', help="「入力データ」をコピーするかどうかを指定します。")
    parser.add_argument('--copy_tasks', action='store_true', help="「タスク」をコピーするかどうかを指定します。")
    parser.add_argument('--copy_annotations', action='store_true', help="「アノテーション」をコピーするかどうかを指定します。")
    parser.add_argument('--copy_webhooks', action='store_true', help="「Webhook」をコピーするかどうかを指定します。")
    parser.add_argument('--copy_supplementaly_data', action='store_true', help="「補助情報」をコピーするかどうかを指定します。")
    parser.add_argument('--copy_instructions', action='store_true', help="「作業ガイド」をコピーするかどうかを指定します。")

    parser.add_argument('--wait_for_completion', action='store_true', help="プロジェクトのコピーが完了するまで待ちます。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "copy"
    subcommand_help = "プロジェクトをコピーします。"
    description = ("プロジェクトをコピーして（アノテーション仕様やメンバーを引き継いで）、新しいプロジェクトを作成します。")
    epilog = "コピー元のプロジェクトに対してオーナロール、組織に対して組織管理者、組織オーナを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
