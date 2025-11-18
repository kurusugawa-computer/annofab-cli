from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import annofabapi
import pandas
from annofabapi.models import ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.annofab.annotation_zip import lazy_parse_simple_annotation_by_input_data
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery, match_annotation_with_task_query
from annofabcli.common.utils import print_csv, print_json

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """バリデーション結果を格納するクラス"""

    project_id: str
    task_id: str
    input_data_id: str
    input_data_name: str
    annotation_id: str
    label_name: str
    function_name: str
    is_valid: bool
    error_message: str | None = None
    detail_data: dict[str, Any] | None = None


class ValidationFunctionLoader:
    """ユーザー定義のバリデーション関数をロードするクラス"""

    def __init__(self, validation_file_path: Path) -> None:
        """
        Args:
            validation_file_path: バリデーション関数が定義されたPythonファイルのパス
        """
        self.validation_file_path = validation_file_path

    def load_validation_functions(self) -> dict[str, Callable[[dict[str, Any]], bool]]:
        """
        バリデーション関数をロードして辞書で返す。

        バリデーション関数は以下のシグネチャを持つ必要がある：
        ```python
        def validate_detail(detail: dict[str, Any]) -> bool:
            # バリデーションロジック
            return True  # 正常な場合
        ```

        Returns:
            関数名をキーとするバリデーション関数の辞書

        Raises:
            ImportError: バリデーションファイルの読み込みに失敗した場合
        """
        if not self.validation_file_path.exists():
            msg = f"バリデーションファイルが存在しません: {self.validation_file_path}"
            raise FileNotFoundError(msg)

        spec = importlib.util.spec_from_file_location("validation_module", self.validation_file_path)
        if spec is None or spec.loader is None:
            msg = f"バリデーションファイルの読み込みに失敗しました: {self.validation_file_path}"
            raise ImportError(msg)

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        validation_functions = {}
        for name in dir(module):
            obj = getattr(module, name)
            if callable(obj) and name.startswith("validate_") and not name.startswith("__"):
                validation_functions[name] = obj
                logger.debug(f"バリデーション関数を読み込みました: {name}")

        if not validation_functions:
            logger.warning(f"バリデーション関数が見つかりません: {self.validation_file_path}")

        return validation_functions


class AnnotationValidator:
    """アノテーションのバリデーションを実行するクラス"""

    def __init__(
        self,
        service: annofabapi.Resource,
        project_id: str,
        validation_functions: dict[str, Callable[[dict[str, Any]], bool]],
        task_query: TaskQuery | None = None,
    ) -> None:
        self.service = service
        self.project_id = project_id
        self.validation_functions = validation_functions
        self.task_query = task_query
        self.facade = AnnofabApiFacade(service)

    def validate_annotations(self, annotation_zip_path: Path) -> list[ValidationResult]:
        """
        アノテーションZIPファイルを検証する。

        Args:
            annotation_zip_path: アノテーションZIPファイルのパス

        Returns:
            バリデーション結果のリスト
        """
        logger.info("アノテーションの検証を開始します。")
        results: list[ValidationResult] = []

        count_validated_annotations = 0

        # アノテーションZIPからアノテーション詳細情報を取得
        for parser in lazy_parse_simple_annotation_by_input_data(annotation_zip_path):
            simple_annotation_detail = parser.load_json()

            # タスク検索条件でフィルタリング
            if self.task_query is not None and not match_annotation_with_task_query(simple_annotation_detail, self.task_query):
                continue

            task_id = simple_annotation_detail["task_id"]
            input_data_id = simple_annotation_detail["input_data_id"]
            input_data_name = simple_annotation_detail["input_data_name"]

            details = simple_annotation_detail["details"]
            for detail in details:
                annotation_id = detail["annotation_id"]
                label_name = detail["label"]

                count_validated_annotations += 1
                if count_validated_annotations % 1000 == 0:
                    logger.info(f"{count_validated_annotations} 件のアノテーションを検証しました。")

                # 各バリデーション関数を実行
                for function_name, validation_function in self.validation_functions.items():
                    try:
                        is_valid = validation_function(detail)
                        result = ValidationResult(
                            project_id=self.project_id,
                            task_id=task_id,
                            input_data_id=input_data_id,
                            input_data_name=input_data_name,
                            annotation_id=annotation_id,
                            label_name=label_name,
                            function_name=function_name,
                            is_valid=is_valid,
                            detail_data=detail if not is_valid else None,
                        )
                        results.append(result)

                        if not is_valid:
                            logger.debug(f"バリデーション失敗: task_id={task_id}, input_data_id={input_data_id}, annotation_id={annotation_id}, function={function_name}")

                    except Exception as e:
                        error_message = f"バリデーション関数でエラーが発生しました: {e!s}"
                        logger.warning(error_message, exc_info=True)
                        result = ValidationResult(
                            project_id=self.project_id,
                            task_id=task_id,
                            input_data_id=input_data_id,
                            input_data_name=input_data_name,
                            annotation_id=annotation_id,
                            label_name=label_name,
                            function_name=function_name,
                            is_valid=False,
                            error_message=error_message,
                            detail_data=detail,
                        )
                        results.append(result)

        logger.info(f"検証完了: {count_validated_annotations} 件のアノテーションを処理しました。")
        return results


class ValidateAnnotation(CommandLine):
    """
    アノテーションZIPをユーザー定義のバリデーション関数で検証する。
    """

    def __init__(self, service, facade, args) -> None:  # noqa: ANN001
        super().__init__(service, facade, args)

    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli annotation_zip validate: error:"  # noqa: N806

        validation_file_path = Path(args.validation_file)
        if not validation_file_path.exists():
            print(  # noqa: T201
                f"{COMMON_MESSAGE} バリデーションファイルが存在しません: {validation_file_path}",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id

        # プロジェクトメンバーかどうかを確認
        self.facade.validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        # バリデーション関数をロード
        try:
            function_loader = ValidationFunctionLoader(Path(args.validation_file))
            validation_functions = function_loader.load_validation_functions()
        except (ImportError, FileNotFoundError):
            logger.exception("バリデーション関数の読み込みに失敗しました")
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        if not validation_functions:
            logger.error("有効なバリデーション関数が見つかりません。")
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        logger.info(f"読み込んだバリデーション関数: {list(validation_functions.keys())}")

        # タスク検索クエリ
        task_query: TaskQuery | None = None
        if args.task_query is not None:
            dict_task_query = annofabcli.common.cli.get_json_from_args(args.task_query)
            task_query = TaskQuery.from_dict(dict_task_query)

        # アノテーションZIPファイルのダウンロード
        if args.annotation_zip is None:
            # 最新のアノテーションZIPをダウンロード
            with tempfile.TemporaryDirectory() as str_temp_dir:
                temp_dir = Path(str_temp_dir)
                logger.info("最新のアノテーションZIPをダウンロードしています...")

                downloading_obj = DownloadingFile(self.service)
                annotation_zip_path = downloading_obj.download_annotation_zip_to_dir(project_id, temp_dir)

                # バリデーション実行
                validator = AnnotationValidator(
                    service=self.service,
                    project_id=project_id,
                    validation_functions=validation_functions,
                    task_query=task_query,
                )
                results = validator.validate_annotations(annotation_zip_path)
        else:
            # ローカルのアノテーションZIPファイルを使用
            annotation_zip_path = Path(args.annotation_zip)
            if not annotation_zip_path.exists():
                logger.error(f"アノテーションZIPファイルが存在しません: {annotation_zip_path}")
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

            validator = AnnotationValidator(
                service=self.service,
                project_id=project_id,
                validation_functions=validation_functions,
                task_query=task_query,
            )
            results = validator.validate_annotations(annotation_zip_path)

        # 結果の出力
        self._output_results(results, args.format, args.output_file)

        # サマリー表示
        self._print_summary(results)

    def _output_results(self, results: list[ValidationResult], format_type: str, output_file: Path | None) -> None:
        """バリデーション結果を出力する"""
        if not results:
            logger.info("バリデーション結果はありません。")
            return

        # DataFrameに変換
        df_results = pandas.DataFrame(
            [
                {
                    "project_id": result.project_id,
                    "task_id": result.task_id,
                    "input_data_id": result.input_data_id,
                    "input_data_name": result.input_data_name,
                    "annotation_id": result.annotation_id,
                    "label_name": result.label_name,
                    "function_name": result.function_name,
                    "is_valid": result.is_valid,
                    "error_message": result.error_message,
                    "detail_data": json.dumps(result.detail_data, ensure_ascii=False) if result.detail_data else None,
                }
                for result in results
            ]
        )

        # フォーマットに応じて出力
        if format_type == "json":
            if output_file is not None:
                print_json(results, output=output_file, is_pretty=True)
            else:
                print_json(results, is_pretty=True)
        elif output_file is not None:
            print_csv(df_results, output=output_file)
        else:
            print_csv(df_results)

    def _print_summary(self, results: list[ValidationResult]) -> None:
        """バリデーション結果のサマリーを表示する"""
        if not results:
            return

        df_results = pandas.DataFrame(
            [
                {
                    "function_name": result.function_name,
                    "is_valid": result.is_valid,
                }
                for result in results
            ]
        )

        summary = df_results.groupby(["function_name", "is_valid"]).size().reset_index(name="count").pivot_table(index="function_name", columns="is_valid", values="count", fill_value=0)

        logger.info("=== バリデーション結果サマリー ===")
        for function_name in summary.index:
            valid_count = summary.loc[function_name].get(True, 0)
            invalid_count = summary.loc[function_name].get(False, 0)
            total_count = valid_count + invalid_count
            logger.info(f"{function_name}: 正常 {valid_count} / 異常 {invalid_count} / 合計 {total_count}")


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ValidateAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--validation_file",
        type=Path,
        required=True,
        help=(
            "バリデーション関数が定義されたPythonファイルのパスを指定してください。\n"
            "ファイル内で 'validate_' から始まる関数が自動的に検出され、バリデーション関数として使用されます。\n"
            "バリデーション関数は 'def validate_xxx(detail: dict[str, Any]) -> bool:' のシグネチャを持つ必要があります。"
        ),
    )

    parser.add_argument(
        "--annotation_zip",
        type=Path,
        help="検証対象のアノテーションZIPファイルのパスを指定してください。指定しない場合は、最新のアノテーションZIPをダウンロードして使用します。",
    )

    parser.add_argument(
        "--task_query",
        type=str,
        help=(
            "タスクの検索クエリをJSON形式で指定します。\n"
            "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。\n"
            "クエリのキーは、``task_id`` , ``phase`` , ``phase_stage`` , ``status`` のみです。"
        ),
    )

    argument_parser.add_format(choices=[FormatArgument.CSV, FormatArgument.JSON], default=FormatArgument.CSV)
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "validate"
    subcommand_help = "ユーザー定義のバリデーション関数でアノテーションZIPを検証します。"
    description = "ユーザー定義のバリデーション関数でアノテーションZIPを検証します。\nバリデーション関数は 'validate_' から始まる関数名で定義してください。"
    epilog = "アノテーションユーザまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
