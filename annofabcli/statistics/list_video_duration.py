from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
from functools import partial
from pathlib import Path
from typing import Any, Optional

import pandas
from annofabapi.models import InputDataType, ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import print_according_to_format, print_csv

logger = logging.getLogger(__name__)


def get_video_duration_list(task_list: list[dict[str, Any]], input_data_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    タスクlistと入力データlistから、動画長さの一覧を取得します。

    """
    dict_input_data_by_id = {e["input_data_id"]: e for e in input_data_list}

    result = []
    for task in task_list:
        task_id = task["task_id"]
        elm = {"project_id": task["project_id"], "task_id": task_id, "task_status": task["status"], "task_phase": task["phase"], "task_phase_stage": task["phase_stage"]}
        input_data_id_list = task["input_data_id_list"]
        assert len(input_data_id_list) == 1, f"task_id='{task_id}'には複数の入力データが含まれています。"
        input_data_id = input_data_id_list[0]
        elm["input_data_id"] = input_data_id
        input_data = dict_input_data_by_id.get(input_data_id)
        if input_data is None:
            logger.warning(f"task_id='{task_id}'のタスクに含まれている入力データ（input_data_id='{input_data_id}'）は、見つかりません。")
            elm.update({"input_data_name": None, "video_duration_second": 0})
        else:
            video_duration_second = input_data["system_metadata"]["input_duration"]
            if video_duration_second is None:
                logger.warning(f"input_data_id='{input_data_id}' :: 'system_metadata.input_duration'がNoneです。")
                video_duration_second = 0

            elm.update(
                {
                    "input_data_name": input_data["input_data_name"],
                    "video_duration_second": video_duration_second,
                    "input_data_updated_datetime": input_data["updated_datetime"],
                }
            )

        result.append(elm)
    return result


class ListVideoDuration(CommandLine):
    COMMON_MESSAGE = "annofabcli statistics list_video_duration: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.project_id is None and (args.input_data_json is None or args.task_json is None):
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --project_id: '--input_data_json'または'--task_json'が未指定のときは、'--project_id' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def list_video_duration(
        self,
        task_json: Path,
        input_data_json: Path,
        output_format: FormatArgument,
        output_file: Optional[Path],
    ) -> None:
        with task_json.open() as f:
            task_list = json.load(f)
        with input_data_json.open() as f:
            input_data_list = json.load(f)

        video_duration_list = get_video_duration_list(task_list=task_list, input_data_list=input_data_list)
        logger.info(f"{len(video_duration_list)} 件のタスクの動画長さを出力します。")
        if output_format == FormatArgument.CSV:
            columns = [
                "project_id",
                "task_id",
                "task_status",
                "task_phase",
                "task_phase_stage",
                "input_data_id",
                "input_data_name",
                "video_duration_second",
                "input_data_updated_datetime",
            ]
            df = pandas.DataFrame(video_duration_list, columns=columns)
            print_csv(df, output=output_file)
        else:
            print_according_to_format(video_duration_list, format=output_format, output=output_file)

    def main(self) -> None:
        args = self.args

        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id: Optional[str] = args.project_id
        if project_id is not None:
            super().validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
            project, _ = self.service.api.get_project(project_id)
            if project["input_data_type"] != InputDataType.MOVIE.value:
                print(  # noqa: T201
                    f"project_id='{project_id}'であるプロジェクトは、動画プロジェクトでないので動画の長さを出力できません。終了します。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        func = partial(self.list_video_duration, output_file=args.output, output_format=FormatArgument(args.format))

        def wrapper_func(temp_dir: Path) -> None:
            downloading_obj = DownloadingFile(self.service)
            assert project_id is not None
            if args.input_data_json is None:
                input_data_json = temp_dir / f"{project_id}__input_data.json"
                downloading_obj.download_input_data_json(
                    project_id,
                    dest_path=input_data_json,
                    is_latest=args.latest,
                )
            else:
                input_data_json = args.input_data_json

            if args.task_json is None:
                task_json = temp_dir / f"{project_id}__task.json"
                downloading_obj.download_task_json(
                    project_id,
                    dest_path=task_json,
                    is_latest=args.latest,
                )
            else:
                task_json = args.task_json

            func(task_json=task_json, input_data_json=input_data_json)

        if args.input_data_json is None or args.task_json is None:
            if args.temp_dir is not None:
                wrapper_func(args.temp_dir)
            else:
                # `NamedTemporaryFile`を使わない理由: Windowsで`PermissionError`が発生するため
                # https://qiita.com/yuji38kwmt/items/c6f50e1fc03dafdcdda0 参考
                with tempfile.TemporaryDirectory() as str_temp_dir:
                    wrapper_func(Path(str_temp_dir))

        else:
            func(task_json=args.task_json, input_data_json=args.input_data_json)


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    parser.add_argument(
        "--input_data_json",
        type=Path,
        required=False,
        help="入力データ情報が記載されたJSONファイルのパスを指定します。\nJSONファイルは ``$ annofabcli input_data download`` コマンドで取得できます。",
    )

    parser.add_argument(
        "--task_json",
        type=Path,
        required=False,
        help="タスク情報が記載されたJSONファイルのパスを指定します。\nJSONファイルは ``$ annofabcli task download`` コマンドで取得できます。",
    )

    parser.add_argument(
        "-p",
        "--project_id",
        type=str,
        required=False,
        help="出力対象プロジェクトのID。``--input_data_json`` と ``--task_json`` が未指定のときは必須です。",
    )

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON],
        default=FormatArgument.CSV,
    )

    argument_parser.add_output()

    parser.add_argument(
        "--latest",
        action="store_true",
        help="入力データ情報とタスク情報の最新版を参照します。このオプションを指定すると数分待ちます。",
    )

    parser.add_argument(
        "--temp_dir",
        type=Path,
        help="指定したディレクトリに、入力データのJSONやタスクのJSONなどテンポラリファイルをダウンロードします。",
    )

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListVideoDuration(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_video_duration"
    subcommand_help = "各タスクの動画の長さを出力します。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
