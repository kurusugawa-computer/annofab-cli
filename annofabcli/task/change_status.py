import argparse
import logging
import multiprocessing
import sys
from functools import partial
from typing import List, Optional, Tuple

import annofabapi

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery

logger = logging.getLogger(__name__)


class ChangeStatusMain:
    def __init__(self, service: annofabapi.Resource, all_yes: bool):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.all_yes = all_yes

    def change_status_for_task(
        self,
        project_id: str,
        status: str,
        task_id: str,
        task_query: Optional[TaskQuery] = None,
        task_index: Optional[int] = None,
    ) -> bool:
        logging_prefix = f"{task_index+1} 件目" if task_index is not None else ""
        dict_task = self.service.wrapper.get_task_or_none(project_id, task_id)
        if dict_task is None:
            logger.warning(f"{logging_prefix}: task_id='{task_id}'のタスクは存在しないので、スキップします。")
            return False
        return True

    def change_status_for_task_wrapper(
        self,
        tpl: Tuple[int, str],
        status: str,
        project_id: str,
        task_query: Optional[TaskQuery] = None,
    ) -> bool:
        task_index, task_id = tpl
        try:
            return self.change_status_for_task(
                project_id=project_id,
                task_id=task_id,
                task_index=task_index,
                task_query=task_query,
                status=status,
            )
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"タスク'{task_id}'のステータスの変更に失敗しました。", exc_info=True)
            return False

    def change_status(
        self,
        project_id: str,
        task_id_list: List[str],
        status: str,
        task_query: Optional[TaskQuery] = None,
        parallelism: Optional[int] = None,
    ):
        """
        作業中のタスクのステータスを変更する。

        Args:
            project_id:
            task_id_list:
            status: 変更後のタスクのステータス。
            parallelism: 並列度

        """

        if task_query is not None:
            task_query = self.facade.set_account_id_of_task_query(project_id, task_query)

        if status == "break":
            logger.info(f"{len(task_id_list)} 件のタスクのステータスを、作業中から休憩中に変更します。")
        else:
            logger.info(f"{len(task_id_list)} 件のタスクのステータスを、作業中から保留中に変更します。")

        if parallelism is not None:
            partial_func = partial(
                self.change_status_for_task_wrapper,
                project_id=project_id,
                task_query=task_query,
                status=status,
            )
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(partial_func, enumerate(task_id_list))
                success_count = len([e for e in result_bool_list if e])

        else:
            # 逐次処理
            for task_index, task_id in enumerate(task_id_list):
                try:
                    result = self.change_status_for_task(
                        project_id, status, task_id, task_index=task_index, task_query=task_query,
                    )
                    if result:
                        success_count += 1
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"タスク'{task_id}'のステータスの変更に失敗しました。", exc_info=True)
                    continue

        if status == "break":
            logger.info(f"{success_count} / {len(task_id_list)} 件 タスクのステータスを休憩中に変更しました。")
        else:
            logger.info(f"{success_count} / {len(task_id_list)} 件 タスクのステータスを保留中に変更しました。")


class ChangeStatus(AbstractCommandLineInterface):
    """
    作業中のタスクのステータスを変更する。
    """

    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli task change_status: error:"

        if args.parallelism is not None and not args.yes:
            print(
                f"{COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず ``--yes`` を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        if args.to_break is True:
            status = "break"
        elif args.to_on_hold is True:
            status = "on_hold"
        else:
            logger.error(f"変更後のタスクのステータスの指定方法が正しくありません。")
            return

        dict_task_query = annofabcli.common.cli.get_json_from_args(args.task_query)
        task_query: Optional[TaskQuery] = TaskQuery.from_dict(dict_task_query) if dict_task_query is not None else None

        project_id = args.project_id

        main_obj = ChangeStatusMain(self.service, all_yes=self.all_yes)
        main_obj.change_status(
            project_id,
            task_id_list=task_id_list,
            status=status,
            task_query=task_query,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeStatus(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    status_group = parser.add_mutually_exclusive_group(required=True)

    status_group.add_argument("--to_break", action="store_true", help="タスクのステータスを休憩中に変更します。")

    status_group.add_argument("--to_on_hold", action="store_true", help="タスクのステータスを保留中に変更します。")

    argument_parser.add_task_query()

    parser.add_argument(
        "--parallelism", type=int, help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "change_status"
    subcommand_help = "タスクのステータスを変更します。"
    description = "タスクのステータスを作業中から休憩中、または保留中に変更します。"
    epilog = ""

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
