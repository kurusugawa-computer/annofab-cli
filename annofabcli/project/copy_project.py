from __future__ import annotations

import argparse
import logging
import uuid
from collections.abc import Collection
from enum import Enum
from typing import Any, Optional

from annofabapi.models import OrganizationMemberRole, ProjectJobType, ProjectMemberRole

import annofabcli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.facade import AnnofabApiFacade

# 入力データをコピーしなければ1分以内にコピーが完了したので、intervalを60秒以下にした
DEFAULT_WAIT_OPTIONS = WaitOptions(interval=30, max_tries=360)

logger = logging.getLogger(__name__)


class CopiedTarget(Enum):
    """
    コピー対象のリソース
    補助情報をコピーする際は`input_data`を指定する必要があります。
    """

    INPUT_DATA = "input_data"
    TASK = "task"
    ANNOTATION = "annotation"
    WEBHOOK = "webhook"
    INSTRUCTION = "instruction"


COPIED_TARGET_AND_KEY_MAP = {
    CopiedTarget.INPUT_DATA: {"copy_inputs", "copy_supplementary_data"},
    CopiedTarget.TASK: {"copy_inputs", "copy_supplementary_data", "copy_tasks"},
    CopiedTarget.ANNOTATION: {"copy_inputs", "copy_supplementary_data", "copy_tasks", "copy_annotations"},
    CopiedTarget.WEBHOOK: {"copy_webhooks"},
    CopiedTarget.INSTRUCTION: {"copy_instructions"},
}
"""
コピー対象とリクエストボディに渡すキーの関係

入力データを指定した場合は、必ず補助情報もコピーするようにしています。
入力データのみコピーするユースケースがないためです。
"""


class CopyProject(CommandLine):
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
    ) -> None:
        """
        プロジェクトメンバを、別のプロジェクトにコピーする。

        Args:
            src_project_id: コピー元のproject_id
            dest_project_id: 新しいプロジェクトのproject_id
            dest_title: 新しいプロジェクトのタイトル
            wait_options: 待つときのオプション
            dest_overview: 新しいプロジェクトの概要
            copy_options: 各項目についてコピーするかどうかのオプション
        """

        self.validate_project(
            src_project_id,
            project_member_roles=[ProjectMemberRole.OWNER],
            organization_member_roles=[OrganizationMemberRole.ADMINISTRATOR, OrganizationMemberRole.OWNER],
        )

        src_project_title = self.facade.get_project_title(src_project_id)

        if copied_targets is not None:
            logger.info(f"コピー対象: {[e.value for e in copied_targets]}")

        confirm_message = f"プロジェクト'{src_project_title}'（project_id='{src_project_id}'）を、プロジェクト'{dest_title}'（project_id='{dest_project_id}'） にコピーしますか？"
        if not self.confirm_processing(confirm_message):
            logger.info(f"プロジェクト'{src_project_title}'（project_id='{src_project_id}'）をコピーせずに終了します。")
            return

        request_body: dict[str, Any] = {}

        if copied_targets is not None:
            for target in copied_targets:
                for key in COPIED_TARGET_AND_KEY_MAP[target]:
                    request_body[key] = True

        request_body.update({"dest_project_id": dest_project_id, "dest_title": dest_title, "dest_overview": dest_overview})

        self.service.api.initiate_project_copy(src_project_id, request_body=request_body)
        logger.info("プロジェクトのコピーを実施しています。")

        MAX_WAIT_MINUTE = DEFAULT_WAIT_OPTIONS.max_tries * DEFAULT_WAIT_OPTIONS.interval / 60  # noqa: N806
        logger.info(f"最大{MAX_WAIT_MINUTE}分間、コピーが完了するまで待ちます。")

        result = self.service.wrapper.wait_for_completion(
            src_project_id,
            job_type=ProjectJobType.COPY_PROJECT,
            job_access_interval=DEFAULT_WAIT_OPTIONS.interval,
            max_job_access=DEFAULT_WAIT_OPTIONS.max_tries,
        )
        if result:
            logger.info("プロジェクトのコピーが完了しました。")
        else:
            logger.info("プロジェクトのコピーは実行中 または 失敗しました。")

    def main(self) -> None:
        args = self.args
        dest_project_id = args.dest_project_id if args.dest_project_id is not None else str(uuid.uuid4())
        copied_targets = {CopiedTarget(e) for e in args.copied_target} if args.copied_target is not None else None
        self.copy_project(
            args.project_id,
            dest_project_id=dest_project_id,
            dest_title=args.dest_title,
            dest_overview=args.dest_overview,
            copied_targets=copied_targets,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CopyProject(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id(help_message="コピー元のプロジェクトのproject_idを指定してください。")

    parser.add_argument("--dest_project_id", type=str, help="新しいプロジェクトのproject_idを指定してください。省略した場合は UUIDv4 フォーマットになります。")
    parser.add_argument("--dest_title", type=str, required=True, help="新しいプロジェクトのタイトルを指定してください。")
    parser.add_argument("--dest_overview", type=str, help="新しいプロジェクトの概要を指定してください。")

    parser.add_argument("--copied_target", type=str, nargs="+", choices=[e.value for e in CopiedTarget], help="コピー対象を指定してください。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "copy"
    subcommand_help = "プロジェクトをコピーします。"
    description = "プロジェクトをコピーします。'プロジェクト設定', 'プロジェクトメンバー', 'アノテーション仕様'は必ずコピーされます。"
    epilog = "コピー元のプロジェクトに対してオーナロール、組織に対して組織管理者、組織オーナを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
