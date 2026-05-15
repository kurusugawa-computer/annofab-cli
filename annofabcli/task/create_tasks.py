from __future__ import annotations

import argparse
import logging
import multiprocessing
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import annofabapi
import pandas
from annofabapi.models import ProjectMemberRole
from annofabapi.project_member_repository import ProjectMemberRepository

import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    get_list_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)

Metadata = dict[str, object]
"""タスクのメタデータを表現する型"""


@dataclass(frozen=True)
class TaskCreationInfo:
    """タスク作成時に指定する情報"""

    task_id: str
    """作成するタスクのID"""

    input_data_id_list: list[str]
    """タスクに紐づける入力データのIDのlist"""

    metadata: Metadata
    """タスクに付与するメタデータ"""

    user_id: str | None = None
    """タスクの担当者にするユーザーのuser_id。指定しない場合は担当者を設定しない。"""


def get_task_creation_info_list_from_csv(
    csv_file: Path,
    *,
    common_metadata: Metadata | None = None,
    common_user_id: str | None = None,
) -> list[TaskCreationInfo]:
    """ヘッダ行ありCSVから、タスク作成情報のlistを取得します。"""

    # `dtype=str`を指定した理由：指定しないと、IDが`001`のときに`1`に変換されてしまうため
    df = pandas.read_csv(str(csv_file), dtype=str)
    if "task_id" not in df.columns or "input_data_id" not in df.columns:
        raise ValueError("CSV形式が不正です。ヘッダ行に 'task_id' と 'input_data_id' を指定してください。")

    task_relation_dict: dict[str, list[str]] = defaultdict(list)
    for task_id, input_data_id in zip(df["task_id"], df["input_data_id"], strict=False):
        task_relation_dict[task_id].append(input_data_id)

    common_metadata = common_metadata or {}
    return [
        TaskCreationInfo(
            task_id=task_id,
            input_data_id_list=input_data_id_list,
            metadata=common_metadata,
            user_id=common_user_id,
        )
        for task_id, input_data_id_list in task_relation_dict.items()
    ]


def get_metadata_from_json_args(metadata_value: str | None) -> Metadata:
    """JSON引数から、全タスク共通のメタデータを取得します。

    Args:
        metadata_value: メタデータを表すJSON文字列、またはJSONファイルのパス

    Returns:
        全タスク共通のメタデータ
    """

    if metadata_value is None:
        return {}

    return get_json_from_args(metadata_value)


def get_task_creation_info_list_from_input_data_id_as_task_id_args(
    input_data_id_value: list[str],
    *,
    common_metadata: Metadata | None = None,
    common_user_id: str | None = None,
) -> list[TaskCreationInfo]:
    """input_data_idのlistから、task_idがinput_data_idと同じタスク作成情報のlistを取得します。

    Args:
        input_data_id_value: コマンドライン引数で指定されたinput_data_idのlist
        common_metadata: 全タスク共通のメタデータ
        common_user_id: 全タスク共通の担当者のuser_id

    Returns:
        タスク作成情報のlist
    """

    input_data_id_list = get_list_from_args(input_data_id_value)
    common_metadata = common_metadata or {}
    result: list[TaskCreationInfo] = []
    task_id_set: set[str] = set()
    for index, input_data_id in enumerate(input_data_id_list, start=1):
        if input_data_id in task_id_set:
            raise ValueError(f"{index}番目のinput_data_idが重複しています。 :: input_data_id='{input_data_id}'")

        task_id_set.add(input_data_id)
        result.append(
            TaskCreationInfo(
                task_id=input_data_id,
                input_data_id_list=[input_data_id],
                metadata=common_metadata,
                user_id=common_user_id,
            )
        )

    return result


def get_task_creation_info_list_from_json_args(
    json_value: str,
    *,
    common_metadata: Metadata | None = None,
    common_user_id: str | None = None,
) -> list[TaskCreationInfo]:
    """JSON引数からタスク作成情報のlistを取得します。

    Args:
        json_value: `task list --format json` と同じ形式のJSON文字列、またはJSONファイルのパス
        common_metadata: 全タスク共通のメタデータ
        common_user_id: 全タスク共通の担当者のuser_id

    Returns:
        タスク作成情報のlist
    """

    task_list = get_json_from_args(json_value)
    if not isinstance(task_list, list):
        raise TypeError("配列を指定してください。")

    common_metadata = common_metadata or {}
    result: list[TaskCreationInfo] = []
    task_id_set: set[str] = set()
    for index, task in enumerate(task_list):
        if not isinstance(task, dict):
            raise TypeError(f"{index + 1}番目の要素にはオブジェクトを指定してください。")

        try:
            task_id = task["task_id"]
            input_data_id_list = task["input_data_id_list"]
        except KeyError as e:
            raise TypeError(f"{index + 1}番目の要素には 'task_id' と 'input_data_id_list' キーを指定してください。") from e

        if not isinstance(task_id, str):
            raise TypeError(f"{index + 1}番目の要素の'task_id'には文字列を指定してください。")
        if not isinstance(input_data_id_list, list) or not all(isinstance(input_data_id, str) for input_data_id in input_data_id_list):
            raise TypeError(f"{index + 1}番目の要素の'input_data_id_list'には文字列の配列を指定してください。")

        task_metadata = task.get("metadata", {})
        if not isinstance(task_metadata, dict):
            raise TypeError(f"{index + 1}番目の要素の'metadata'にはオブジェクトを指定してください。")
        metadata = {
            **common_metadata,
            **task_metadata,
        }
        json_user_id = task.get("user_id")
        if json_user_id is not None and not isinstance(json_user_id, str):
            raise TypeError(f"{index + 1}番目の要素の'user_id'には文字列を指定してください。")
        task_user_id = json_user_id or common_user_id

        if task_id in task_id_set:
            raise ValueError(f"{index + 1}番目の要素の'task_id'が重複しています。 :: task_id='{task_id}'")

        task_id_set.add(task_id)
        result.append(TaskCreationInfo(task_id=task_id, input_data_id_list=input_data_id_list, metadata=metadata, user_id=task_user_id))

    return result


class CreateTaskMain(CommandLineWithConfirm):
    PROGRESS_LOG_INTERVAL = 100
    """進捗ログを出力する間隔"""

    def __init__(
        self,
        service: annofabapi.Resource,
        project_id: str,
        *,
        parallelism: int | None,
        all_yes: bool = False,
    ) -> None:
        """タスク作成処理を初期化します。

        Args:
            service: Annofab APIにアクセスするためのResource
            project_id: タスクを作成するプロジェクトのproject_id
            parallelism: タスク作成時の並列度。Noneの場合は逐次処理します。
            all_yes: 確認メッセージへの応答を省略する場合はTrue
        """

        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.project_id = project_id
        self.parallelism = parallelism
        self.project_member_repository = ProjectMemberRepository(service)
        self.account_id_cache: dict[str, str] = {}
        CommandLineWithConfirm.__init__(self, all_yes)

    def create_task(self, task_creation_info: TaskCreationInfo) -> bool:
        """タスクを作成し、必要に応じて担当者を設定します。

        Args:
            task_creation_info: タスク作成時に指定する情報

        Returns:
            タスクを作成した場合はTrue、すでにタスクが存在する場合はFalse
        """

        task = self.service.wrapper.get_task_or_none(self.project_id, task_creation_info.task_id)
        if task is not None:
            logger.warning(f"タスク'{task_creation_info.task_id}'はすでに存在するので、タスクの作成をスキップします。")
            return False

        request_body: dict[str, Any] = {"input_data_id_list": task_creation_info.input_data_id_list}
        if len(task_creation_info.metadata) > 0:
            request_body["metadata"] = task_creation_info.metadata
        self.service.api.put_task(self.project_id, task_creation_info.task_id, request_body=request_body)

        if task_creation_info.user_id is not None:
            account_id = self.project_member_repository.get_account_id_from_user_id(self.project_id, task_creation_info.user_id)
            self.service.wrapper.change_task_operator(self.project_id, task_creation_info.task_id, operator_account_id=account_id)

        logger.debug(f"タスク'{task_creation_info.task_id}'を登録しました。")
        return True

    def create_task_wrapper(self, task_creation_info: TaskCreationInfo) -> bool:
        """例外を捕捉しながらタスクを作成します。

        Args:
            task_creation_info: タスク作成時に指定する情報

        Returns:
            タスクを作成できた場合はTrue、作成できなかった場合はFalse
        """

        try:
            return self.create_task(task_creation_info)
        except Exception:
            logger.exception(f"タスク'{task_creation_info.task_id}'の登録に失敗しました。")
            return False

    def log_progress(self, processed_count: int, total_count: int) -> None:
        """一定件数ごとに進捗ログを出力します。"""

        if processed_count % self.PROGRESS_LOG_INTERVAL == 0 or processed_count == total_count:
            logger.info(f"{processed_count} / {total_count} 件のタスク作成が完了しました。")

    def create_task_list(self, task_creation_info_list: list[TaskCreationInfo]) -> None:
        """タスク作成情報のlistをもとに複数のタスクを作成します。

        Args:
            task_creation_info_list: タスク作成時に指定する情報のlist
        """

        if not self.confirm_processing(f"project_id='{self.project_id}' に {len(task_creation_info_list)} 件のタスクを作成します。よろしいですか？"):
            logger.info("タスクの作成をキャンセルしました。")
            return

        success_count = 0
        total_count = len(task_creation_info_list)
        if self.parallelism is None:
            for index, task_creation_info in enumerate(task_creation_info_list, start=1):
                try:
                    result = self.create_task(task_creation_info)
                    if result:
                        success_count += 1
                except Exception:
                    logger.exception(f"タスク'{task_creation_info.task_id}'の登録に失敗しました。")
                finally:
                    self.log_progress(index, total_count)

        else:
            with multiprocessing.Pool(self.parallelism) as p:
                for index, result in enumerate(p.imap(self.create_task_wrapper, task_creation_info_list), start=1):
                    if result:
                        success_count += 1
                    self.log_progress(index, total_count)

        logger.info(f"{success_count} / {total_count} 件のタスクを登録しました。")


class CreateTask(CommandLine):
    COMMON_MESSAGE = "annofabcli task create: error:"

    @classmethod
    def validate(cls, args: argparse.Namespace) -> bool:
        """コマンドライン引数の組み合わせを検証します。

        Args:
            args: コマンドライン引数

        Returns:
            引数が正しい場合はTrue、正しくない場合はFalse
        """

        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{cls.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、'--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        """タスク作成コマンドのメイン処理を実行します。"""

        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        common_metadata = get_metadata_from_json_args(args.metadata)
        main_obj = CreateTaskMain(
            self.service,
            project_id=args.project_id,
            parallelism=args.parallelism,
            all_yes=args.yes,
        )

        if args.csv is not None:
            try:
                task_creation_info_list_from_csv = get_task_creation_info_list_from_csv(args.csv, common_metadata=common_metadata, common_user_id=args.user_id)
            except ValueError as e:
                print(f"{self.COMMON_MESSAGE} argument --csv: {e}", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            main_obj.create_task_list(task_creation_info_list_from_csv)

        elif args.input_data_id_as_task_id is not None:
            try:
                task_creation_info_list_from_input_data_id = get_task_creation_info_list_from_input_data_id_as_task_id_args(
                    args.input_data_id_as_task_id, common_metadata=common_metadata, common_user_id=args.user_id
                )
            except ValueError as e:
                print(f"{self.COMMON_MESSAGE} argument --input_data_id_as_task_id: {e}", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            main_obj.create_task_list(task_creation_info_list_from_input_data_id)

        elif args.json is not None:
            task_creation_info_list_from_json = get_task_creation_info_list_from_json_args(args.json, common_metadata=common_metadata, common_user_id=args.user_id)
            main_obj.create_task_list(task_creation_info_list_from_json)


def main(args: argparse.Namespace) -> None:
    """Annofabにログインして、タスク作成コマンドを実行します。

    Args:
        args: コマンドライン引数
    """

    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CreateTask(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    """タスク作成コマンドのコマンドライン引数を追加します。

    Args:
        parser: コマンドライン引数を追加するArgumentParser
    """

    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    file_group = parser.add_mutually_exclusive_group(required=True)
    file_group.add_argument(
        "--csv",
        type=Path,
        help=(
            "タスクに割り当てる入力データが記載されたCSVファイルのパスを指定してください。CSVのフォーマットは、以下の通りです。\n\n * ヘッダ行あり, カンマ区切り\n * 必須列: task_id, input_data_id\n"
        ),
    )

    file_group.add_argument(
        "--input_data_id_as_task_id",
        type=str,
        nargs="+",
        help="タスクを作成する対象のinput_data_idを指定してください。"
        " 指定したinput_data_idと同じtask_idのタスクを作成し、各タスクには1件の入力データだけを紐づけます。"
        " ``file://`` を先頭に付けると、input_data_idの一覧が記載されたファイルを指定できます。",
    )

    json_sample = '[{"task_id":"task1","input_data_id_list":["input1","input2"]}]'
    file_group.add_argument(
        "--json",
        type=str,
        help=(
            "タスクに割り当てる入力データをJSON形式で指定してください。 "
            "`task list --format json` と同じ形式です。 "
            "`task_id` と `input_data_id_list` と `metadata` と `user_id` キーを参照し、それ以外のキーは無視します。\n"
            f"(ex) ``{json_sample}`` \n"
            "``file://`` を先頭に付けるとjsonファイルを指定できます。"
        ),
    )

    parser.add_argument(
        "--metadata",
        type=str,
        help="タスクに設定する共通の ``metadata`` をJSON形式で指定してください。メタデータの値には文字列、数値、真偽値のいずれかを指定してください。"
        " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        " ``--json`` に指定したタスクの ``metadata`` と同じキーがある場合は、タスクの ``metadata`` が優先されます。",
    )

    parser.add_argument("--user_id", type=str, help="作成するタスクの担当者のuser_idを指定してください。``--json`` に指定したタスクの ``user_id`` が優先されます。")

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="並列度。指定しない場合は、逐次的に処理します。指定する場合は必ず ``--yes`` を指定してください。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """タスク作成コマンドのサブコマンドを追加します。

    Args:
        subparsers: サブコマンドを追加するSubParsersAction。Noneの場合は新しいArgumentParserを作成します。

    Returns:
        タスク作成コマンド用のArgumentParser
    """

    subcommand_name = "create"
    subcommand_help = "タスクを作成します。"
    description = "タスクを作成します。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
