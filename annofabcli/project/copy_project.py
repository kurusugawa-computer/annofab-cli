from __future__ import annotations

import argparse
import logging
import uuid
from enum import Enum
from typing import Any, Collection, Dict, Optional

from annofabapi.models import OrganizationMemberRole, ProjectJobType, ProjectMemberRole

import annofabcli
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.facade import AnnofabApiFacade

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)

logger = logging.getLogger(__name__)


class CopiedTarget(Enum):
    """コピー対象のリソース"""

    INPUT_DATA = "input_data"
    SUPPLEMENTARY_DATA = "supplementary_data"
    TASK = "task"
    ANNOTATION = "annotation"
    WEBHOOK = "webhook"
    INSTRUCTION = "instruction"


COPIED_TARGET_AND_KEY_MAP = {
    CopiedTarget.INPUT_DATA: "copy_inputs",
    CopiedTarget.SUPPLEMENTARY_DATA: "copy_supplementary_data",
    CopiedTarget.TASK: "copy_tasks",
    CopiedTarget.ANNOTATION: "copy_annotations",
    CopiedTarget.WEBHOOK: "copy_webhooks",
    CopiedTarget.INSTRUCTION: "copy_instructions",
}
"""コピー対象とリクエストボディに渡すキーの関係"""


class CopyProject(AbstractCommandLineInterface):
    """
    プロジェクトをコピーする
    """

    def copy_project(
        self,
        src_project_id: str,
        dest_project_id: str,
        dest_title: str,
        dest_overview: Optional[str] = None,
        copied_targets: Optional[Collection[CopiedTarget]] = None,
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

        set_copied_targets = self._get_completion_copied_targets(copied_targets) if copied_targets is not None else None
        if set_copied_targets is not None:
            str_copied_targets = ", ".join([e.value for e in set_copied_targets])
            logger.info(f"コピー対象: {str_copied_targets}")

        confirm_message = f"{src_project_title} ({src_project_id} を、{dest_title} ({dest_project_id}) にコピーしますか？"
        if not self.confirm_processing(confirm_message):
            logger.info(f"{src_project_title} ({src_project_id} をコピーせずに終了します。")
            return

        request_body: Dict[str, Any] = {}

        if set_copied_targets is not None:
            for target in set_copied_targets:
                key = COPIED_TARGET_AND_KEY_MAP[target]
                request_body[key] = True

        request_body.update(
            {"dest_project_id": dest_project_id, "dest_title": dest_title, "dest_overview": dest_overview}
        )

        self.service.api.initiate_project_copy(src_project_id, request_body=request_body)
        logger.info(f"プロジェクトのコピーを実施しています。")

        if wait_for_completion:
            MAX_WAIT_MINUTE = DEFAULT_WAIT_OPTIONS.max_tries * DEFAULT_WAIT_OPTIONS.interval / 60
            logger.info(f"最大{MAX_WAIT_MINUTE}分間、コピーが完了するまで待ちます。")

            result = self.service.wrapper.wait_for_completion(
                src_project_id,
                job_type=ProjectJobType.COPY_PROJECT,
                job_access_interval=DEFAULT_WAIT_OPTIONS.interval,
                max_job_access=DEFAULT_WAIT_OPTIONS.max_tries,
            )
            if result:
                logger.info(f"プロジェクトのコピーが完了しました。")
            else:
                logger.info(f"プロジェクトのコピーは実行中 または 失敗しました。")
        else:
            logger.info(f"コピーの完了を待たずに終了します。")

    @staticmethod
    def _get_completion_copied_targets(copied_targets: Collection[CopiedTarget]) -> set[CopiedTarget]:
        """
        コピー対象から、補完したコピー対象を取得する。
        """
        result = set(copied_targets)

        if CopiedTarget.ANNOTATION in result:
            result.add(CopiedTarget.TASK)
            result.add(CopiedTarget.INPUT_DATA)

        if CopiedTarget.TASK in result:
            result.add(CopiedTarget.INPUT_DATA)

        if CopiedTarget.SUPPLEMENTARY_DATA in result:
            result.add(CopiedTarget.INPUT_DATA)

        return result

    def main(self):
        args = self.args
        dest_project_id = args.dest_project_id if args.dest_project_id is not None else str(uuid.uuid4())
        copied_targets = {CopiedTarget(e) for e in args.copied_target} if args.copied_target is not None else None
        self.copy_project(
            args.project_id,
            dest_project_id=dest_project_id,
            dest_title=args.dest_title,
            dest_overview=args.dest_overview,
            copied_targets=copied_targets,
            wait_for_completion=args.wait,
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

    parser.add_argument(
        "--copied_target", type=str, nargs="+", choices=[e.value for e in CopiedTarget], help="コピー対象を指定してください。"
    )

    parser.add_argument("--wait", action="store_true", help="プロジェクトのコピーが完了するまで待ちます。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "copy"
    subcommand_help = "プロジェクトをコピーします。"
    description = "プロジェクトをコピーします。'プロジェクト設定', 'プロジェクトメンバー', 'アノテーション仕様'は必ずコピーされます。"
    epilog = "コピー元のプロジェクトに対してオーナロール、組織に対して組織管理者、組織オーナを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
