import argparse
import logging
import sys
import uuid
import zipfile
from pathlib import Path
from typing import Optional

from annofabapi.models import ProjectJobType, ProjectMemberRole

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)


class PutInputData(AbstractCommandLineInterface):
    """
    入力データをZIPで登録する。
    """

    COMMON_MESSAGE = "annofabcli input_data put_with_zip: error:"

    def put_input_data_from_zip_file(
        self,
        project_id: str,
        zip_file: Path,
        wait_options: WaitOptions,
        input_data_name_prefix: Optional[str] = None,
        wait: bool = False,
    ) -> None:
        """
        zipファイルを入力データとして登録する

        Args:
            project_id: 入力データの登録先プロジェクトのプロジェクトID
            zip_file: 入力データとして登録するzipファイルのパス
            input_data_name_prefix: zipファイルのinput_data_name
            wait: 入力データの登録が完了するまで待つかどうか

        """

        project_title = self.facade.get_project_title(project_id)
        logger.info(f"{project_title} に、{str(zip_file)} を登録します。")

        request_body = {}
        if input_data_name_prefix is not None:
            request_body["input_data_name"] = input_data_name_prefix

        self.service.wrapper.put_input_data_from_file(
            project_id,
            input_data_id=str(uuid.uuid4()),
            file_path=str(zip_file),
            content_type="application/zip",
            request_body=request_body,
        )
        logger.info(f"入力データの登録中です（サーバ側の処理）。")

        if wait:
            MAX_WAIT_MINUTE = wait_options.max_tries * wait_options.interval / 60
            logger.info(f"最大{MAX_WAIT_MINUTE}分間、処理が終了するまで待ちます。")

            result = self.service.wrapper.wait_for_completion(
                project_id,
                job_type=ProjectJobType.GEN_INPUTS,
                job_access_interval=wait_options.interval,
                max_job_access=wait_options.max_tries,
            )
            if result:
                logger.info(f"入力データの登録が完了しました。")
            else:
                logger.warning(f"入力データの登録に失敗しました。または、{MAX_WAIT_MINUTE}分間待っても、入力データの登録が完了しませんでした。")

    def validate(self, args: argparse.Namespace) -> bool:
        if args.zip is not None:
            if not Path(args.zip).exists():
                print(f"{self.COMMON_MESSAGE} argument --zip: ファイルパスが存在しません。 '{args.zip}'", file=sys.stderr)
                return False

            if not zipfile.is_zipfile(args.zip):
                print(f"{self.COMMON_MESSAGE} argument --zip: zipファイルではありません。 '{args.zip}'", file=sys.stderr)
                return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER])
        if args.zip is not None:
            wait_options = DEFAULT_WAIT_OPTIONS
            self.put_input_data_from_zip_file(
                project_id,
                zip_file=args.zip,
                input_data_name_prefix=args.input_data_name_prefix,
                wait=args.wait,
                wait_options=wait_options,
            )

        else:
            print(f"引数が不正です。", file=sys.stderr)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PutInputData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument("--zip", type=Path, help=("入力データとして登録するzipファイルのパスを指定してください。"))

    parser.add_argument(
        "--input_data_name_prefix",
        type=str,
        help="入力データとして登録するzipファイルのinput_data_nameを指定してください。省略した場合、 ``--zip`` のパスになります。",
    )

    parser.add_argument("--wait", action="store_true", help=("入力データの登録が完了するまで待ちます。"))

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "put_with_zip"
    subcommand_help = "zipファイルを入力データとして登録します。"
    description = "zipファイルを入力データとして登録します。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
