from __future__ import annotations

import argparse
import logging
import tempfile
from functools import partial
from pathlib import Path

from annofabapi.models import ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.annotation_count import (
    AnnotationSpecs,
    AttributeNameKey,
    CsvType,
    GroupBy,
    ListAnnotationCountMain,
)
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import (
    AnnofabApiFacade,
    TaskQuery,
)

logger = logging.getLogger(__name__)

DEPRECATED_MESSAGE = (
    "[DEPRECATED] :: `statistics list_annotation_count` コマンドは非推奨です。"
    "ラベルごとの集計は `annotation_zip count_annotation_by_label` コマンドを使用してください。"
    "属性値ごとの集計は `annotation_zip count_annotation_by_attribute_value` コマンドを使用してください。 "
    "`statistics list_annotation_count` コマンドは2027/01/01以降に廃止予定です。"
)


class ListAnnotationCount(CommandLine):
    """
    アノテーション数情報を出力する。
    """

    def main(self) -> None:
        """
        アノテーション数情報を出力するメイン処理。
        コマンドライン引数を解析し、アノテーションzip/ディレクトリから集計情報を取得して、
        指定された形式（CSV/JSON）で出力します。
        """
        args = self.args

        project_id: str = args.project_id
        super().require_project_access(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        annotation_path = args.annotation

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None

        # アノテーション仕様を取得
        annotation_specs = AnnotationSpecs(self.service, project_id)

        additional_attribute_names: list[AttributeNameKey] | None = None
        specified_attribute_names: list[AttributeNameKey] | None = None

        if args.additional_attribute_name is not None:
            attribute_name_str_list = annofabcli.common.cli.get_list_from_args(args.additional_attribute_name)
            # アノテーション仕様から属性名を検索してAttributeNameKeyのリストに変換
            additional_attribute_names, not_found_names = annotation_specs.get_attribute_name_keys_by_attribute_names(attribute_name_str_list)
            if len(not_found_names) > 0:
                logger.warning(f"指定された属性名のうち、アノテーション仕様に見つからなかった属性名があります。 :: {not_found_names}")
        elif args.attribute_name is not None:
            attribute_name_str_list = annofabcli.common.cli.get_list_from_args(args.attribute_name)
            # アノテーション仕様から属性名を検索してAttributeNameKeyのリストに変換
            specified_attribute_names, not_found_names = annotation_specs.get_attribute_name_keys_by_attribute_names(attribute_name_str_list)
            if len(not_found_names) > 0:
                logger.warning(f"指定された属性名のうち、アノテーション仕様に見つからなかった属性名があります。 :: {not_found_names}")

        group_by = GroupBy(args.group_by)
        csv_type = CsvType(args.type)
        output_file: Path = args.output
        arg_format = OutputFormat(args.format)
        main_obj = ListAnnotationCountMain(self.service, annotation_specs)

        downloading_obj = DownloadingFile(self.service)

        def download_and_process_annotation(temp_dir: Path, *, is_latest: bool, annotation_path: Path | None) -> None:
            # タスク全件ファイルは、group_by=input_data_idの場合のみフレーム番号を参照するのに利用する
            task_json_path: Path | None = None
            if group_by == GroupBy.INPUT_DATA_ID:
                task_json_path = downloading_obj.download_task_json_to_dir(
                    project_id,
                    temp_dir,
                    is_latest=is_latest,
                )

            func = partial(
                main_obj.print_annotation_counter,
                task_json_path=task_json_path,
                group_by=group_by,
                csv_type=csv_type,
                arg_format=arg_format,
                output_file=output_file,
                target_task_ids=task_id_list,
                task_query=task_query,
                additional_attribute_names=additional_attribute_names,
                specified_attribute_names=specified_attribute_names,
            )

            if annotation_path is None:
                annotation_path = downloading_obj.download_annotation_zip_to_dir(
                    project_id,
                    temp_dir,
                    is_latest=is_latest,
                )
                func(annotation_path=annotation_path)
            else:
                func(annotation_path=annotation_path)

        if args.temp_dir is not None:
            download_and_process_annotation(temp_dir=args.temp_dir, is_latest=args.latest, annotation_path=annotation_path)
        else:
            with tempfile.TemporaryDirectory() as str_temp_dir:
                download_and_process_annotation(temp_dir=Path(str_temp_dir), is_latest=args.latest, annotation_path=annotation_path)


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    コマンドライン引数のパーサーを設定します。

    Args:
        parser: argparseのArgumentParserインスタンス
    """
    argument_parser = ArgumentParser(parser)

    parser.add_argument(
        "--annotation",
        type=Path,
        help="アノテーションzip、またはzipを展開したディレクトリを指定します。指定しない場合はAnnofabからダウンロードします。",
    )

    argument_parser.add_project_id()

    parser.add_argument(
        "--group_by",
        type=str,
        choices=[GroupBy.TASK_ID.value, GroupBy.INPUT_DATA_ID.value],
        default=GroupBy.TASK_ID.value,
        help="アノテーションの個数をどの単位で集約するかを指定してます。",
    )

    parser.add_argument(
        "--type",
        type=str,
        choices=[e.value for e in CsvType],
        default=CsvType.LABEL.value,
        help="出力するCSVの種類を指定してください。 ``--format csv`` を指定したときのみ有効なオプションです。\n"
        "\n"
        "* label: ラベルごとにアノテーション数が記載されているCSV\n"
        "* attribute: 属性値ごとにアノテーション数が記載されているCSV",
    )

    argument_parser.add_format(
        choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON],
        default=OutputFormat.CSV,
    )

    argument_parser.add_output()

    parser.add_argument(
        "-tq",
        "--task_query",
        type=str,
        help="集計対象タスクを絞り込むためのクエリ条件をJSON形式で指定します。使用できるキーは task_id, status, phase, phase_stage です。"
        " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
    )
    argument_parser.add_task_id(required=False)

    parser.add_argument(
        "--latest",
        action="store_true",
        help="``--annotation`` を指定しないとき、最新のアノテーションzipを参照します。このオプションを指定すると、アノテーションzipを更新するのに数分待ちます。",
    )

    parser.add_argument(
        "--temp_dir",
        type=Path,
        help="指定したディレクトリに、アノテーションZIPなどの一時ファイルをダウンロードします。",
    )

    # --attribute_nameと--additional_attribute_nameは排他的
    attribute_group = parser.add_mutually_exclusive_group()
    attribute_group.add_argument(
        "--additional_attribute_name",
        type=str,
        nargs="+",
        help=(
            "デフォルトで集計される選択肢系の属性（ドロップダウン、ラジオボタン、チェックボックス）に加えて、集計したい属性の英語名を指定します。"
            "ラベル名に関係なく、デフォルト属性と指定した属性名を持つ属性が集計対象になります。"
            " ``file://`` を先頭に付けると、属性名が記載されたファイルを指定できます。"
            " ``--type attribute`` を指定したときのみ有効なオプションです。"
            " ファイルを読み込む場合は、ファイル指定を1個だけ渡してください。"
            "直接指定する値や別のファイル指定とは併用できません。"
        ),
    )

    attribute_group.add_argument(
        "--attribute_name",
        type=str,
        nargs="+",
        help=(
            "集計対象とする属性の英語名を指定します。"
            "指定した属性名のみが集計対象になります（デフォルトの選択肢系属性は含まれません）。"
            "ラベル名に関係なく、指定した属性名を持つ属性のみが集計対象になります。"
            " ``file://`` を先頭に付けると、属性名が記載されたファイルを指定できます。"
            " ``--type attribute`` を指定したときのみ有効なオプションです。"
            " ファイルを読み込む場合は、ファイル指定を1個だけ渡してください。"
            "直接指定する値や別のファイル指定とは併用できません。"
        ),
    )

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    list_annotation_countコマンドのエントリーポイント。

    Args:
        args: コマンドライン引数
    """
    logger.warning(DEPRECATED_MESSAGE)
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAnnotationCount(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    list_annotation_countサブコマンドのパーサーを追加します。

    Args:
        subparsers: 親パーサーのサブパーサーアクション

    Returns:
        作成されたArgumentParserインスタンス
    """
    subcommand_name = "list_annotation_count"
    subcommand_help = "[DEPRECATED] ラベルごとまたは属性値ごとにアノテーション数を出力します。"
    description = f"{subcommand_help}\n{DEPRECATED_MESSAGE}"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog)
    parse_args(parser)
    return parser
