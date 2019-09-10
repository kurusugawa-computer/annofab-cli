import argparse
import copy
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple, Union  # pylint: disable=unused-import

from annofabapi.models import JobType, OrganizationMemberRole, ProjectMemberRole

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class CopyProject(AbstractCommandLineInterface):
    """
    プロジェクトをコピーする
    """
    def copy_project(self, src_project_id: str, dest_project_id: str, dest_title: str,
                     dest_overview: Optional[str] = None, copy_options: Optional[Dict[str, bool]] = None,
                     wait_for_completion: bool = False):
        """
        プロジェクトメンバを、別のプロジェクトにコピーする。

        Args:
            src_project_id: コピー元のproject_id
            dest_project_id: 新しいプロジェクトのproject_id
            dest_title: 新しいプロジェクトのタイトル
            dest_overview: 新しいプロジェクトの概要
            copy_options: 各項目についてコピーするかどうかのオプション
            wait_for_completion: プロジェクトのコピーが完了するまで待つかかどうか
        """

        self.validate_project(
            src_project_id, project_member_roles=[ProjectMemberRole.OWNER],
            organization_member_roles=[OrganizationMemberRole.ADMINISTRATOR, OrganizationMemberRole.OWNER])

        src_project_title = self.facade.get_project_title(src_project_id)

        if copy_options is not None:
            copy_target = [key.replace("copy_", "") for key in copy_options.keys() if copy_options[key]]
            logger.info(f"コピー対象: {str(copy_target)}")

        confirm_message = f"{src_project_title} ({src_project_id} を、{dest_title} ({dest_project_id}) にコピーしますか？"
        if not self.confirm_processing(confirm_message):
            return

        request_body: Dict[str, Any] = {}
        if copy_options is not None:
            request_body = copy.deepcopy(copy_options)

        request_body.update({
            "dest_project_id": dest_project_id,
            "dest_title": dest_title,
            "dest_overview": dest_overview
        })

        self.service.api.initiate_project_copy(src_project_id, request_body=request_body)
        logger.info(f"プロジェクトのコピーを実施しています。")

        if wait_for_completion:
            result = self.service.wrapper.wait_for_completion(src_project_id, job_type=JobType.COPY_PROJECT,
                                                              job_access_interval=60, max_job_access=15)
            if result:
                logger.info(f"プロジェクトのコピーが完了しました。")
            else:
                logger.info(f"プロジェクトのコピーは実行中 または 失敗しました。")

    def main(self):
        args = self.args
        dest_project_id = args.dest_project_id if args.dest_project_id is not None else str(uuid.uuid4())

        copy_option_kyes = [
            "copy_inputs", "copy_tasks", "copy_annotations", "copy_webhooks", "copy_supplementaly_data",
            "copy_instructions"
        ]
        copy_options: Dict[str, bool] = {}
        for key in copy_option_kyes:
            copy_options[key] = getattr(args, key)

        self.copy_project(args.project_id, dest_project_id=dest_project_id, dest_title=args.dest_title,
                          dest_overview=args.dest_overview, copy_options=copy_options,
                          wait_for_completion=args.wait_for_completion)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    CopyProject(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id(help_message='コピー元のプロジェクトのproject_idを指定してください。')

    parser.add_argument('--dest_project_id', type=str, help='新しいプロジェクトのproject_idを指定してください。省略した場合は UUIDv4 フォーマットになります。')
    parser.add_argument('--dest_title', type=str, required=True, help="新しいプロジェクトのタイトルを指定してください。")
    parser.add_argument('--dest_overview', type=str, help="新しいプロジェクトの概要を指定してください。")

    parser.add_argument('--copy_inputs', action='store_true', help="「入力データ」をコピーするかどうかを指定します。")
    parser.add_argument('--copy_tasks', action='store_true', help="「タスク」をコピーするかどうかを指定します。")
    parser.add_argument('--copy_annotations', action='store_true', help="「アノテーション」をコピーするかどうかを指定します。")
    parser.add_argument('--copy_webhooks', action='store_true', help="「Webhook」をコピーするかどうかを指定します。")
    parser.add_argument('--copy_supplementaly_data', action='store_true', help="「補助情報」をコピーするかどうかを指定します。")
    parser.add_argument('--copy_instructions', action='store_true', help="「作業ガイド」をコピーするかどうかを指定します。")

    parser.add_argument('--wait_for_completion', action='store_true', help=("プロジェクトのコピーが完了するまで待ちます。"
                                                                            "1分ごとにプロジェクトのコピーが完了したかを確認し、最大15分間待ちます。"))

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "copy"
    subcommand_help = "プロジェクトをコピーします。"
    description = ("プロジェクトをコピーして（アノテーション仕様やメンバーを引き継いで）、新しいプロジェクトを作成します。")
    epilog = "コピー元のプロジェクトに対してオーナロール、組織に対して組織管理者、組織オーナを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
