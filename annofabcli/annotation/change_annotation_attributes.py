from __future__ import annotations

import argparse
import functools
import json
import logging
import multiprocessing
import sys
from enum import Enum
from pathlib import Path
from typing import Any

import annofabapi
from annofabapi.dataclass.task import Task
from annofabapi.models import ProjectMemberRole, TaskStatus

import annofabcli.common.cli
from annofabcli.annotation.annotation_query import (
    AnnotationQueryForAPI,
    AnnotationQueryForCLI,
    convert_attributes_from_cli_to_additional_data_list_v2,
)
from annofabcli.annotation.dump_annotation import DumpAnnotationMain
from annofabcli.annotation.update_result import AnnotationUpdateResult
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
    get_json_from_args,
)
from annofabcli.common.exceptions import AnnofabCliException
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class ChangeBy(Enum):
    TASK = "task"
    INPUT_DATA = "input_data"


class ChangeAnnotationAttributesMain(CommandLineWithConfirm):
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        project_id: str,
        include_complete_task: bool,
        all_yes: bool,
    ) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)
        CommandLineWithConfirm.__init__(self, all_yes)

        self.project_id = project_id
        self.include_complete_task = include_complete_task

        self.dump_annotation_obj = DumpAnnotationMain(service, project_id)

    def change_annotation_attributes(self, annotation_list: list[dict[str, Any]], additional_data_list: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        """
        アノテーション属性値を変更する。

        Args:
            annotation_list: 変更対象のアノテーション一覧
            additional_data_list: 変更後の属性値(`AdditionalDataListV2`スキーマ)

        Returns:
            `batch_update_annotations`メソッドのレスポンス

        """

        def _to_request_body_elm(annotation: dict[str, Any]) -> dict[str, Any]:
            detail = annotation["detail"]
            return {
                "data": {
                    "project_id": annotation["project_id"],
                    "task_id": annotation["task_id"],
                    "input_data_id": annotation["input_data_id"],
                    "updated_datetime": annotation["updated_datetime"],
                    "annotation_id": detail["annotation_id"],
                    "label_id": detail["label_id"],
                    "additional_data_list": additional_data_list,
                },
                "_type": "PutV2",
            }

        request_body = [_to_request_body_elm(annotation) for annotation in annotation_list]
        return self.service.api.batch_update_annotations(self.project_id, request_body=request_body)[0]

    def get_annotation_list_for_task(self, task_id: str, annotation_query: AnnotationQueryForAPI) -> list[dict[str, Any]]:
        """
        タスク内のアノテーション一覧を取得する。

        Args:
            project_id:
            task_id:
            annotation_query: アノテーションの検索条件

        Returns:
            アノテーション一覧
        """
        dict_query = annotation_query.to_dict()
        dict_query.update({"task_id": task_id, "exact_match_task_id": True})
        annotation_list = self.service.wrapper.get_all_annotation_list(self.project_id, query_params={"query": dict_query})
        return annotation_list

    def change_attributes_for_task(
        self,
        task_id: str,
        annotation_query: AnnotationQueryForAPI,
        additional_data_list: list[dict[str, Any]],
        *,
        backup_dir: Path | None = None,
        task_index: int | None = None,
    ) -> tuple[bool, int]:
        """
        タスクに対してアノテーション属性値を変更する。

        Args:
            project_id:
            task_id:
            annotation_query: 変更対象のアノテーションの検索条件
            additional_data_list: 変更後の属性値(`AdditionalDataListV2`スキーマ)
            force: タスクのステータスによらず更新する
            backup_dir: アノテーションをバックアップとして保存するディレクトリ。指定しない場合は、バックアップを取得しない。

        Returns:
            tuple[0]: 成功した場合はTrue、失敗した場合はFalse
            tuple[1]: 変更したアノテーションの個数
        """
        logger_prefix = f"{task_index + 1!s} 件目 :: " if task_index is not None else ""
        dict_task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if dict_task is None:
            logger.warning(f"task_id = '{task_id}' は存在しません。")
            return False, 0

        task: Task = Task.from_dict(dict_task)
        if task.status == TaskStatus.WORKING:
            logger.warning(f"task_id='{task_id}': タスクが作業中状態のため、スキップします。")
            return False, 0

        if not self.include_complete_task:  # noqa: SIM102
            if task.status == TaskStatus.COMPLETE:
                logger.warning(f"task_id='{task_id}': タスクが完了状態のため、スキップします。完了状態のタスクのアノテーション属性値を変更するには、 ``--include_complete_task`` を指定してください。")
                return False, 0

        annotation_list = self.get_annotation_list_for_task(task_id, annotation_query)
        logger.info(
            f"{logger_prefix}task_id='{task_id}'の変更対象アノテーション数は{len(annotation_list)}個です。 :: task_phase='{task.phase.value}', task_status='{task.status.value}', task_updated_datetime='{task.updated_datetime}'"  # noqa: E501
        )
        if len(annotation_list) == 0:
            logger.info(f"{logger_prefix}task_id='{task_id}'には変更対象のアノテーションが存在しないので、スキップします。")
            return False, 0

        if not self.confirm_processing(f"task_id='{task_id}' のアノテーション属性値を変更しますか？"):
            return False, 0

        if backup_dir is not None:
            self.dump_annotation_obj.dump_annotation_for_task(task_id, output_dir=backup_dir)

        self.change_annotation_attributes(annotation_list, additional_data_list)
        logger.info(f"{logger_prefix}task_id='{task_id}': {len(annotation_list)} 個のアノテーションの属性値を変更しました。")
        return True, len(annotation_list)

    def change_attributes_for_task_wrapper(
        self,
        tpl: tuple[int, str],
        annotation_query: AnnotationQueryForAPI,
        additional_data_list: list[dict[str, Any]],
        *,
        backup_dir: Path | None = None,
    ) -> AnnotationUpdateResult:
        task_index, task_id = tpl
        try:
            success, changed_count = self.change_attributes_for_task(
                task_id,
                annotation_query=annotation_query,
                additional_data_list=additional_data_list,
                backup_dir=backup_dir,
                task_index=task_index,
            )
            return AnnotationUpdateResult(success, changed_count)
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"タスク'{task_id}'のアノテーションの属性値の変更に失敗しました。", exc_info=True)
            return AnnotationUpdateResult(success=False, changed_count=0, failed=True)

    def get_target_task_id_list(self, task_id_list: list[str] | None, *, all_tasks: bool = False) -> list[str]:
        """明示的に指定された処理対象のタスクID一覧を取得する。

        Args:
            task_id_list: 対象のタスクID一覧。
            all_tasks: 全タスクを対象にする場合はTrue。

        Returns:
            処理対象のタスクID一覧。
        """
        if task_id_list is not None:
            return task_id_list
        if not all_tasks:
            raise ValueError("対象のタスクIDまたは全タスク指定が必要です。")

        task_list = self.service.wrapper.get_all_tasks(self.project_id)
        if len(task_list) >= 10_000:
            raise ValueError("タスク一覧が10,000件の取得上限に達したため、全タスクを安全に取得できず処理を中断しました。`--task_id` を指定して対象タスクを絞り込んでください。")
        return [e["task_id"] for e in task_list]

    def change_annotation_attributes_for_task_list(
        self,
        task_id_list: list[str] | None,
        annotation_query: AnnotationQueryForAPI,
        additional_data_list: list[dict[str, Any]],
        *,
        backup_dir: Path | None = None,
        parallelism: int | None = None,
        all_tasks: bool = False,
    ) -> None:
        """
        複数のタスクに対してアノテーションの属性値を変更します。

        Args:
            task_id_list: 変更対象のタスクのIDのlist
            annotation_query: 変更対象のアノテーションを特定するためのクエリー
            additional_data_list: 変更後の属性値(`AdditionalDataListV2`スキーマ)
            backup_dir: バックアップ先のディレクトリ
            parallelism: 並列数
            all_tasks: 全タスクを対象にする場合はTrue。

        Returns:
            None

        """
        task_id_list = self.get_target_task_id_list(task_id_list, all_tasks=all_tasks)
        project_title = self.facade.get_project_title(self.project_id)
        logger.info(f"プロジェクト'{project_title}'に対して、タスク{len(task_id_list)} 件のアノテーションの属性値を変更します。")

        if backup_dir is not None:
            backup_dir.mkdir(exist_ok=True, parents=True)
        func = functools.partial(
            self.change_attributes_for_task_wrapper,
            annotation_query=annotation_query,
            additional_data_list=additional_data_list,
            backup_dir=backup_dir,
        )
        if parallelism is not None:
            with multiprocessing.Pool(parallelism) as pool:
                results = pool.map(func, enumerate(task_id_list))
        else:
            results = [func(item) for item in enumerate(task_id_list)]

        success_count = sum(result.success for result in results)
        failed_count = sum(result.failed for result in results)
        skipped_count = len(results) - success_count - failed_count
        changed_annotation_count = sum(result.changed_count for result in results)
        logger.info(f"{changed_annotation_count} 件のアノテーションの属性値を変更しました。タスク: 成功{success_count}件、スキップ{skipped_count}件、失敗{failed_count}件。")
        if failed_count:
            raise AnnofabCliException(f"{failed_count} 件のタスクのアノテーションの属性値変更に失敗しました。")


class ChangeAttributesOfAnnotation(CommandLine):
    """
    アノテーション属性を変更
    """

    COMMON_MESSAGE = "annofabcli annotation change_attributes: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、'--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    @classmethod
    def get_annotation_query_for_api(cls, str_annotation_query: str, annotation_specs: dict[str, Any]) -> AnnotationQueryForAPI:
        """
        CLIから受け取った`--annotation_query`の値から、APIに渡すクエリー情報を返す。
        """
        dict_annotation_query = get_json_from_args(str_annotation_query)
        annotation_query_for_cli = AnnotationQueryForCLI.from_dict(dict_annotation_query)
        return annotation_query_for_cli.to_query_for_api(annotation_specs)

    @classmethod
    def get_additional_data_list_from_cli_attributes(cls, str_attributes: str, annotation_specs: dict[str, Any], label_id: str | None) -> list[dict[str, Any]]:
        """
        CLIから受け取った`--attributes`の値から、APIに渡す属性情報(`AdditionalDataListV2`)を返します。
        """
        dict_attributes = get_json_from_args(str_attributes)
        return convert_attributes_from_cli_to_additional_data_list_v2(dict_attributes, annotation_specs, label_id=label_id)

    def main(self) -> None:
        args = self.args

        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None

        annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params={"v": "3"})

        try:
            annotation_query = self.get_annotation_query_for_api(args.annotation_query, annotation_specs)
        except ValueError as e:
            print(f"{self.COMMON_MESSAGE} argument '--annotation_query' の値が不正です。 :: {e}", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        try:
            additional_data_list = self.get_additional_data_list_from_cli_attributes(args.attributes, annotation_specs, label_id=annotation_query.label_id)
        except ValueError as e:
            print(f"{self.COMMON_MESSAGE} argument '--attributes' の値が不正です。 :: {e}", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        if args.backup is None:
            print(  # noqa: T201
                "間違えてアノテーションを変更してしまっときに復元できるようにするため、'--backup'でバックアップ用のディレクトリを指定することを推奨します。",
                file=sys.stderr,
            )
            if not args.yes and not annofabcli.common.cli.prompt_yesno("復元用のバックアップディレクトリが指定されていません。処理を続行しますか？"):
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            backup_dir = None
        else:
            backup_dir = Path(args.backup)

        super().require_project_access(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])
        if args.include_complete_task:  # noqa: SIM102
            if not self.facade.contains_any_project_member_role(project_id, [ProjectMemberRole.OWNER]):
                print(  # noqa: T201
                    f"{self.COMMON_MESSAGE} argument --include_complete_task : '--include_complete_task' 引数を利用するにはプロジェクトのオーナーロールを持つユーザーで実行する必要があります。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        main_obj = ChangeAnnotationAttributesMain(self.service, project_id=project_id, include_complete_task=args.include_complete_task, all_yes=args.yes)
        main_obj.change_annotation_attributes_for_task_list(
            task_id_list,
            annotation_query=annotation_query,
            additional_data_list=additional_data_list,
            backup_dir=backup_dir,
            parallelism=args.parallelism,
            all_tasks=args.all_tasks,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeAttributesOfAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id_or_all_tasks()

    EXAMPLE_ANNOTATION_QUERY = {"label": "car", "attributes": {"occluded": True}}  # noqa: N806
    parser.add_argument(
        "-aq",
        "--annotation_query",
        type=str,
        required=True,
        help=f"変更対象のアノテーションを検索する条件をJSON形式で指定します。``file://`` を先頭に付けると、JSON形式のファイルを指定できます。(ex): ``{json.dumps(EXAMPLE_ANNOTATION_QUERY)}``",
    )

    EXAMPLE_ATTRIBUTES = '{"occluded": false}'  # noqa: N806
    parser.add_argument(
        "--attributes",
        type=str,
        required=True,
        help=f"変更後の属性をJSON形式で指定します。``file://`` を先頭に付けると、JSON形式のファイルを指定できます。(ex): ``{EXAMPLE_ATTRIBUTES}``",
    )

    parser.add_argument(
        "--include_complete_task",
        action="store_true",
        help="完了状態のタスクのアノテーション属性も変更します。ただし、オーナーロールを持つユーザーでしか実行できません。",
    )

    parser.add_argument(
        "--backup",
        type=str,
        required=False,
        help="アノテーションのバックアップを保存するディレクトリを指定してください。アノテーションの復元は ``annotation restore`` コマンドで実現できます。",
    )
    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="並列度。指定しない場合は、逐次的に処理します。指定した場合は、``--yes`` も指定してください。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "change_attributes"
    subcommand_help = "アノテーションの属性値を変更します。"
    description = (
        "アノテーションの属性値を一括で変更します。ただし、作業中状態のタスクに含まれるアノテーションは変更できません。"
        "完了状態のタスクに含まれるアノテーションは、デフォルトでは変更できません。"
        "間違えてアノテーション属性値を変更したときに復元できるようにするため、 ``--backup`` でバックアップ用のディレクトリを指定することを推奨します。"
    )
    epilog = "オーナロールまたはチェッカーロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
