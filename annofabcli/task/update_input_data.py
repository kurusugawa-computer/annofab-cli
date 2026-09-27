from __future__ import annotations

import argparse
import enum
import functools
import logging
import multiprocessing
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import annofabapi
import pandas
from annofabapi.models import ProjectMemberRole, Task

import annofabcli.common.cli
from annofabcli.common.annofab.input_data import BULK_REQUEST_SIZE
from annofabcli.common.annofab.task import MAX_INPUT_DATA_COUNT, get_task_dict_in_bulk
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
from annofabcli.utils.iterables import batched

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskInputDataUpdateInfo:
    """タスクの入力データ更新情報。"""

    task_id: str
    """更新対象のタスクID。"""

    input_data_id_list: list[str]
    """更新後の入力データID。リストの並びがフレーム順を表す。"""


@dataclass(frozen=True)
class TaskInputDataDiff:
    """タスクに割り当てられた入力データの差分。"""

    added_input_data_id_list: list[str]
    """追加される入力データID。"""

    removed_input_data_id_list: list[str]
    """削除される入力データID。"""

    order_changed: bool
    """既存の入力データ同士の順序が変わる場合はTrue。"""

    @property
    def has_change(self) -> bool:
        """差分が存在するか判定する。

        Returns:
            差分が存在する場合はTrue。
        """

        return len(self.added_input_data_id_list) > 0 or len(self.removed_input_data_id_list) > 0 or self.order_changed


class UpdateResult(Enum):
    """タスクの入力データ更新結果。"""

    UPDATED = enum.auto()
    """更新した。"""

    UNCHANGED = enum.auto()
    """差分がなかった。"""

    NOT_FOUND = enum.auto()
    """更新対象のタスクが存在しなかった。"""

    REMOVAL_NOT_ALLOWED = enum.auto()
    """入力データの削除が許可されていなかった。"""

    CANCELLED = enum.auto()
    """ユーザーが更新をキャンセルした。"""

    FAILED = enum.auto()
    """更新に失敗した。"""


def calculate_task_input_data_diff(old_input_data_id_list: list[str], new_input_data_id_list: list[str]) -> TaskInputDataDiff:
    """タスクに割り当てられた入力データの差分を算出する。

    Args:
        old_input_data_id_list: 更新前の入力データID。
        new_input_data_id_list: 更新後の入力データID。

    Returns:
        入力データの追加、削除、順序変更を表す差分。
    """

    old_input_data_id_set = set(old_input_data_id_list)
    new_input_data_id_set = set(new_input_data_id_list)
    old_retained_input_data_id_list = [input_data_id for input_data_id in old_input_data_id_list if input_data_id in new_input_data_id_set]
    new_retained_input_data_id_list = [input_data_id for input_data_id in new_input_data_id_list if input_data_id in old_input_data_id_set]

    return TaskInputDataDiff(
        added_input_data_id_list=[input_data_id for input_data_id in new_input_data_id_list if input_data_id not in old_input_data_id_set],
        removed_input_data_id_list=[input_data_id for input_data_id in old_input_data_id_list if input_data_id not in new_input_data_id_set],
        order_changed=old_retained_input_data_id_list != new_retained_input_data_id_list,
    )


def validate_input_data_id_list(input_data_id_list: list[str], *, index: int) -> None:
    """入力データIDのリストを検証する。

    Args:
        input_data_id_list: 検証対象の入力データID。
        index: エラーメッセージに表示するタスクの位置。1始まり。

    Raises:
        ValueError: 入力データIDが重複している、または最大数を超えている場合。
    """

    if len(input_data_id_list) != len(set(input_data_id_list)):
        raise ValueError(f"{index}番目のタスクに重複したinput_data_idが含まれています。")
    if len(input_data_id_list) > MAX_INPUT_DATA_COUNT:
        raise ValueError(f"{index}番目のタスクに指定できるinput_data_idは最大{MAX_INPUT_DATA_COUNT}件です。")


def get_task_input_data_update_info_list_from_csv(csv_file: Path) -> list[TaskInputDataUpdateInfo]:
    """CSVからタスクの入力データ更新情報を取得する。

    Args:
        csv_file: ``task_id`` 列と ``input_data_id`` 列を持つCSVファイル。

    Returns:
        CSVの行順を入力データの順序として保持した更新情報。

    Raises:
        ValueError: CSVの形式または値が不正な場合。
    """

    df = pandas.read_csv(csv_file, dtype="string")
    if "task_id" not in df.columns or "input_data_id" not in df.columns:
        raise ValueError("CSV形式が不正です。ヘッダ行に 'task_id' と 'input_data_id' を指定してください。")
    if df[["task_id", "input_data_id"]].isna().any().any():
        raise ValueError("CSV形式が不正です。'task_id' または 'input_data_id' に欠損値を指定できません。")

    input_data_id_list_by_task_id: dict[str, list[str]] = defaultdict(list)
    for task_id, input_data_id in zip(df["task_id"], df["input_data_id"], strict=False):
        input_data_id_list_by_task_id[str(task_id)].append(str(input_data_id))

    result: list[TaskInputDataUpdateInfo] = []
    for index, (task_id, input_data_id_list) in enumerate(input_data_id_list_by_task_id.items(), start=1):
        validate_input_data_id_list(input_data_id_list, index=index)
        result.append(TaskInputDataUpdateInfo(task_id=task_id, input_data_id_list=input_data_id_list))
    return result


def get_task_input_data_update_info_list_from_json(json_value: str) -> list[TaskInputDataUpdateInfo]:
    """JSONからタスクの入力データ更新情報を取得する。

    Args:
        json_value: JSON文字列、またはJSONファイルのパス。

    Returns:
        タスクの入力データ更新情報。

    Raises:
        TypeError: JSONの形式が不正な場合。
        ValueError: task_idまたはinput_data_idが重複している場合。
    """

    task_list = get_json_from_args(json_value)
    if not isinstance(task_list, list):
        raise TypeError("配列を指定してください。")

    result: list[TaskInputDataUpdateInfo] = []
    task_id_set: set[str] = set()
    for index, task in enumerate(task_list, start=1):
        if not isinstance(task, dict):
            raise TypeError(f"{index}番目の要素にはオブジェクトを指定してください。")
        try:
            task_id = task["task_id"]
            input_data_id_list = task["input_data_id_list"]
        except KeyError as e:
            raise TypeError(f"{index}番目の要素には 'task_id' と 'input_data_id_list' キーを指定してください。") from e

        if not isinstance(task_id, str):
            raise TypeError(f"{index}番目の要素の'task_id'には文字列を指定してください。")
        if not isinstance(input_data_id_list, list) or not all(isinstance(input_data_id, str) for input_data_id in input_data_id_list):
            raise TypeError(f"{index}番目の要素の'input_data_id_list'には文字列の配列を指定してください。")
        if task_id in task_id_set:
            raise ValueError(f"{index}番目の要素の'task_id'が重複しています。 :: task_id='{task_id}'")

        validate_input_data_id_list(input_data_id_list, index=index)
        task_id_set.add(task_id)
        result.append(TaskInputDataUpdateInfo(task_id=task_id, input_data_id_list=input_data_id_list))

    return result


class UpdateTaskInputDataMain(CommandLineWithConfirm):
    """タスクに割り当てられた入力データを更新する。"""

    PROGRESS_LOG_INTERVAL = 100
    """進捗ログを出力する間隔。"""

    def __init__(
        self,
        service: annofabapi.Resource,
        project_id: str,
        *,
        allow_removing_input_data: bool = False,
        parallelism: int | None = None,
        all_yes: bool = False,
    ) -> None:
        """更新処理を初期化する。

        Args:
            service: Annofab APIにアクセスするためのResource。
            project_id: 更新対象のプロジェクトID。
            allow_removing_input_data: タスクから入力データを削除してよい場合はTrue。
            parallelism: 更新時の並列度。Noneの場合は逐次処理する。
            all_yes: 確認メッセージへの応答を省略する場合はTrue。
        """

        super().__init__(all_yes)
        self.service = service
        self.project_id = project_id
        self.allow_removing_input_data = allow_removing_input_data
        self.parallelism = parallelism

    def update_task_input_data(
        self,
        update_info: TaskInputDataUpdateInfo,
        *,
        existing_task_dict: dict[str, Task] | None = None,
    ) -> UpdateResult:
        """1個のタスクに割り当てられた入力データを更新する。

        Args:
            update_info: タスクの入力データ更新情報。
            existing_task_dict: task_idをキーにした既存タスク。未指定の場合はAPIから取得する。

        Returns:
            更新結果。
        """

        task = existing_task_dict.get(update_info.task_id) if existing_task_dict is not None else self.service.wrapper.get_task_or_none(self.project_id, update_info.task_id)
        if task is None:
            logger.warning(f"task_id='{update_info.task_id}' :: タスクが存在しないため、更新をスキップします。")
            return UpdateResult.NOT_FOUND

        old_input_data_id_list = task["input_data_id_list"]
        diff = calculate_task_input_data_diff(old_input_data_id_list, update_info.input_data_id_list)
        if not diff.has_change:
            logger.debug(f"task_id='{update_info.task_id}' :: 入力データと順序に変更はありません。")
            return UpdateResult.UNCHANGED

        diff_message = (
            f"追加: {len(diff.added_input_data_id_list)}件 {diff.added_input_data_id_list}, "
            f"削除: {len(diff.removed_input_data_id_list)}件 {diff.removed_input_data_id_list}, "
            f"順序変更: {'あり' if diff.order_changed else 'なし'}"
        )
        logger.info(f"task_id='{update_info.task_id}' :: {diff_message}")

        if len(diff.removed_input_data_id_list) > 0 and not self.allow_removing_input_data:
            logger.warning(f"task_id='{update_info.task_id}' :: タスクから入力データが削除されるため、更新をスキップします。更新するには '--allow_removing_input_data' を指定してください。")
            return UpdateResult.REMOVAL_NOT_ALLOWED

        confirm_message = f"task_id='{update_info.task_id}' :: タスクの入力データを更新しますか？ :: {diff_message}"
        if len(diff.removed_input_data_id_list) > 0:
            confirm_message += " 削除対象の入力データに紐づくアノテーションが削除される可能性があります。"
        if not self.confirm_processing(confirm_message):
            return UpdateResult.CANCELLED

        request_body: dict[str, object] = {
            "input_data_id_list": update_info.input_data_id_list,
            "metadata": task.get("metadata", {}),
        }
        self.service.api.put_task(self.project_id, update_info.task_id, request_body=request_body)
        logger.debug(f"task_id='{update_info.task_id}' :: タスクの入力データを更新しました。")
        return UpdateResult.UPDATED

    def update_task_input_data_wrapper(
        self,
        indexed_update_info: tuple[int, TaskInputDataUpdateInfo],
        *,
        existing_task_dict: dict[str, Task],
    ) -> UpdateResult:
        """例外を捕捉しながらタスクの入力データを更新する。

        Args:
            indexed_update_info: 処理位置と更新情報。
            existing_task_dict: task_idをキーにした既存タスク。

        Returns:
            更新結果。例外が発生した場合はFAILED。
        """

        index, update_info = indexed_update_info
        try:
            return self.update_task_input_data(update_info, existing_task_dict=existing_task_dict)
        except Exception:
            logger.warning(f"{index}件目 :: task_id='{update_info.task_id}'の入力データ更新に失敗しました。", exc_info=True)
            return UpdateResult.FAILED

    def log_progress(self, processed_count: int, total_count: int) -> None:
        """一定件数ごとに進捗を出力する。

        Args:
            processed_count: 処理済み件数。
            total_count: 全件数。
        """

        if processed_count % self.PROGRESS_LOG_INTERVAL == 0 or processed_count == total_count:
            logger.info(f"{processed_count} / {total_count} 件のタスクを処理しました。")

    def update_task_input_data_list(self, update_info_list: list[TaskInputDataUpdateInfo]) -> Counter[UpdateResult]:
        """複数タスクに割り当てられた入力データを更新する。

        Args:
            update_info_list: タスクの入力データ更新情報。

        Returns:
            更新結果ごとの件数。
        """

        result_counter: Counter[UpdateResult] = Counter()
        total_count = len(update_info_list)
        logger.info(f"{total_count} 件のタスクの入力データを更新します。")

        if self.parallelism is not None:
            with multiprocessing.Pool(self.parallelism) as pool:
                for initial_index, update_info_batch in enumerate(batched(update_info_list, BULK_REQUEST_SIZE)):
                    existing_task_dict = get_task_dict_in_bulk(self.service, self.project_id, [info.task_id for info in update_info_batch])
                    wrapper = functools.partial(self.update_task_input_data_wrapper, existing_task_dict=existing_task_dict)
                    indexed_update_info_list = list(enumerate(update_info_batch, start=initial_index * BULK_REQUEST_SIZE + 1))
                    for index, result in zip(
                        range(initial_index * BULK_REQUEST_SIZE + 1, initial_index * BULK_REQUEST_SIZE + len(update_info_batch) + 1),
                        pool.imap(wrapper, indexed_update_info_list),
                        strict=True,
                    ):
                        result_counter[result] += 1
                        self.log_progress(index, total_count)
        else:
            for initial_index, update_info_batch in enumerate(batched(update_info_list, BULK_REQUEST_SIZE)):
                existing_task_dict = get_task_dict_in_bulk(self.service, self.project_id, [info.task_id for info in update_info_batch])
                for index, update_info in enumerate(update_info_batch, start=initial_index * BULK_REQUEST_SIZE + 1):
                    result = self.update_task_input_data_wrapper((index, update_info), existing_task_dict=existing_task_dict)
                    result_counter[result] += 1
                    self.log_progress(index, total_count)

        logger.info(
            f"{result_counter[UpdateResult.UPDATED]} / {total_count} 件のタスクを更新しました。"
            f"（更新: {result_counter[UpdateResult.UPDATED]}件, 変更なし: {result_counter[UpdateResult.UNCHANGED]}件, "
            f"不存在: {result_counter[UpdateResult.NOT_FOUND]}件, "
            f"削除未許可: {result_counter[UpdateResult.REMOVAL_NOT_ALLOWED]}件, キャンセル: {result_counter[UpdateResult.CANCELLED]}件, "
            f"失敗: {result_counter[UpdateResult.FAILED]}件）"
        )
        return result_counter


class UpdateTaskInputData(CommandLine):
    """タスクに割り当てられた入力データを更新するコマンド。"""

    COMMON_MESSAGE = "annofabcli task update_input_data: error:"
    """コマンドライン引数エラーの共通メッセージ。"""

    @classmethod
    def validate(cls, args: argparse.Namespace) -> bool:
        """コマンドライン引数の組み合わせを検証する。

        Args:
            args: コマンドライン引数。

        Returns:
            引数が正しい場合はTrue。
        """

        if args.parallelism is not None and not args.yes:
            print(f"{cls.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、'--yes'を指定してください。", file=sys.stderr)  # noqa: T201
            return False
        if args.parallelism is not None and args.allow_removing_input_data:
            print(  # noqa: T201
                f"{cls.COMMON_MESSAGE} argument --parallelism: '--allow_removing_input_data'と同時に指定できません。",
                file=sys.stderr,
            )
            return False
        return True

    def main(self) -> None:
        """コマンドのメイン処理を実行する。"""

        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        try:
            if args.csv is not None:
                update_info_list = get_task_input_data_update_info_list_from_csv(args.csv)
            else:
                update_info_list = get_task_input_data_update_info_list_from_json(args.json)
        except (TypeError, ValueError) as e:
            print(f"{self.COMMON_MESSAGE} {e}", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        super().validate_project(args.project_id, [ProjectMemberRole.OWNER])
        main_obj = UpdateTaskInputDataMain(
            self.service,
            args.project_id,
            allow_removing_input_data=args.allow_removing_input_data,
            parallelism=args.parallelism,
            all_yes=args.yes,
        )
        main_obj.update_task_input_data_list(update_info_list)


def main(args: argparse.Namespace) -> None:
    """Annofabにログインしてコマンドを実行する。

    Args:
        args: コマンドライン引数。
    """

    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateTaskInputData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    """コマンドライン引数を追加する。

    Args:
        parser: コマンドライン引数を追加するArgumentParser。
    """

    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--csv",
        type=Path,
        help=(
            "更新後のタスクと入力データの関係が記載されたCSVファイルを指定してください。"
            "CSVの行順がタスク内の入力データの順序になります。\n\n"
            " * ヘッダ行あり, カンマ区切り\n"
            " * 必須列: task_id, input_data_id\n"
        ),
    )
    source_group.add_argument(
        "--json",
        type=str,
        help=(
            "更新後のタスクと入力データの関係をJSON形式で指定してください。"
            "各要素の ``task_id`` と ``input_data_id_list`` キーを参照し、それ以外のキーは無視します。\n"
            '(ex) ``[{"task_id":"task1","input_data_id_list":["input1","input2"]}]``\n'
            "``file://`` を先頭に付けるとJSONファイルを指定できます。"
        ),
    )
    parser.add_argument(
        "--allow_removing_input_data",
        action="store_true",
        help="タスクから入力データが削除される更新を許可します。削除対象の入力データに紐づくアノテーションが削除される可能性があります。",
    )
    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="並列度。指定する場合は ``--yes`` も指定してください。 ``--allow_removing_input_data`` とは同時に指定できません。",
    )
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """サブコマンドを追加する。

    Args:
        subparsers: サブコマンドの追加先。Noneの場合は新しいArgumentParserを作成する。

    Returns:
        コマンド用のArgumentParser。
    """

    subcommand_name = "update_input_data"
    subcommand_help = "タスクに割り当てられた入力データと順序を更新します。"
    description = "既存タスクに割り当てられた入力データと順序を更新します。タスクは新規作成しません。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
