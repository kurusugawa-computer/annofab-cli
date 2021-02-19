import argparse
import copy
import logging
import uuid
from typing import Any, Dict, Optional

from annofabapi.models import JobType, OrganizationMemberRole, ProjectMemberRole

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    get_wait_options_from_args,
)
from annofabcli.common.dataclasses import WaitOptions

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)

logger = logging.getLogger(__name__)


class CopyProject(AbstractCommandLineInterface):
    """
    プロジェクトをコピーする
    """

    def copy_project(
        self,
        src_project_id: str,
        dest_project_id: str,
        dest_title: str,
        wait_options: WaitOptions,
        dest_overview: Optional[str] = None,
        copy_options: Optional[Dict[str, bool]] = None,
        wait_for_completion: bool = False,
    ):
        """
        プロジェクトメンバを、別のプロジェクトにコピーする。

        Args:
            src_project_id: コピー元のproject_id
            dest_project_id: 新しいプロジェクトのproject_id
            dest_title: 新しいプロジェクトのタイトル
            wait_options: 待つときのオプション
            dest_overview: 新しいプロジェクトの概要
            copy_options: 各項目についてコピーするかどうかのオプション
            wait_for_completion: プロジェクトのコピーが完了するまで待つかかどうか
        """

        self.validate_project(
            src_project_id,
            project_member_roles=[ProjectMemberRole.OWNER],
            organization_member_roles=[OrganizationMemberRole.ADMINISTRATOR, OrganizationMemberRole.OWNER],
        )

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

        request_body.update(
            {"dest_project_id": dest_project_id, "dest_title": dest_title, "dest_overview": dest_overview}
        )

        self.service.api.initiate_project_copy(src_project_id, request_body=request_body)
        logger.info(f"プロジェクトのコピーを実施しています。")

        if wait_for_completion:
            MAX_WAIT_MINUTUE = wait_options.max_tries * wait_options.interval / 60
            logger.info(f"最大{MAX_WAIT_MINUTUE}分間、コピーが完了するまで待ちます。")

            result = self.service.wrapper.wait_for_completion(
                src_project_id,
                job_type=JobType.COPY_PROJECT,
                job_access_interval=wait_options.interval,
                max_job_access=wait_options.max_tries,
            )
            if result:
                logger.info(f"プロジェクトのコピーが完了しました。")
            else:
                logger.info(f"プロジェクトのコピーは実行中 または 失敗しました。")
        else:
            logger.info(f"コピーの完了を待たずに終了します。")

    @staticmethod
    def _set_copy_options(options: Dict[str, Any]):
        if options.get("copy_annotations", False):
            options["copy_tasks"] = True
            options["copy_inputs"] = True
        if options.get("copy_tasks", False):
            options["copy_inputs"] = True
        if options.get("copy_supplementaly_data", False):
            options["copy_inputs"] = True
        return options

    def main(self):
        args = self.args
        dest_project_id = args.dest_project_id if args.dest_project_id is not None else str(uuid.uuid4())

        copy_option_kyes = [
            "copy_inputs",
            "copy_tasks",
            "copy_annotations",
            "copy_webhooks",
            "copy_supplementaly_data",
            "copy_instructions",
        ]
        copy_options: Dict[str, bool] = {}
        for key in copy_option_kyes:
            copy_options[key] = getattr(args, key)
        copy_options = self._set_copy_options(copy_options)

        wait_options = get_wait_options_from_args(get_json_from_args(args.wait_options), DEFAULT_WAIT_OPTIONS)

        self.copy_project(
            args.project_id,
            dest_project_id=dest_project_id,
            dest_title=args.dest_title,
            dest_overview=args.dest_overview,
            copy_options=copy_options,
            wait_for_completion=args.wait,
            wait_options=wait_options,
        )


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CopyProject(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id(help_message="コピー元のプロジェクトのproject_idを指定してください。")

    parser.add_argument("--dest_project_id", type=str, help="新しいプロジェクトのproject_idを指定してください。省略した場合は UUIDv4 フォーマットになります。")
    parser.add_argument("--dest_title", type=str, required=True, help="新しいプロジェクトのタイトルを指定してください。")
    parser.add_argument("--dest_overview", type=str, help="新しいプロジェクトの概要を指定してください。")

    parser.add_argument("--copy_inputs", action="store_true", help="「入力データ」をコピーします。")
    parser.add_argument("--copy_tasks", action="store_true", help="「タスク」をコピーします。指定した場合は入力データもコピーします。")
    parser.add_argument("--copy_annotations", action="store_true", help="「アノテーション」をコピーします。指定した場合は入力データとタスクもコピーします。")
    parser.add_argument("--copy_webhooks", action="store_true", help="「Webhook」をコピーします。")
    parser.add_argument("--copy_supplementaly_data", action="store_true", help="「補助情報」をコピーします。指定した場合は入力データもコピーします。")
    parser.add_argument("--copy_instructions", action="store_true", help="「作業ガイド」をコピーします。")

    parser.add_argument("--wait", action="store_true", help="プロジェクトのコピーが完了するまで待ちます。")

    parser.add_argument(
        "--wait_options",
        type=str,
        help="プロジェクトのコピーが完了するまで待つ際のオプションをJSON形式で指定してください。"
        "`file://`を先頭に付けるとjsonファイルを指定できます。"
        'デフォルとは`{"interval":60, "max_tries":360}` です。'
        "`interval`:完了したかを問い合わせる間隔[秒], "
        "`max_tires`:完了したかの問い合わせを最大何回行うか。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "copy"
    subcommand_help = "プロジェクトをコピーします。"
    description = "プロジェクトをコピーします。'プロジェクト設定', 'プロジェクトメンバー', 'アノテーション仕様'は必ずコピーされます。"
    epilog = "コピー元のプロジェクトに対してオーナロール、組織に対して組織管理者、組織オーナを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
