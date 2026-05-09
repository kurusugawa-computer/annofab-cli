from __future__ import annotations

import argparse
import logging
import multiprocessing
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, TypeGuard, cast

import annofabapi
import pandas
from annofabapi.models import ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
    get_json_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)

TaskInputRelation = dict[str, list[str]]
"""task_idとinput_data_idの構造を表現する型"""

TaskMetadataValue = str | int | float | bool
"""タスクのメタデータに指定できる値の型"""

Metadata = dict[str, TaskMetadataValue]
"""タスクのメタデータを表現する型"""


@dataclass(frozen=True)
class TaskCreationInfo:
    """タスク作成時に指定する情報"""

    input_data_id_list: list[str]
    metadata: Metadata
    user_id: str | None = None


TaskCreationInfoDict = dict[str, TaskCreationInfo]
"""task_idとタスク作成情報の関係を表現する型"""


def print_json_error_and_exit(message: str) -> NoReturn:
    """JSON形式のエラーメッセージを出力して、コマンドラインエラーとして終了します。"""

    print(f"annofabcli task create: error: JSON形式が不正です。{message}", file=sys.stderr)  # noqa: T201
    sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)


def print_error_and_exit(message: str) -> NoReturn:
    """エラーメッセージを出力して、コマンドラインエラーとして終了します。"""

    print(f"annofabcli task create: error: {message}", file=sys.stderr)  # noqa: T201
    sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)


def get_task_relation_dict(csv_file: Path) -> TaskInputRelation:
    """ヘッダ行ありCSVから、keyがtask_id, valueがinput_data_idのlistのdictを生成します。"""

    # `dtype=str`を指定した理由：指定しないと、IDが`001`のときに`1`に変換されてしまうため
    df = pandas.read_csv(str(csv_file), dtype=str)
    if "task_id" not in df.columns or "input_data_id" not in df.columns:
        sys.stderr.write("annofabcli task create: error: CSV形式が不正です。ヘッダ行に 'task_id' と 'input_data_id' を指定してください。\n")
        sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

    result: TaskInputRelation = defaultdict(list)
    for task_id, input_data_id in zip(df["task_id"], df["input_data_id"], strict=False):
        result[task_id].append(input_data_id)
    return result


def is_metadata_value(value: object) -> TypeGuard[TaskMetadataValue]:
    """タスクメタデータの値として指定できる型かどうかを返します。"""

    return isinstance(value, str | int | float | bool)


def validate_metadata(metadata: object, *, target_name: str) -> Metadata:
    """メタデータの形式を検証します。

    Args:
        metadata: 検証対象のメタデータ
        target_name: エラーメッセージに表示する対象名

    Returns:
        検証済みのメタデータ
    """

    if not isinstance(metadata, dict):
        raise TypeError(f"{target_name}にはオブジェクトを指定してください。")

    result: Metadata = {}
    metadata_dict = cast(dict[object, object], metadata)
    for key, value in metadata_dict.items():
        if not isinstance(key, str):
            raise TypeError(f"{target_name}のキーには文字列を指定してください。")
        if not is_metadata_value(value):
            raise TypeError(f"{target_name}の値には文字列、数値、真偽値のいずれかを指定してください。")
        result[key] = value

    return result


def get_metadata_from_json_args(metadata_value: str | None) -> Metadata:
    """JSON引数から、全タスク共通のメタデータを取得します。

    Args:
        metadata_value: メタデータを表すJSON文字列、またはJSONファイルのパス

    Returns:
        全タスク共通のメタデータ
    """

    if metadata_value is None:
        return {}

    return validate_metadata(get_json_from_args(metadata_value), target_name="引数'--metadata'")


def get_task_creation_info_dict_from_task_relation_dict(
    task_relation_dict: TaskInputRelation,
    *,
    common_metadata: Metadata | None = None,
    common_user_id: str | None = None,
) -> TaskCreationInfoDict:
    """task_idとinput_data_idの関係を表すdictから、タスク作成情報のdictを取得します。"""

    common_metadata = common_metadata or {}
    return {
        task_id: TaskCreationInfo(
            input_data_id_list=input_data_id_list,
            metadata=common_metadata,
            user_id=common_user_id,
        )
        for task_id, input_data_id_list in task_relation_dict.items()
    }


def get_task_creation_info_dict_from_json_args(
    json_value: str,
    *,
    common_metadata: Metadata | None = None,
    common_user_id: str | None = None,
) -> TaskCreationInfoDict:
    """JSON引数からタスク作成情報のdictを取得します。

    Args:
        json_value: `task list --format json` と同じ形式のJSON文字列、またはJSONファイルのパス
        common_metadata: 全タスク共通のメタデータ
        common_user_id: 全タスク共通の担当者のuser_id

    Returns:
        keyがtask_id, valueがタスク作成情報であるdict
    """

    task_list = get_json_from_args(json_value)
    if not isinstance(task_list, list):
        raise TypeError("配列を指定してください。")

    common_metadata = common_metadata or {}
    result: TaskCreationInfoDict = {}
    for index, task in enumerate(task_list):
        if not isinstance(task, dict):
            raise TypeError(f"{index + 1}番目の要素にはオブジェクトを指定してください。")

        task_id = task.get("task_id")
        if not isinstance(task_id, str):
            raise TypeError(f"{index + 1}番目の要素の'task_id'には文字列を指定してください。")

        input_data_id_list = task.get("input_data_id_list")
        if not isinstance(input_data_id_list, list) or not all(isinstance(e, str) for e in input_data_id_list):
            raise TypeError(f"{index + 1}番目の要素の'input_data_id_list'には文字列の配列を指定してください。")

        task_metadata = validate_metadata(task.get("metadata", {}), target_name=f"{index + 1}番目の要素の'metadata'")
        metadata = {
            **common_metadata,
            **task_metadata,
        }
        json_user_id = task.get("user_id")
        if json_user_id is not None and not isinstance(json_user_id, str):
            raise TypeError(f"{index + 1}番目の要素の'user_id'には文字列を指定してください。")
        task_user_id = json_user_id or common_user_id

        if task_id in result:
            raise ValueError(f"{index + 1}番目の要素の'task_id'が重複しています。 :: task_id='{task_id}'")
        else:
            result[task_id] = TaskCreationInfo(input_data_id_list=input_data_id_list, metadata=metadata, user_id=task_user_id)

    return result


class CreateTaskMain:
    def __init__(
        self,
        service: annofabapi.Resource,
        project_id: str,
        *,
        parallelism: int | None,
    ) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.project_id = project_id
        self.parallelism = parallelism
        self.account_id_cache: dict[str, str] = {}

    def get_account_id_from_user_id(self, user_id: str) -> str:
        """user_idからaccount_idを取得します。"""

        account_id = self.account_id_cache.get(user_id)
        if account_id is not None:
            return account_id

        account_id = self.facade.get_account_id_from_user_id(self.project_id, user_id)
        if account_id is None:
            print_error_and_exit(f"user_id='{user_id}'であるユーザーは、project_id='{self.project_id}'のプロジェクトメンバーではありません。")

        self.account_id_cache[user_id] = account_id
        return account_id

    def validate_task_does_not_exist(self, task_creation_info_dict: TaskCreationInfoDict) -> None:
        """作成対象のタスクが存在しないことを確認します。"""

        existing_task_id_list = [task_id for task_id in task_creation_info_dict if self.service.wrapper.get_task_or_none(self.project_id, task_id) is not None]
        if len(existing_task_id_list) > 0:
            print_error_and_exit(f"以下のタスクはすでに存在します。 :: task_id={existing_task_id_list}")

    def validate_user_id(self, task_creation_info_dict: TaskCreationInfoDict) -> None:
        """指定されたuser_idがプロジェクトメンバーであることを確認します。"""

        user_id_set = {info.user_id for info in task_creation_info_dict.values() if info.user_id is not None}
        for user_id in sorted(user_id_set):
            self.get_account_id_from_user_id(user_id)

    def create_task(self, task_id: str, task_creation_info: TaskCreationInfo) -> bool:
        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is not None:
            raise ValueError(f"タスク'{task_id}'はすでに存在します。")

        # タスクを上書きしない理由：タスクを上書きすると、タスクに紐づくアノテーションまで消えてしまう恐れがあるため
        request_body: dict[str, list[str] | Metadata] = {"input_data_id_list": task_creation_info.input_data_id_list}
        if len(task_creation_info.metadata) > 0:
            request_body["metadata"] = task_creation_info.metadata
        self.service.api.put_task(self.project_id, task_id, request_body=request_body)

        if task_creation_info.user_id is not None:
            account_id = self.get_account_id_from_user_id(task_creation_info.user_id)
            self.service.wrapper.change_task_operator(self.project_id, task_id, operator_account_id=account_id)

        logger.debug(f"タスク'{task_id}'を登録しました。")
        return True

    def create_task_wrapper(self, tpl: tuple[str, TaskCreationInfo]) -> bool:
        task_id, task_creation_info = tpl
        try:
            return self.create_task(task_id, task_creation_info)
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"タスク'{task_id}'の登録に失敗しました。", exc_info=True)
            return False

    def create_task_list(self, task_creation_info_dict: TaskCreationInfoDict) -> None:
        logger.debug("'put_task' WebAPIを用いてタスクを生成します。")
        self.validate_task_does_not_exist(task_creation_info_dict)
        self.validate_user_id(task_creation_info_dict)

        success_count = 0
        if self.parallelism is None:
            for task_id, task_creation_info in task_creation_info_dict.items():
                try:
                    result = self.create_task(task_id, task_creation_info)
                    if result:
                        success_count += 1
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"タスク'{task_id}'の登録に失敗しました。", exc_info=True)

        else:
            with multiprocessing.Pool(self.parallelism) as p:
                results = p.map(self.create_task_wrapper, task_creation_info_dict.items())
                success_count = len([e for e in results if e])

        logger.info(f"{success_count} / {len(task_creation_info_dict)} 件のタスクを登録しました。")


class CreateTask(CommandLine):
    def main(self) -> None:
        args = self.args
        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        try:
            common_metadata = get_metadata_from_json_args(args.metadata)
        except (TypeError, ValueError) as e:
            print_json_error_and_exit(str(e))
        main_obj = CreateTaskMain(
            self.service,
            project_id=args.project_id,
            parallelism=args.parallelism,
        )

        if args.csv is not None:
            task_relation_dict_from_csv = get_task_relation_dict(args.csv)
            main_obj.create_task_list(get_task_creation_info_dict_from_task_relation_dict(task_relation_dict_from_csv, common_metadata=common_metadata, common_user_id=args.user_id))

        elif args.json is not None:
            try:
                task_creation_info_dict_from_json = get_task_creation_info_dict_from_json_args(args.json, common_metadata=common_metadata, common_user_id=args.user_id)
            except (TypeError, ValueError) as e:
                print_json_error_and_exit(str(e))
            main_obj.create_task_list(task_creation_info_dict_from_json)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CreateTask(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
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

    json_sample = '[{"task_id":"task1","input_data_id_list":["input1","input2"]}]'
    file_group.add_argument(
        "--json",
        type=str,
        help=(
            "タスクに割り当てる入力データをJSON形式で指定してください。"
            "`task list --format json` と同じ形式です。"
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
        help="並列度。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "create"
    subcommand_help = "タスクを作成します。"
    description = "タスクを作成します。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
