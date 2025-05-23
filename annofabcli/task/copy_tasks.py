from __future__ import annotations

import argparse
import functools
import logging
import multiprocessing
import sys
from dataclasses import dataclass
from typing import Optional

import annofabapi
from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CopyTarget:
    src_task_id: str
    dest_task_id: str


def parse_copy_target(str_copy_target: str) -> CopyTarget:
    """
    コピー対象の文字列をパースします。
    以下の文字列をサポートします。
    * `src_task_id:dest_task_id`
    """
    tmp_array = str_copy_target.split(":")
    if len(tmp_array) != 2:
        raise ValueError(f"'{str_copy_target}' の形式が間違っています。")

    return CopyTarget(src_task_id=tmp_array[0], dest_task_id=tmp_array[1])


def get_copy_target_list(str_copy_target_list: list[str]) -> list[CopyTarget]:
    """コマンドラインから受けとった文字列のlistから、コピー対象のlistを取得する。"""
    copy_target_list: list[CopyTarget] = []

    for str_copy_target in str_copy_target_list:
        try:
            copy_target = parse_copy_target(str_copy_target)
            copy_target_list.append(copy_target)
        except ValueError as e:
            logger.warning(e)
    return copy_target_list


class CopyTasksMain(CommandLineWithConfirm):
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        all_yes: bool,
        is_copy_annotations: bool = False,
        is_copy_metadata: bool = False,
    ) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)
        CommandLineWithConfirm.__init__(self, all_yes)

        self.is_copy_annotations = is_copy_annotations
        self.is_copy_metadata = is_copy_metadata

    def copy_task(self, project_id: str, src_task_id: str, dest_task_id: str, task_index: Optional[int] = None) -> bool:
        logging_prefix = f"{task_index + 1} 件目" if task_index is not None else ""
        src_task = self.service.wrapper.get_task_or_none(project_id, src_task_id)
        if src_task is None:
            logger.warning(f"{logging_prefix}: コピー元タスク'{src_task_id}'は存在しないので、スキップします。")
            return False

        old_dest_task = self.service.wrapper.get_task_or_none(project_id, dest_task_id)
        if old_dest_task is not None:
            logger.warning(f"{logging_prefix}: コピー先タスク'{dest_task_id}'はすでに存在するので、スキップします。")
            return False

        if not self.confirm_processing(f"タスク'{src_task_id}'を'{dest_task_id}'にコピーしますか？"):
            return False

        request_body = {"input_data_id_list": src_task["input_data_id_list"]}
        if self.is_copy_metadata:
            request_body["metadata"] = src_task["metadata"]

        self.service.api.put_task(project_id, dest_task_id, request_body=request_body)
        logger.debug(f"{logging_prefix} : タスク'{src_task_id}'を'{dest_task_id}'にコピーしました。")

        return True

    def copy_task_wrapper(
        self,
        tpl: tuple[int, CopyTarget],
        project_id: str,
    ) -> bool:
        task_index, copy_target = tpl
        try:
            return self.copy_task(
                project_id=project_id,
                src_task_id=copy_target.src_task_id,
                dest_task_id=copy_target.dest_task_id,
                task_index=task_index,
            )
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"タスク'{copy_target.src_task_id}'を'{copy_target.dest_task_id}'にコピーする際に失敗しました。", exc_info=True)
            return False

    def main(self, project_id: str, copy_target_list: list[CopyTarget], parallelism: Optional[int] = None) -> None:
        """
        タスクをコピーします

        """
        logger.info(f"{len(copy_target_list)} 件のタスクをコピーします。")
        success_count = 0

        if parallelism is not None:
            partial_func = functools.partial(
                self.copy_task_wrapper,
                project_id=project_id,
            )

            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(partial_func, enumerate(copy_target_list))
                success_count = len([e for e in result_bool_list if e])

        else:
            for task_index, copy_target in enumerate(copy_target_list):
                try:
                    result = self.copy_task(
                        project_id,
                        src_task_id=copy_target.src_task_id,
                        dest_task_id=copy_target.dest_task_id,
                        task_index=task_index,
                    )
                    if result:
                        success_count += 1
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"タスク'{copy_target.src_task_id}'を'{copy_target.dest_task_id}'にコピーする際に失敗しました。", exc_info=True)
                    continue

        logger.info(f"{success_count} / {len(copy_target_list)} 件 タスクをコピーしました。")


class CopyTasks(CommandLine):
    COMMON_MESSAGE = "annofabcli task copy: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず '--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args

        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        str_copy_target_list = annofabcli.common.cli.get_list_from_args(args.input)
        copy_target_list = get_copy_target_list(str_copy_target_list)
        if len(str_copy_target_list) != len(copy_target_list):
            print(f"{self.COMMON_MESSAGE} argument '--input' の値が不正です。", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        main_obj = CopyTasksMain(
            self.service,
            all_yes=self.all_yes,
            is_copy_metadata=args.copy_metadata,
        )
        main_obj.main(project_id, copy_target_list=copy_target_list, parallelism=args.parallelism)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CopyTasks(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--input",
        type=str,
        nargs="+",
        required=True,
        help="コピー元のtask_idとコピー先のtask_idを ``:`` で区切って指定してください。\n``file://`` を先頭に付けると、コピー元とコピー先が記載されているファイルを指定できます。",
    )

    parser.add_argument("--copy_metadata", action="store_true", help="指定した場合、タスクのメタデータもコピーします。")

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "copy"
    subcommand_help = "タスクをコピーします。"
    description = "タスクをコピーします。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
