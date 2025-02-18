from __future__ import annotations

import argparse
import json
import logging
import multiprocessing
import sys
from dataclasses import dataclass
from functools import partial
from typing import Any, Optional

import annofabapi
import more_itertools
from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)

Metadata = dict[str, str]
"""
入力データのメタデータ。
値はstr型しか指定できない。
"""


@dataclass(frozen=True)
class InputDataMetadataInfo:
    input_data_id: str
    metadata: Metadata


class UpdateMetadataMain(CommandLineWithConfirm):
    def __init__(
        self, service: annofabapi.Resource, *, src_project_id: str, dest_project_id: str, should_overwrite: bool, all_yes: bool = False
    ) -> None:
        self.service = service
        self.src_project_id = src_project_id
        self.dest_project_id = dest_project_id
        self.should_overwrite = should_overwrite
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
    ) -> dict[str, Any]:
        for src_supplementary_data in src_supplementary_data_list:
            dest_supplementary_data = more_itertools.first_true(
                dest_supplementary_data_list, pred=lambda e: e["supplementary_data_id"] == src_supplementary_data["supplementary_data_id"]
            )
            last_updated_datetime_for_supplementary_data = (
                dest_supplementary_data["updated_datetime"] if dest_supplementary_data is not None else None
            )
            self.copy_supplementary_data(src_supplementary_data, last_updated_datetime=last_updated_datetime_for_supplementary_data)
            logger.debug(
                f"{logging_prefix}補助情報をコピーしました。 :: input_data_id='{src_supplementary_data['input_data_id']}', supplementary_data_id='{src_supplementary_data['supplementary_data_id']}', supplementary_data_name='{src_supplementary_data['supplementary_data_name']}', src_project_id='{self.src_project_id}', dest_project_id='{self.dest_project_id}'"
            )

        logger.debug(
            f"{logging_prefix}補助情報を{len(src_supplementary_data_list)}件コピーしました。 :: input_data_id='{src_supplementary_data_list[0]['input_data_id']}', src_project_id='{self.src_project_id}', dest_project_id='{self.dest_project_id}'"
        )

    def copy_foo(self, src_input_data: dict[str, Any], last_updated_datetime: Optional[str]):
        request_body = {
            "input_data_name": src_input_data["input_data_name"],
            "input_data_path": src_input_data["input_data_path"],
            "last_updated_datetime": last_updated_datetime,
            "sign_required": src_input_data["sign_required"],
            "metadata": src_input_data["metadata"],
        }
        content, _ = self.service.api.put_input_data(self.dest_project_id, request_body=request_body)

    def copy_input_data(
        self,
        src_project_id: str,
        input_data_id: str,
        *,
        should_overwrite: bool = False,
        input_data_index: Optional[int] = None,
    ):
        def get_confirm_message(exists_in_dest_project: bool, supplementary_data_count: int) -> str:
            message = f"入力データ(input_data_id='{input_data_id}')と補助情報{supplementary_data_count}件をコピーしますか？"
            if exists_in_dest_project:
                message += "コピー先プロジェクトにすでに入力データが存在します。"
            message += f" :: input_data_id='{input_data_id}', src_project_id='{src_project_id}', dest_project_id='{self.dest_project_id}'"

        logging_prefix = f"{input_data_index + 1} 件目" if input_data_index is not None else ""

        src_input_data = self.service.wrapper.get_input_data_or_none(src_project_id, input_data_id)
        if src_input_data is None:
            logger.warning(f"{logging_prefix}入力データは存在しないのでコピーをスキップします。 :: input_data_id='{input_data_id}'")
            return False

        src_supplementary_data_list, _ = self.service.api.get_supplementary_data_list(src_project_id, input_data_id)

        input_data_name = src_input_data["input_data_name"]
        dest_input_data = self.service.wrapper.get_input_data_or_none(self.dest_project_id, input_data_id)
        if dest_input_data is not None and not self.should_overwrite:
            logger.debug(
                f"{logging_prefix}入力データはコピー先プロジェクトにすでに存在するので、コピーをスキップします。 :: input_data_id='{input_data_id}', input_data_name='{input_data_name}', src_project_id='{src_project_id}', dest_project_id='{self.dest_project_id}'"
            )
            return False

        if not self.confirm_processing(get_confirm_message(dest_input_data is not None), len(src_supplementary_data_list)):
            return False

        last_updated_datetime = dest_input_data["updated_datetime"] if dest_input_data is not None else None
        self.copy_foo(src_input_data, last_updated_datetime=last_updated_datetime)

        logger.debug(
            f"{logging_prefix}入力データをコピーしました。 :: input_data_id='{input_data_id}', input_data_name='{input_data_name}', src_project_id='{src_project_id}', dest_project_id='{self.dest_project_id}'"
        )

        if dest_input_data is not None:
            dest_supplementary_data_list, _ = self.service.api.get_supplementary_data_list(self.dest_project_id, input_data_id)
        else:
            dest_supplementary_data_list = []

        for src_supplementary_data in src_supplementary_data_list:
            dest_supplementary_data = more_itertools.first_true(
                dest_supplementary_data_list, pred=lambda e: e["supplementary_data_id"] == src_supplementary_data["supplementary_data_id"]
            )
            last_updated_datetime_for_supplementary_data = (
                dest_supplementary_data["updated_datetime"] if dest_supplementary_data is not None else None
            )
            self.copy_supplementary_data(src_supplementary_data, last_updated_datetime=last_updated_datetime_for_supplementary_data)
        logger.debug(
            f"{logging_prefix}入力データをコピーしました。 :: input_data_id='{input_data_id}', input_data_name='{input_data_name}', src_project_id='{src_project_id}', dest_project_id='{self.dest_project_id}'"
        )

        return True

    def set_metadata_to_input_data(
        self,
        project_id: str,
        input_data_id: str,
        metadata: Metadata,
        *,
        overwrite_metadata: bool = False,
        input_data_index: Optional[int] = None,
    ) -> bool:
        def get_confirm_message() -> str:
            if overwrite_metadata:
                return f"入力データ(input_data_id='{input_data_id}')のメタデータを'{json.dumps(metadata)}'に変更しますか？ "
            else:
                return f"入力データ(input_data_id='{input_data_id}')のメタデータに'{json.dumps(metadata)}'を追加しますか？ "

        logging_prefix = f"{input_data_index + 1} 件目" if input_data_index is not None else ""

        input_data = self.service.wrapper.get_input_data_or_none(project_id, input_data_id)
        if input_data is None:
            logger.warning(f"{logging_prefix} 入力データは存在しないのでスキップします。input_data_id={input_data_id}")
            return False

        logger.debug(
            f"{logging_prefix} input_data_id='{input_data['input_data_id']}', "
            f"input_data_name='{input_data['input_data_name']}', metadata='{json.dumps(input_data['metadata'])}'"
        )
        if not self.confirm_processing(get_confirm_message()):
            return False

        input_data["last_updated_datetime"] = input_data["updated_datetime"]
        if overwrite_metadata:
            input_data["metadata"] = metadata
        else:
            input_data["metadata"].update(metadata)

        self.service.api.put_input_data(project_id, input_data_id, request_body=input_data)
        logger.debug(f"{logging_prefix} 入力データのメタデータを更新しました。input_data_id='{input_data['input_data_id']}'")
        return True

    def set_metadata_to_input_data_wrapper(
        self, tpl: tuple[int, InputDataMetadataInfo], project_id: str, *, overwrite_metadata: bool = False
    ) -> bool:
        input_data_index, info = tpl
        return self.set_metadata_to_input_data(
            project_id,
            info.input_data_id,
            metadata=info.metadata,
            overwrite_metadata=overwrite_metadata,
            input_data_index=input_data_index,
        )

    def update_metadata_of_input_data(
        self,
        project_id: str,
        metadata_by_input_data_id: dict[str, Metadata],
        *,
        overwrite_metadata: bool = False,
        parallelism: Optional[int] = None,
    ) -> None:
        metadata_info_list = [InputDataMetadataInfo(input_data_id, metadata) for input_data_id, metadata in metadata_by_input_data_id.items()]
        if overwrite_metadata:
            logger.info(f"{len(metadata_info_list)} 件の入力データのメタデータを変更します（上書き）。")
        else:
            logger.info(f"{len(metadata_info_list)} 件の入力データのメタデータを変更します（追記）。")

        success_count = 0

        if parallelism is not None:
            partial_func = partial(
                self.set_metadata_to_input_data_wrapper,
                project_id=project_id,
                overwrite_metadata=overwrite_metadata,
            )
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(partial_func, enumerate(metadata_info_list))
                success_count = len([e for e in result_bool_list if e])

        else:
            # 逐次処理
            for input_data_index, info in enumerate(metadata_info_list):
                result = self.set_metadata_to_input_data(
                    project_id,
                    info.input_data_id,
                    metadata=info.metadata,
                    overwrite_metadata=overwrite_metadata,
                    input_data_index=input_data_index,
                )
                if result:
                    success_count += 1

        logger.info(f"{success_count} / {len(metadata_info_list)} 件の入力データのmetadataを変更しました。")


def validate_metadata(metadata: Metadata) -> bool:
    """
    メタデータの値を検証します。
    * メタデータの値がstr型であること
    """
    return all(isinstance(value, str) for value in metadata.values())


class UpdateMetadata(CommandLine):
    COMMON_MESSAGE = "annofabcli input_data update_metadata: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず ``--yes`` を指定してください。",
                file=sys.stderr,
            )
            return False

        if args.metadata is not None and args.input_data_id is None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --input_data_id: '--metadata' を指定するときは、 '--input_data_id' が必須です。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        input_data_id_list = annofabcli.common.cli.get_list_from_args(args.input_data_id) if args.input_data_id is not None else None

        if args.metadata is not None:
            metadata = annofabcli.common.cli.get_json_from_args(args.metadata)
            if not validate_metadata(metadata):
                print(  # noqa: T201
                    f"{self.COMMON_MESSAGE} argument --metadata: メタデータは不正な形式です。メタデータの値は文字列である必要があります。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

            assert input_data_id_list is not None, "'--metadata'を指定したときは'--input_data_id'は必須です。"
            metadata_by_input_data_id = {input_data_id: metadata for input_data_id in input_data_id_list}

        elif args.metadata_by_input_data_id is not None:
            metadata_by_input_data_id = annofabcli.common.cli.get_json_from_args(args.metadata_by_input_data_id)

            input_data_ids_containing_invalid_metadata = []
            for input_data_id, metadata in metadata_by_input_data_id.items():
                if not validate_metadata(metadata):
                    input_data_ids_containing_invalid_metadata.append(input_data_id)

            if len(input_data_ids_containing_invalid_metadata) > 0:
                print(  # noqa: T201
                    f"{self.COMMON_MESSAGE} argument --metadata: 以下の入力データIDに対応するメタデータは不正な形式です。"
                    f"メタデータの値は文字列である必要があります。 :: {input_data_ids_containing_invalid_metadata}",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

            if input_data_id_list is not None:
                metadata_by_input_data_id = {
                    input_data_id: metadata for input_data_id, metadata in metadata_by_input_data_id.items() if input_data_id in input_data_id_list
                }
        else:
            raise RuntimeError("'--metadata'か'--metadata_by_input_data_id'のどちらかを指定する必要があります。")

        super().validate_project(args.project_id, [ProjectMemberRole.OWNER])
        main_obj = UpdateMetadataMain(self.service, all_yes=args.yes)
        main_obj.update_metadata_of_input_data(
            args.project_id,
            metadata_by_input_data_id=metadata_by_input_data_id,
            overwrite_metadata=args.overwrite,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateMetadata(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    argument_parser.add_project_id()
    argument_parser.add_input_data_id(required=False)

    parser.add_argument(
        "--dest_project_id",
        type=str,
        help=("コピー先のプロジェクトのproject_id"),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="コピー先プロジェクトにすでに入力データが存在する場合、入力データを更新します。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",  # noqa: E501
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "copy"
    subcommand_help = "入力データと関連する補助情報をコピーします。"
    epilog = "コピー先プロジェクトに対してオーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
