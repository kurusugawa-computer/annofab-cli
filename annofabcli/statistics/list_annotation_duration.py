from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from pathlib import Path

from annofabapi.models import InputDataType, ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.annotation_duration import (
    CsvType,
    ListAnnotationDurationMain,
)
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
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


class ListAnnotationDuration(CommandLine):
    """
    区間アノテーションの長さ情報を出力する。
    """

    COMMON_MESSAGE = "annofabcli statistics list_annotation_duration: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.project_id is None and args.annotation is None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --project_id: '--annotation'が未指定のときは、'--project_id' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        logger.warning(
            "[DEPRECATED] statistics list_annotation_durationは非推奨です。annotation_zip sum_annotation_duration_by_label、またはsum_annotation_duration_by_attribute_valueに移行してください。"
        )
        args = self.args

        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id: str | None = args.project_id
        if project_id is not None:
            super().require_project_access(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
            project, _ = self.service.api.get_project(project_id)
            if project["input_data_type"] != InputDataType.MOVIE.value:
                logger.warning(f"project_id='{project_id}'であるプロジェクトは、動画プロジェクトでないので、出力される区間アノテーションの長さはすべて0秒になります。")

        annotation_path = Path(args.annotation) if args.annotation is not None else None

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None

        csv_type = CsvType(args.type)
        output_file: Path = args.output
        arg_format = OutputFormat(args.format)
        main_obj = ListAnnotationDurationMain(self.service)

        downloading_obj = DownloadingFile(self.service)

        def download_and_print_annotation_duration(project_id: str, temp_dir: Path, *, is_latest: bool, annotation_path: Path | None) -> None:
            if annotation_path is None:
                annotation_path = downloading_obj.download_annotation_zip_to_dir(
                    project_id,
                    temp_dir,
                    is_latest=is_latest,
                )

            input_data_json_path = downloading_obj.download_input_data_json_to_dir(
                project_id,
                temp_dir,
                is_latest=is_latest,
            )

            main_obj.print_annotation_duration(
                project_id=project_id,
                csv_type=csv_type,
                arg_format=arg_format,
                output_file=output_file,
                target_task_ids=task_id_list,
                task_query=task_query,
                annotation_path=annotation_path,
                input_data_json_path=input_data_json_path,
            )

        if project_id is not None:
            if args.temp_dir is not None:
                download_and_print_annotation_duration(project_id=project_id, temp_dir=args.temp_dir, is_latest=args.latest, annotation_path=annotation_path)
            else:
                # `NamedTemporaryFile`を使わない理由: Windowsで`PermissionError`が発生するため
                # https://qiita.com/yuji38kwmt/items/c6f50e1fc03dafdcdda0 参考
                with tempfile.TemporaryDirectory() as str_temp_dir:
                    download_and_print_annotation_duration(project_id=project_id, temp_dir=Path(str_temp_dir), is_latest=args.latest, annotation_path=annotation_path)
        else:
            assert annotation_path is not None
            main_obj.print_annotation_duration(
                project_id=project_id,
                csv_type=csv_type,
                arg_format=arg_format,
                output_file=output_file,
                target_task_ids=task_id_list,
                task_query=task_query,
                annotation_path=annotation_path,
                input_data_json_path=None,
            )


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    parser.add_argument(
        "--annotation",
        type=str,
        help="アノテーションzip、またはzipを展開したディレクトリを指定します。指定しない場合はAnnofabからダウンロードします。",
    )

    parser.add_argument(
        "-p",
        "--project_id",
        type=str,
        help="project_id。``--annotation`` が未指定のときは必須です。\n"
        "``--annotation`` が指定されているときに ``--project_id`` を指定すると、アノテーション仕様を参照して、集計対象の属性やCSV列順が決まります。"
        "また、動画の長さ( ``video_duration_second`` )も出力します。",
    )

    parser.add_argument(
        "--type",
        type=str,
        choices=[e.value for e in CsvType],
        default=CsvType.LABEL.value,
        help="出力するCSVの種類を指定してください。 ``--format csv`` を指定したときのみ有効なオプションです。\n"
        "\n"
        "* label: ラベルごとに区間アノテーションの長さが記載されているCSV\n"
        "* attribute: 属性値ごとに区間アノテーションの長さが記載されているCSV",
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

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAnnotationDuration(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_annotation_duration"
    subcommand_help = "[非推奨] ラベルごとまたは属性値ごとに区間アノテーションの長さ（秒）を出力します。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
