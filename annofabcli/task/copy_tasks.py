import argparse
import logging
import sys
from typing import List, Optional

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
from annofabcli.common.utils import duplicated_set

logger = logging.getLogger(__name__)


class CopyTasksMain(AbstracCommandCinfirmInterface):
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        all_yes: bool,
        copy_annotations: bool = False,
        copy_metadata: bool = False,
    ):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        AbstracCommandCinfirmInterface.__init__(self, all_yes)

        self.copy_annotations = copy_annotations
        self.copy_metadata = copy_metadata

    def copy_task(self, project_id: str, src_task_id: str, dest_task_id: str, task_index: Optional[int] = None) -> bool:

        logging_prefix = f"{task_index+1} 件目" if task_index is not None else ""
        src_task = self.service.wrapper.get_task_or_none(project_id, src_task_id)
        if src_task is None:
            logger.warning(f"{logging_prefix}: コピー元タスク'{src_task_id}'は存在しません。")
            return False

        old_dest_task = self.service.wrapper.get_task_or_none(project_id, dest_task_id)
        if old_dest_task is not None:
            logger.warning(f"{logging_prefix}: コピー先タスク'{dest_task_id}'はすでに存在します。")
            return False

        if not self.confirm_processing(f"タスク'{src_task_id}'を'{dest_task_id}'にコピーしますか？"):
            return False

        request_body = {"input_data_id_list": src_task["input_data_id_list"]}
        if self.copy_metadata:
            request_body["metadata"] = src_task["metadata"]

        self.service.api.put_task(project_id, dest_task_id, request_body=request_body)
        logger.debug(f"{logging_prefix} : タスク'{src_task_id}'を'{dest_task_id}'にコピーしました。")

        if self.copy_annotations:
            pass

        return True

    def main(
        self,
        project_id: str,
        src_task_id_list: List[str],
        dest_task_id_list: List[str],
    ):
        """
        タスクをコピーします

        """
        logger.info(f"{len(src_task_id_list)} 件 タスクをコピーします。")
        success_count = 0

        for task_index, (src_task_id, dest_task_id) in enumerate(zip(src_task_id_list, dest_task_id_list)):
            try:
                result = self.copy_task(
                    project_id, src_task_id=src_task_id, dest_task_id=dest_task_id, task_index=task_index
                )
                if result:
                    success_count += 1
            except Exception as e:
                logger.warning(f"タスク'{src_task_id}'を'{dest_task_id}'にコピーする際に失敗しました。", e)
                continue

        logger.info(f"{success_count} / {len(src_task_id_list)} 件 タスクをコピーしました。")


class CopyTasks(AbstractCommandLineInterface):
    COMMON_MESSAGE = "annofabcli task copy: error:"

    def validate(self, args: argparse.Namespace) -> bool:

        if args.parallelism is not None and not args.yes:
            print(
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず'--yes'を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            return

        src_task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        dest_task_id_list = annofabcli.common.cli.get_list_from_args(args.dest_task_id)

        duplicated_dest_task_id_list = duplicated_set(dest_task_id_list)
        if len(duplicated_dest_task_id_list) > 0:
            print(
                f"{self.COMMON_MESSAGE} argument --dest_task_id: 以下のtask_idが重複しています。'--dest_task_id'には一意な値を指定してください。\n"
                + duplicated_dest_task_id_list,
                file=sys.stderr,
            )
            return

        if len(src_task_id_list) != len(duplicated_dest_task_id_list):
            print(
                f"{self.COMMON_MESSAGE} argument: '--task_id'に渡した値の個数と'--dest_task_id'に渡した値の個数が異なります。",
                file=sys.stderr,
            )
            return

        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        main_obj = CopyTasksMain(
            self.service, all_yes=self.all_yes, copy_annotations=args.copy_annotations, copy_metadata=args.copy_metadata
        )
        main_obj.main(
            project_id,
            src_task_id_list=src_task_id_list,
            dest_task_id_list=dest_task_id_list,
            copy_annotations=args.copy_annotations,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CopyTasks(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "-t",
        "--task_id",
        type=str,
        required=True,
        nargs="+",
        help="コピー元のタスクのtask_idを指定してください。file://`を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "--dest_task_id",
        type=str,
        required=True,
        nargs="+",
        help="コピー先のタスクのtask_idを指定してください。file://`を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument("--copy_metadata", action="store_true", help="指定した場合、タスクのメタデータもコピーします。")
    parser.add_argument("--copy_annotations", action="store_true", help="指定した場合、アノテーションもコピーします。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "copy"
    subcommand_help = "タスクをコピーします。"
    description = "タスクをコピーします。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
