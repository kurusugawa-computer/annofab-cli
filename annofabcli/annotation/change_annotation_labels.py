from __future__ import annotations

import argparse
import functools
import json
import logging
import multiprocessing
import sys
from pathlib import Path
from typing import Any

import annofabapi
from annofabapi.dataclass.task import Task
from annofabapi.models import ProjectMemberRole, TaskStatus
from annofabapi.util.annotation_specs import get_english_message

import annofabcli.common.cli
from annofabcli.annotation.annotation_query import AnnotationQueryForAPI, AnnotationQueryForCLI
from annofabcli.annotation.dump_annotation import DumpAnnotationMain
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
    get_json_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


def get_label_id_from_name_or_id(annotation_specs: dict[str, Any], *, label_name: str | None = None, label_id: str | None = None) -> str:
    """変更後ラベルのlabel_idを取得する。

    Args:
        annotation_specs: アノテーション仕様
        label_name: 変更後ラベル名（英語）
        label_id: 変更後ラベルID

    Raises:
        ValueError: ラベルが存在しない、または同名ラベルが複数存在する

    Returns:
        変更後ラベルのlabel_id
    """
    if label_id is not None:
        tmp = [e for e in annotation_specs["labels"] if e["label_id"] == label_id]
        if len(tmp) == 0:
            raise ValueError(f"アノテーション仕様に、label_id='{label_id}'であるラベルは存在しません。")
        return label_id

    assert label_name is not None
    tmp = [e for e in annotation_specs["labels"] if get_english_message(e["label_name"]) == label_name]
    if len(tmp) == 0:
        raise ValueError(f"アノテーション仕様に、ラベル名（英語）が'{label_name}'であるラベルは存在しません。")
    if len(tmp) > 1:
        raise ValueError(f"アノテーション仕様に、ラベル名（英語）が'{label_name}'であるラベルが複数（{len(tmp)} 個）存在します。")
    return tmp[0]["label_id"]


class ChangeAnnotationLabelsMain(CommandLineWithConfirm):
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

    def change_annotation_labels(self, annotation_list: list[dict[str, Any]], dest_label_id: str) -> None:
        """アノテーションのラベルを変更する。

        ラベル変更後のラベルに紐づかない属性が残らないように、属性は空で更新する。

        Args:
            annotation_list: 変更対象のアノテーション一覧
            dest_label_id: 変更後ラベルのlabel_id
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
                    "label_id": dest_label_id,
                    "additional_data_list": annotation["additional_data_list"],
                },
                "_type": "PutV2",
            }

        request_body = [_to_request_body_elm(annotation) for annotation in annotation_list]
        self.service.api.batch_update_annotations(self.project_id, request_body=request_body)

    def get_annotation_list_for_task(self, task_id: str, annotation_query: AnnotationQueryForAPI) -> list[dict[str, Any]]:
        """タスク内のアノテーション一覧を取得する。"""
        dict_query = annotation_query.to_dict()
        dict_query.update({"task_id": task_id, "exact_match_task_id": True})
        annotation_list = self.service.wrapper.get_all_annotation_list(self.project_id, query_params={"query": dict_query})
        return annotation_list

    def change_labels_for_task(
        self,
        task_id: str,
        annotation_query: AnnotationQueryForAPI,
        dest_label_id: str,
        *,
        backup_dir: Path | None = None,
        task_index: int | None = None,
    ) -> tuple[bool, int]:
        """タスクに対してアノテーションのラベルを変更する。"""
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
                logger.warning(f"task_id='{task_id}': タスクが完了状態のため、スキップします。完了状態のタスクのアノテーションラベルを変更するには、 ``--include_complete_task`` を指定してください。")
                return False, 0

        annotation_list = self.get_annotation_list_for_task(task_id, annotation_query)
        target_annotation_list = [e for e in annotation_list if e["detail"]["label_id"] != dest_label_id]

        logger.info(
            f"{logger_prefix}task_id='{task_id}'の検索ヒット件数は{len(annotation_list)}個、"
            f"実際の変更対象アノテーション数は{len(target_annotation_list)}個です。"
            f" :: task_phase='{task.phase.value}', task_status='{task.status.value}', task_updated_datetime='{task.updated_datetime}'"
        )
        if len(target_annotation_list) == 0:
            logger.info(f"{logger_prefix}task_id='{task_id}'には変更対象のアノテーションが存在しないので、スキップします。")
            return False, 0

        if not self.confirm_processing(f"task_id='{task_id}' のアノテーションラベルを変更しますか？"):
            return False, 0

        if backup_dir is not None:
            self.dump_annotation_obj.dump_annotation_for_task(task_id, output_dir=backup_dir)

        self.change_annotation_labels(target_annotation_list, dest_label_id)
        logger.info(f"{logger_prefix}task_id='{task_id}': {len(target_annotation_list)} 個のアノテーションのラベルを変更しました。")
        return True, len(target_annotation_list)

    def change_labels_for_task_wrapper(
        self,
        tpl: tuple[int, str],
        annotation_query: AnnotationQueryForAPI,
        dest_label_id: str,
        *,
        backup_dir: Path | None = None,
    ) -> tuple[bool, int]:
        task_index, task_id = tpl
        try:
            return self.change_labels_for_task(
                task_id,
                annotation_query=annotation_query,
                dest_label_id=dest_label_id,
                backup_dir=backup_dir,
                task_index=task_index,
            )
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"タスク'{task_id}'のアノテーションラベルの変更に失敗しました。", exc_info=True)
            return False, 0

    def get_target_task_id_list(self, task_id_list: list[str] | None) -> list[str]:
        """処理対象のタスクID一覧を取得する。"""
        if task_id_list is not None:
            return task_id_list

        task_list = self.service.wrapper.get_all_tasks(self.project_id)
        if len(task_list) == 10_000:
            logger.warning("タスク一覧は10,000件で打ち切られている可能性があります。")
        return [e["task_id"] for e in task_list]

    def change_annotation_labels_for_task_list(
        self,
        task_id_list: list[str] | None,
        annotation_query: AnnotationQueryForAPI,
        dest_label_id: str,
        *,
        backup_dir: Path | None = None,
        parallelism: int | None = None,
    ) -> None:
        """複数タスクに対してアノテーションのラベルを変更する。"""
        actual_task_id_list = self.get_target_task_id_list(task_id_list)
        project_title = self.facade.get_project_title(self.project_id)
        logger.info(f"プロジェクト'{project_title}'に対して、タスク{len(actual_task_id_list)} 件のアノテーションラベルを変更します。")

        if backup_dir is not None:
            backup_dir.mkdir(exist_ok=True, parents=True)

        success_count = 0
        changed_annotation_count = 0
        if parallelism is not None:
            func = functools.partial(
                self.change_labels_for_task_wrapper,
                annotation_query=annotation_query,
                dest_label_id=dest_label_id,
                backup_dir=backup_dir,
            )
            with multiprocessing.Pool(parallelism) as pool:
                result_tuple_list = pool.map(func, enumerate(actual_task_id_list))
                success_count = len([e for e in result_tuple_list if e[0]])
                changed_annotation_count = sum(e[1] for e in result_tuple_list)

        else:
            for task_index, task_id in enumerate(actual_task_id_list):
                try:
                    result, sub_changed_annotation_count = self.change_labels_for_task(
                        task_id,
                        annotation_query=annotation_query,
                        dest_label_id=dest_label_id,
                        backup_dir=backup_dir,
                        task_index=task_index,
                    )
                    changed_annotation_count += sub_changed_annotation_count
                    if result:
                        success_count += 1
                except Exception:
                    logger.warning(f"タスク'{task_id}'のアノテーションラベルの変更に失敗しました。", exc_info=True)
                    continue

        logger.info(f"{success_count} / {len(actual_task_id_list)} 件のタスクに対して {changed_annotation_count} 件のアノテーションラベルを変更しました。")


class ChangeLabelsOfAnnotation(CommandLine):
    """アノテーションラベルを変更"""

    COMMON_MESSAGE = "annofabcli annotation change_labels: error:"

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
        """CLIから受け取った`--annotation_query`の値から、APIに渡すクエリー情報を返す。"""
        dict_annotation_query = get_json_from_args(str_annotation_query)
        annotation_query_for_cli = AnnotationQueryForCLI.from_dict(dict_annotation_query)
        return annotation_query_for_cli.to_query_for_api(annotation_specs)

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
            dest_label_id = get_label_id_from_name_or_id(annotation_specs, label_name=args.label_name, label_id=args.label_id)
        except ValueError as e:
            option_name = "--label_id" if args.label_id is not None else "--label_name"
            print(f"{self.COMMON_MESSAGE} argument '{option_name}' の値が不正です。 :: {e}", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        if args.backup is None:
            print(  # noqa: T201
                "間違えてアノテーションを変更してしまっときに復元できるようにするため、'--backup'でバックアップ用のディレクトリを指定することを推奨します。",
                file=sys.stderr,
            )
            if not self.confirm_processing("復元用のバックアップディレクトリが指定されていません。処理を続行しますか？"):
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            backup_dir = None
        else:
            backup_dir = Path(args.backup)

        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER])
        if args.include_complete_task:  # noqa: SIM102
            if not self.facade.contains_any_project_member_role(project_id, [ProjectMemberRole.OWNER]):
                print(  # noqa: T201
                    f"{self.COMMON_MESSAGE} argument --include_complete_task : '--include_complete_task' 引数を利用するにはプロジェクトのオーナーロールを持つユーザーで実行する必要があります。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        main_obj = ChangeAnnotationLabelsMain(self.service, project_id=project_id, include_complete_task=args.include_complete_task, all_yes=args.yes)
        main_obj.change_annotation_labels_for_task_list(
            task_id_list,
            annotation_query=annotation_query,
            dest_label_id=dest_label_id,
            backup_dir=backup_dir,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeLabelsOfAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id(required=False)

    example_annotation_query = {"label": "car"}
    parser.add_argument(
        "-aq",
        "--annotation_query",
        type=str,
        required=True,
        help=f"変更対象のアノテーションを検索する条件をJSON形式で指定します。``file://`` を先頭に付けると、JSON形式のファイルを指定できます。(ex): ``{json.dumps(example_annotation_query)}``",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--label_name",
        type=str,
        help="変更後のラベル名（英語）を指定します。",
    )
    group.add_argument(
        "--label_id",
        type=str,
        help="変更後のラベルIDを指定します。",
    )

    parser.add_argument(
        "--include_complete_task",
        action="store_true",
        help="完了状態のタスクのアノテーションラベルも変更します。ただし、オーナーロールを持つユーザーでしか実行できません。",
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
    subcommand_name = "change_labels"
    subcommand_help = "アノテーションのラベルを変更します。"
    description = (
        "アノテーションのラベルを一括で変更します。"
        "ラベル変更後のラベルに存在しない属性との不整合を避けるため、変更対象アノテーションの属性は削除されます。"
        "ただし、作業中状態のタスクに含まれるアノテーションは変更できません。"
        "完了状態のタスクに含まれるアノテーションは、デフォルトでは変更できません。"
        "間違えてアノテーションラベルを変更したときに復元できるようにするため、 ``--backup`` でバックアップ用のディレクトリを指定することを推奨します。"
    )
    epilog = "オーナロールまたはチェッカーロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
