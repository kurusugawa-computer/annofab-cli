from __future__ import annotations

import argparse
import json
import logging
import multiprocessing
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

import annofabapi
import more_itertools
from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class CopyInputDataMain(CommandLineWithConfirm):
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        src_project_id: str,
        dest_project_id: str,
        should_overwrite: bool,
        all_yes: bool = False,
    ) -> None:
        self.service = service
        self.src_project_id = src_project_id
        self.dest_project_id = dest_project_id
        self.should_overwrite = should_overwrite

        src_project, _ = service.api.get_project(src_project_id)
        self.src_project_title = src_project["title"]
        dest_project, _ = service.api.get_project(dest_project_id)
        self.dest_project_title = dest_project["title"]

        CommandLineWithConfirm.__init__(self, all_yes)

    def copy_supplementary_data(self, src_supplementary_data: dict[str, Any], last_updated_datetime: Optional[str]) -> dict[str, Any]:
        request_body = {
            "supplementary_data_name": src_supplementary_data["supplementary_data_name"],
            "supplementary_data_path": src_supplementary_data["supplementary_data_path"],
            "supplementary_data_type": src_supplementary_data["supplementary_data_type"],
            "supplementary_data_number": src_supplementary_data["supplementary_data_number"],
            "last_updated_datetime": last_updated_datetime,
        }
        new_supplementary_data, _ = self.service.api.put_supplementary_data(
            self.dest_project_id,
            input_data_id=src_supplementary_data["input_data_id"],
            supplementary_data_id=src_supplementary_data["supplementary_data_id"],
            request_body=request_body,
        )
        return new_supplementary_data

    def copy_supplementary_data_list(
        self,
        src_supplementary_data_list: list[dict[str, Any]],
        dest_supplementary_data_list: list[dict[str, Any]],
        *,
        logging_prefix: Optional[str] = None,
    ) -> None:
        for src_supplementary_data in src_supplementary_data_list:
            dest_supplementary_data = more_itertools.first_true(
                dest_supplementary_data_list,
                pred=lambda e, s=src_supplementary_data: e["supplementary_data_id"] == s["supplementary_data_id"],  # type: ignore[misc]
            )
            last_updated_datetime_for_supplementary_data = dest_supplementary_data["updated_datetime"] if dest_supplementary_data is not None else None
            self.copy_supplementary_data(src_supplementary_data, last_updated_datetime=last_updated_datetime_for_supplementary_data)
            logger.debug(
                f"{logging_prefix}補助情報をコピーしました。 :: "
                f"input_data_id='{src_supplementary_data['input_data_id']}', "
                f"supplementary_data_id='{src_supplementary_data['supplementary_data_id']}', "
                f"supplementary_data_name='{src_supplementary_data['supplementary_data_name']}', "
                f"src_project_id='{self.src_project_id}', dest_project_id='{self.dest_project_id}'"
            )

        logger.debug(
            f"{logging_prefix}補助情報を{len(src_supplementary_data_list)}件コピーしました。 :: "
            f"input_data_id='{src_supplementary_data_list[0]['input_data_id']}', "
            f"src_project_id='{self.src_project_id}', dest_project_id='{self.dest_project_id}'"
        )

    def copy_input_data(self, src_input_data: dict[str, Any], last_updated_datetime: Optional[str]) -> dict[str, Any]:
        request_body = {
            "input_data_name": src_input_data["input_data_name"],
            "input_data_path": src_input_data["input_data_path"],
            "last_updated_datetime": last_updated_datetime,
            "sign_required": src_input_data["sign_required"],
            "metadata": src_input_data["metadata"],
        }
        new_input_data, _ = self.service.api.put_input_data(self.dest_project_id, src_input_data["input_data_id"], request_body=request_body)
        return new_input_data

    def copy_input_data_and_supplementary_data(
        self,
        input_data_id: str,
        *,
        input_data_index: Optional[int] = None,
    ) -> bool:
        def get_confirm_message(supplementary_data_count: int, *, exists_in_dest_project: bool) -> str:
            message = f"入力データ(input_data_id='{input_data_id}')と補助情報{supplementary_data_count}件をコピーしますか？"
            if exists_in_dest_project:
                message += "コピー先プロジェクトにすでに入力データが存在します。"
            message += f" :: input_data_id='{input_data_id}', src_project_id='{self.src_project_id}', dest_project_id='{self.dest_project_id}'"
            return message

        logging_prefix = f"{input_data_index + 1} 件目 :: " if input_data_index is not None else ""

        src_input_data = self.service.wrapper.get_input_data_or_none(self.src_project_id, input_data_id)
        if src_input_data is None:
            logger.warning(f"{logging_prefix}入力データは存在しないのでコピーをスキップします。 :: input_data_id='{input_data_id}'")
            return False

        input_data_name = src_input_data["input_data_name"]
        dest_input_data = self.service.wrapper.get_input_data_or_none(self.dest_project_id, input_data_id)
        if dest_input_data is not None and not self.should_overwrite:
            logger.debug(
                f"{logging_prefix}入力データはコピー先プロジェクトにすでに存在するので、コピーをスキップします。 :: "
                f"input_data_id='{input_data_id}', input_data_name='{input_data_name}', "
                f"src_project_id='{self.src_project_id}', dest_project_id='{self.dest_project_id}'"
            )
            return False

        src_supplementary_data_list, _ = self.service.api.get_supplementary_data_list(self.src_project_id, input_data_id)
        if not self.confirm_processing(get_confirm_message(len(src_supplementary_data_list), exists_in_dest_project=dest_input_data is not None)):
            return False

        last_updated_datetime = dest_input_data["updated_datetime"] if dest_input_data is not None else None
        self.copy_input_data(src_input_data, last_updated_datetime=last_updated_datetime)

        logger.debug(
            f"{logging_prefix}入力データをコピーしました。 :: "
            f"input_data_id='{input_data_id}', input_data_name='{input_data_name}', "
            f"src_project_id='{self.src_project_id}', dest_project_id='{self.dest_project_id}'"
        )

        if len(src_supplementary_data_list) > 0:
            # 補助情報が存在する場合は、補助情報もコピーする
            if dest_input_data is not None:
                dest_supplementary_data_list, _ = self.service.api.get_supplementary_data_list(self.dest_project_id, input_data_id)
            else:
                dest_supplementary_data_list = []

            self.copy_supplementary_data_list(src_supplementary_data_list, dest_supplementary_data_list, logging_prefix=logging_prefix)

        return True

    def copy_input_data_and_supplementary_data_wrapper(self, tpl: tuple[int, str]) -> bool:
        input_data_index, input_data_id = tpl
        try:
            return self.copy_input_data_and_supplementary_data(
                input_data_id,
                input_data_index=input_data_index,
            )
        except Exception:
            logger.warning(
                f"入力データのコピーに失敗しました。 :: input_data_id='{input_data_id}', src_project_id='{self.src_project_id}', dest_project_id='{self.dest_project_id}'",
                exc_info=True,
            )
            return False

    def get_all_input_data_id_list(self, project_id: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_data_json = Path(tmp_dir) / f"{project_id}_input_data.json"
            self.service.wrapper.download_project_inputs_url(project_id, dest_path=input_data_json)
            input_data_list = json.loads(input_data_json.read_text())
        return [e["input_data_id"] for e in input_data_list]

    def copy_input_data_list(
        self,
        input_data_id_list: Optional[list[str]],
        *,
        parallelism: Optional[int] = None,
    ) -> None:
        if input_data_id_list is None:
            input_data_id_list = self.get_all_input_data_id_list(self.src_project_id)

        logger.info(
            f"プロジェクト'{self.src_project_title}'配下の{len(input_data_id_list)} 件の入力データと関連する補助情報を、"
            f"プロジェクト'{self.dest_project_title}'にコピーします。 :: "
            f"src_project_id='{self.src_project_id}', dest_project_id='{self.dest_project_id}'"
        )

        if parallelism is not None:
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(self.copy_input_data_and_supplementary_data_wrapper, enumerate(input_data_id_list))
                success_count = len([e for e in result_bool_list if e])

        else:
            # 逐次処理
            success_count = 0
            for input_data_index, input_data_id in enumerate(input_data_id_list):
                try:
                    result = self.copy_input_data_and_supplementary_data(input_data_id, input_data_index=input_data_index)
                    if result:
                        success_count += 1
                except Exception:
                    logger.warning(
                        f"入力データのコピーに失敗しました。 :: input_data_id='{input_data_id}', src_project_id='{self.src_project_id}', dest_project_id='{self.dest_project_id}'",
                        exc_info=True,
                    )

        logger.info(
            f"{success_count} / {len(input_data_id_list)} 件の入力データと関連する補助情報をコピーしました。 :: src_project_id='{self.src_project_id}', dest_project_id='{self.dest_project_id}'"
        )


class CopyInputData(CommandLine):
    COMMON_MESSAGE = "annofabcli input_data copy: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず ``--yes`` を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        input_data_id_list = annofabcli.common.cli.get_list_from_args(args.input_data_id) if args.input_data_id is not None else None

        src_project_id = args.src_project_id
        dest_project_id = args.dest_project_id

        super().validate_project(dest_project_id, [ProjectMemberRole.OWNER])
        main_obj = CopyInputDataMain(
            self.service,
            src_project_id=src_project_id,
            dest_project_id=dest_project_id,
            should_overwrite=args.overwrite,
            all_yes=args.yes,
        )
        main_obj.copy_input_data_list(input_data_id_list, parallelism=args.parallelism)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CopyInputData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--src_project_id",
        type=str,
        required=True,
        help="コピー元プロジェクトのproject_id",
    )

    parser.add_argument(
        "--dest_project_id",
        type=str,
        required=True,
        help="コピー先プロジェクトのproject_id",
    )

    parser.add_argument(
        "-i",
        "--input_data_id",
        type=str,
        nargs="+",
        required=False,
        help="コピー対象の入力データのinput_data_idを指定します。 ``file://`` を先頭に付けると、input_data_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="コピー先プロジェクトにすでに入力データが存在する場合、入力データを更新してコピーします。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "copy"
    subcommand_help = "入力データと関連する補助情報を別プロジェクトにコピーします。"
    description = (
        "入力データと関連する補助情報を別プロジェクトにコピーします。\n"
        "【注意】プライベートストレージを参照している入力データをコピーできます。"
        "Annofabストレージを参照している入力データはコピーできません。"
        "コピー先プロジェクトは、プライベートストレージが利用可能である必要があります。"
    )

    epilog = "コピー先プロジェクトに対してオーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog)
    parse_args(parser)
    return parser
