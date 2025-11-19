from __future__ import annotations

import argparse
import copy
import enum
import logging
import multiprocessing
import sys
from enum import Enum
from functools import partial
from pathlib import Path

import annofabapi
import pandas
from pydantic import BaseModel

import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
    get_json_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class UpdateResult(Enum):
    """更新結果の種類"""

    SUCCESS = enum.auto()
    """更新に成功した"""
    SKIPPED = enum.auto()
    """更新を実行しなかった（存在しないproject_id、ユーザー拒否等）"""
    FAILED = enum.auto()
    """更新を試みたが例外で失敗"""


class UpdatedProject(BaseModel):
    """
    更新されるプロジェクト
    """

    project_id: str
    """更新対象のプロジェクトを表すID"""
    title: str | None = None
    """変更後のプロジェクトタイトル（指定した場合のみ更新）"""
    overview: str | None = None
    """変更後のプロジェクト概要（指定した場合のみ更新）"""


class UpdateProjectMain(CommandLineWithConfirm):
    def __init__(self, service: annofabapi.Resource, *, all_yes: bool = False) -> None:
        self.service = service
        CommandLineWithConfirm.__init__(self, all_yes)

    def update_project(
        self,
        project_id: str,
        *,
        new_title: str | None = None,
        new_overview: str | None = None,
        project_index: int | None = None,
    ) -> UpdateResult:
        """
        1個のプロジェクトを更新します。
        """
        # ログメッセージの先頭の変数
        log_prefix = f"project_id='{project_id}' :: "
        if project_index is not None:
            log_prefix = f"{project_index + 1}件目 :: {log_prefix}"

        old_project = self.service.wrapper.get_project_or_none(project_id)
        if old_project is None:
            logger.warning(f"{log_prefix}プロジェクトは存在しません。")
            return UpdateResult.SKIPPED

        # 更新する内容の確認メッセージを作成
        changes = []
        if new_title is not None:
            changes.append(f"title='{old_project['title']}'を'{new_title}'に変更")
        if new_overview is not None:
            changes.append(f"overview='{old_project['overview']}'を'{new_overview}'に変更")

        if len(changes) == 0:
            logger.warning(f"{log_prefix}更新する内容が指定されていません。")
            return UpdateResult.SKIPPED

        change_message = "、".join(changes)
        if not self.confirm_processing(f"{log_prefix}{change_message}しますか？"):
            return UpdateResult.SKIPPED

        request_body = copy.deepcopy(old_project)
        request_body["last_updated_datetime"] = old_project["updated_datetime"]
        request_body["status"] = old_project["project_status"]

        if new_title is not None:
            request_body["title"] = new_title
        if new_overview is not None:
            request_body["overview"] = new_overview

        self.service.api.put_project(project_id, request_body=request_body)
        logger.debug(f"{log_prefix}プロジェクトを更新しました。 :: {change_message}")
        return UpdateResult.SUCCESS

    def update_project_list_sequentially(
        self,
        updated_project_list: list[UpdatedProject],
    ) -> None:
        """複数のプロジェクトを逐次的に更新します。"""
        success_count = 0
        skipped_count = 0  # 更新を実行しなかった個数
        failed_count = 0  # 更新に失敗した個数

        logger.info(f"{len(updated_project_list)} 件のプロジェクトを更新します。")

        for project_index, updated_project in enumerate(updated_project_list):
            current_num = project_index + 1

            # 進捗ログ出力
            if current_num % 100 == 0:
                logger.info(f"{current_num} / {len(updated_project_list)} 件目のプロジェクトを処理中...")

            try:
                result = self.update_project(
                    updated_project.project_id,
                    new_title=updated_project.title,
                    new_overview=updated_project.overview,
                    project_index=project_index,
                )
                if result == UpdateResult.SUCCESS:
                    success_count += 1
                elif result == UpdateResult.SKIPPED:
                    skipped_count += 1
            except Exception:
                logger.warning(f"{current_num}件目 :: project_id='{updated_project.project_id}'のプロジェクトを更新するのに失敗しました。", exc_info=True)
                failed_count += 1
                continue

        logger.info(f"{success_count} / {len(updated_project_list)} 件のプロジェクトを更新しました。（成功: {success_count}件, スキップ: {skipped_count}件, 失敗: {failed_count}件）")

    def _update_project_wrapper(self, args: tuple[int, UpdatedProject]) -> UpdateResult:
        index, updated_project = args
        try:
            return self.update_project(
                project_id=updated_project.project_id,
                new_title=updated_project.title,
                new_overview=updated_project.overview,
                project_index=index,
            )
        except Exception:
            logger.warning(f"{index + 1}件目 :: project_id='{updated_project.project_id}'のプロジェクトを更新するのに失敗しました。", exc_info=True)
            return UpdateResult.FAILED

    def update_project_list_in_parallel(
        self,
        updated_project_list: list[UpdatedProject],
        parallelism: int,
    ) -> None:
        """複数のプロジェクトを並列的に更新します。"""

        logger.info(f"{len(updated_project_list)} 件のプロジェクトを更新します。{parallelism}個のプロセスを使用して並列実行します。")

        partial_func = partial(self._update_project_wrapper)
        with multiprocessing.Pool(parallelism) as pool:
            result_list = pool.map(partial_func, enumerate(updated_project_list))
            success_count = len([e for e in result_list if e == UpdateResult.SUCCESS])
            skipped_count = len([e for e in result_list if e == UpdateResult.SKIPPED])
            failed_count = len([e for e in result_list if e == UpdateResult.FAILED])

        logger.info(f"{success_count} / {len(updated_project_list)} 件のプロジェクトを更新しました。（成功: {success_count}件, スキップ: {skipped_count}件, 失敗: {failed_count}件）")


def create_updated_project_list_from_dict(project_dict_list: list[dict[str, str]]) -> list[UpdatedProject]:
    return [UpdatedProject.model_validate(e) for e in project_dict_list]


def create_updated_project_list_from_csv(csv_file: Path) -> list[UpdatedProject]:
    """プロジェクトの情報が記載されているCSVを読み込み、UpdatedProjectのlistを返します。
    CSVには以下の列が存在します。
    * project_id (必須)
    * title (任意)
    * overview (任意)

    Args:
        csv_file (Path): CSVファイルのパス

    Returns:
        更新対象のプロジェクトのlist
    """
    df_project = pandas.read_csv(
        csv_file,
        # 文字列として読み込むようにする
        dtype={"project_id": "string", "title": "string", "overview": "string"},
    )

    project_dict_list = df_project.to_dict("records")
    return [UpdatedProject.model_validate(e) for e in project_dict_list]


CLI_COMMON_MESSAGE = "annofabcli project update: error:"


class UpdateProject(CommandLine):
    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{CLI_COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、'--yes' も指定する必要があります。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        main_obj = UpdateProjectMain(self.service, all_yes=self.all_yes)

        if args.csv is not None:
            updated_project_list = create_updated_project_list_from_csv(args.csv)

        elif args.json is not None:
            project_dict_list = get_json_from_args(args.json)
            if not isinstance(project_dict_list, list):
                print(f"{CLI_COMMON_MESSAGE} JSON形式が不正です。オブジェクトの配列を指定してください。", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            updated_project_list = create_updated_project_list_from_dict(project_dict_list)
        else:
            raise RuntimeError("argparse により相互排他が保証されているため、ここには到達しません")

        if args.parallelism is not None:
            main_obj.update_project_list_in_parallel(updated_project_list=updated_project_list, parallelism=args.parallelism)
        else:
            main_obj.update_project_list_sequentially(updated_project_list=updated_project_list)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateProject(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    file_group = parser.add_mutually_exclusive_group(required=True)
    file_group.add_argument(
        "--csv",
        type=Path,
        help=(
            "更新対象のプロジェクトと更新後の値が記載されたCSVファイルのパスを指定します。\n"
            "CSVのフォーマットは以下の通りです。"
            "\n"
            " * ヘッダ行あり, カンマ区切り\n"
            " * project_id (required)\n"
            " * title (optional)\n"
            " * overview (optional)\n"
            "更新しないプロパティは、セルの値を空欄にしてください。\n"
        ),
    )

    JSON_SAMPLE = '[{"project_id":"prj1","title":"new_title1"},{"project_id":"prj2","overview":"new_overview2"}]'  # noqa: N806
    file_group.add_argument(
        "--json",
        type=str,
        help=(
            "更新対象のプロジェクトと更新後の値をJSON形式で指定します。\n"
            "JSONの各キーは ``--csv`` に渡すCSVの各列に対応しています。\n"
            "``file://`` を先頭に付けるとjsonファイルを指定できます。\n"
            f"(ex) ``{JSON_SAMPLE}`` \n"
            "更新しないプロパティは、キーを記載しないか値をnullにしてください。\n"
        ),
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）。指定しない場合は、逐次的に処理します。指定する場合は ``--yes`` も一緒に指定する必要があります。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "update"
    subcommand_help = "プロジェクトのタイトルまたは概要を更新します。"
    epilog = "プロジェクトオーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
