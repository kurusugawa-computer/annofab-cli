import argparse
import asyncio
import copy
import logging
import time
from typing import Any, Optional

import annofabapi
import more_itertools
import requests
from annofabapi.models import JobStatus, OrganizationMemberRole, ProjectJobType

import annofabcli
from annofabcli.common.cli import (
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class ChangeProjectOrganizationMain(CommandLineWithConfirm):
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        is_force: bool = False,
        all_yes: bool = False,
    ) -> None:
        self.service = service
        self.is_force = is_force
        self.facade = AnnofabApiFacade(service)
        super().__init__(all_yes)

    async def wait_until_jobs_finished_async(self, jobs: list[dict[str, Any]]) -> None:
        tasks = [
            self.wait_until_job_finished_async(
                project_id=job["project_id"],
                job_type=ProjectJobType(job["job_type"]),
                job_id=job["job_id"],
                job_access_interval=60,
                max_job_access=360,
            )
            for job in jobs
        ]
        results = await asyncio.gather(*tasks)
        success_count = 0
        for result in results:
            if result is not None and result == JobStatus.SUCCEEDED:
                success_count += 1

        logger.info(f"{success_count} 件のプロジェクトの組織の変更が成功しました。")

    async def wait_until_job_finished_async(
        self,
        project_id: str,
        job_type: ProjectJobType,
        job_id: str,
        job_access_interval: int = 60,
        max_job_access: int = 360,
    ) -> Optional["JobStatus"]:
        """
        指定したジョブが終了するまで非同期で待つ。

        Args:
            project_id: プロジェクトID
            job_type: ジョブ種別
            job_id: ジョブID。Noneの場合は、現在進行中のジョブが終了するまで待つ。
            job_access_interval: ジョブにアクセスする間隔[sec]
            max_job_access: ジョブに最大何回アクセスするか

        Returns:
            指定した時間（アクセス頻度と回数）待った後のジョブのステータスを返す。
            指定したジョブ（job_idがNoneの場合は現在進行中のジョブ）が存在しない場合は、Noneを返す。
        """

        def get_job_from_job_id(arg_job_id: str) -> Optional[dict[str, Any]]:
            content, _ = self.service.api.get_project_job(project_id, query_params={"type": job_type.value})
            job_list = content["list"]
            return more_itertools.first_true(job_list, pred=lambda e: e["job_id"] == arg_job_id)

        job_access_count = 0
        while True:
            # API呼び出しは同期なので、スレッドでラップ
            job = get_job_from_job_id(job_id)
            if job is None:
                logger.info(
                    "project_id='%s', job_id='%s', job_type='%s' のジョブは存在しません。",
                    project_id,
                    job_type.value,
                    job_id,
                )
                return None

            job_access_count += 1

            if job["job_status"] == JobStatus.SUCCEEDED.value:
                logger.info(
                    "project_id='%s', job_id='%s', job_type='%s' のジョブが成功しました。",
                    project_id,
                    job_id,
                    job_type.value,
                )
                return JobStatus.SUCCEEDED

            elif job["job_status"] == JobStatus.FAILED.value:
                logger.info(
                    "project_id='%s', job_id='%s', job_type='%s' のジョブが失敗しました。:: errors='%s'",
                    project_id,
                    job_id,
                    job_type.value,
                    job["errors"],
                )
                return JobStatus.FAILED

            elif job_access_count < max_job_access:
                logger.info(
                    "project_id='%s', job_id='%s', job_type='%s' のジョブは進行中です。%d 秒間待ちます。",
                    project_id,
                    job_id,
                    job_type.value,
                    job_access_interval,
                )
                await asyncio.sleep(job_access_interval)
            else:
                logger.info(
                    "project_id='%s', job_id='%s', job_type='%s' のジョブは %.1f 分以上経過しても、終了しませんでした。",
                    project_id,
                    job["job_id"],
                    job_type.value,
                    job_access_interval * job_access_count / 60,
                )
                return JobStatus.PROGRESS

    def change_organization_for_project(self, project_id: str, organization_name: str) -> Optional[dict[str, Any]]:
        project = self.service.wrapper.get_project_or_none(project_id)
        if project is None:
            logger.warning(f"project_id='{project_id}'のプロジェクトは存在しないので、スキップします。")
            return None

        project_name = project["title"]
        if project["project_status"] == "active":
            if self.is_force:
                if not self.confirm_processing(
                    f"project_id='{project_id}'のプロジェクトの状態を停止中にしたあと、所属する組織を'{organization_name}'に変更しますか？ :: project_name='{project_name}'"
                ):
                    return None
                request_body = copy.deepcopy(project)
                request_body.update(
                    {
                        "status": "suspended",
                        "last_updated_datetime": project["updated_datetime"],
                    }
                )
                project, _ = self.service.api.put_project(project_id, request_body=request_body, query_params={"v": "2"})
                logger.info(f"project_id='{project_id}'のプロジェクトのステータスを「停止中」に変更しました。 :: project_name='{project_name}'")
            else:
                logger.warning(
                    f"project_id='{project_id}'のプロジェクトのステータスは「進行中」のため、組織を変更できません。 `--force`オプションを指定すれば、停止中状態に変更した後組織を変更できます。"
                )
                return None
        elif not self.confirm_processing(f"project_id='{project_id}'のプロジェクトの組織を'{organization_name}'に変更しますか？ :: project_name='{project_name}'"):
            return None

        assert project is not None
        request_body = copy.deepcopy(project)
        request_body["organization_name"] = organization_name
        request_body["last_updated_datetime"] = project["updated_datetime"]
        request_body["status"] = project["project_status"]

        content, _ = self.service.api.put_project(project_id, request_body=request_body, query_params={"v": "2"})
        job = content["job"]
        logger.info(f"project_id='{project_id}'のプロジェクトの所属先組織を'{organization_name}'に変更するジョブを発行しました。 :: project_name='{project_name}', job_id='{job['job_id']}'")
        return job

    def change_organization_for_project_list(self, project_id_list: list[str], organization_name: str) -> list[dict[str, Any]]:
        if not self.facade.contains_any_organization_member_role(organization_name, [OrganizationMemberRole.OWNER, OrganizationMemberRole.ADMINISTRATOR]):
            logger.warning(f"変更先組織'{organization_name}'に対して管理者ロールまたはオーナロールでないため、プロジェクトの所属する組織を変更できません。")
            return []

        logger.info(f"{len(project_id_list)} 件のプロジェクトの組織を'{organization_name}'に変更するジョブを発行します。")

        job_list = []
        for project_id in project_id_list:
            try:
                result = self.change_organization_for_project(project_id, organization_name)
                if result is not None:
                    job_list.append(result)
            except requests.HTTPError:
                logger.warning(f"project_id='{project_id}'の組織変更でHTTPエラーが発生しました。", exc_info=True)
        logger.info(f"{len(job_list)}/{len(project_id_list)}件のプロジェクトの組織を'{organization_name}'に変更するジョブを発行しました。")
        return job_list


class ChangeProjectOrganization(CommandLine):
    def main(self) -> None:
        args = self.args
        project_id_list = annofabcli.common.cli.get_list_from_args(args.project_id)
        main_obj = ChangeProjectOrganizationMain(self.service, all_yes=args.yes, is_force=args.force)

        job_list = main_obj.change_organization_for_project_list(project_id_list=project_id_list, organization_name=args.organization)
        if len(job_list) == 0:
            logger.info("組織を変更するジョブは発行されませんでした。終了します。")
            return

        # APIリクエストを減らすため、とりあえず６０秒待ちます
        seconds = 60
        logger.info(f"ジョブの完了を{seconds}秒待ちます。")
        time.sleep(seconds)

        # すべてのジョブが完了するまで待つ
        asyncio.run(main_obj.wait_until_jobs_finished_async(job_list))


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeProjectOrganization(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-p",
        "--project_id",
        type=str,
        required=True,
        nargs="+",
        help="対象プロジェクトのproject_idを指定します。 ``file://`` を先頭に付けると、project_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "-org",
        "--organization",
        type=str,
        required=True,
        help="変更後の組織名を指定してください。",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="強制的に組織を変更します（将来拡張用）。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "change_organization"
    subcommand_help = "プロジェクトの所属する組織を変更します。"
    epilog = "プロジェクトのオーナロール、変更先の組織の管理者またはオーナーロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
