import argparse
import logging
from typing import Dict, List, Union

import annofabapi
from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstracCommandCinfirmInterface,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
)

logger = logging.getLogger(__name__)

Metadata = Dict[str, Union[str, bool, int]]


class UpdateMetadataOfTaskMain(AbstracCommandCinfirmInterface):
    def __init__(self, service: annofabapi.Resource, all_yes: bool = False):
        self.service = service
        AbstracCommandCinfirmInterface.__init__(self, all_yes)

    def update_metadata_of_task(
        self,
        project_id: str,
        task_id_list: List[str],
        metadata: Metadata,
    ):
        logger.info(f"{len(task_id_list)} 件のタスクのmetadataを、{metadata} に変更します。")

        request_body = {task_id: metadata for task_id in task_id_list}
        self.service.api.patch_tasks_metadata(project_id, request_body=request_body)


class UpdateMetadataOfTask(AbstractCommandLineInterface):
    def main(self):
        args = self.args
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        metadata = annofabcli.common.cli.get_json_from_args(args.metadata)
        super().validate_project(args.project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
        main_obj = UpdateMetadataOfTaskMain(self.service)
        main_obj.update_metadata_of_task(args.project_id, task_id_list=task_id_list, metadata=metadata)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateMetadataOfTask(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    argument_parser.add_task_id(required=True)

    parser.add_argument(
        "--metadata",
        required=True,
        type=str,
        help="タスクに設定する`metadata`をJSON形式で指定してください。メタデータの値には文字列、数値、真偽値のいずれかを指定してください。"
        "`file://`を先頭に付けると、JSON形式のファイルを指定できます。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "update_metadata"
    subcommand_help = "タスクのメタデータを更新します。"
    description = "タスクのメタデータを上書きして更新します。"
    epilog = "オーナまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog
    )
    parse_args(parser)
