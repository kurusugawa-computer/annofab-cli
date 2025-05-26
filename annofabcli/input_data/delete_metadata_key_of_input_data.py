from __future__ import annotations

import argparse
import copy
import json
import logging
import multiprocessing
import sys
from collections.abc import Collection
from functools import partial
from typing import Optional

import annofabapi
from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
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


class DeleteMetadataKeyOfInputDataMain(CommandLineWithConfirm):
    def __init__(self, service: annofabapi.Resource, project_id: str, *, all_yes: bool = False) -> None:
        self.service = service
        self.project_id = project_id
        super().__init__(all_yes=all_yes)

    def delete_metadata_keys_for_one_input_data(self, input_data_id: str, metadata_keys: Collection[str], *, input_data_index: Optional[int] = None) -> bool:
        """
        １個の入力データに対して、メタデータのキーを削除します。

        Args:
            input_data_id:
            metadata_keys: 削除するメタデータのキー

        Returns:
            メタデータのキーを削除した場合はTrueを返します。
        """
        logging_prefix = f"{input_data_index + 1} 件目" if input_data_index is not None else ""
        input_data = self.service.wrapper.get_input_data_or_none(self.project_id, input_data_id)
        if input_data is None:
            logger.warning(f"{logging_prefix} input_data_id='{input_data_id}'である入力データは存在しません。")
            return False

        old_metadata = input_data["metadata"]
        input_data_name = input_data["input_data_name"]
        str_old_metadata = json.dumps(old_metadata)
        deleted_keys = set(metadata_keys) & set(old_metadata.keys())  # 削除可能な（存在する）メタデータのキー
        logger.debug(f"{logging_prefix} input_data_id='{input_data_id}', input_data_name='{input_data_name}', metadata='{str_old_metadata}' :: 削除対象のキーが {len(deleted_keys)} 件存在します。")

        if len(deleted_keys) == 0:
            # メタデータを更新する必要がないのでreturnします。
            return False

        new_metadata = copy.deepcopy(old_metadata)
        for key in deleted_keys:
            new_metadata.pop(key, None)

        if not self.all_yes and not self.confirm_processing(
            f"input_data_id='{input_data_id}', input_data_name='{input_data_name}' :: metadata='{str_old_metadata}' からキー'{deleted_keys}'を削除しますか？"
        ):
            return False

        input_data.update(
            {
                "last_updated_datetime": input_data["updated_datetime"],
                "metadata": new_metadata,
            }
        )

        self.service.api.put_input_data(self.project_id, input_data_id, request_body=input_data)
        str_new_metadata = json.dumps(new_metadata)
        logger.debug(f"{logging_prefix} input_data_id='{input_data_id}' :: 入力データのメタデータからキー'{deleted_keys}'を削除しました。 :: metadata='{str_new_metadata}'")
        return True

    def delete_metadata_keys_for_one_input_data_wrapper(self, tpl: tuple[int, str], metadata_keys: Collection[str]) -> bool:
        input_data_index, input_data_id = tpl
        try:
            return self.delete_metadata_keys_for_one_input_data(
                input_data_id=input_data_id,
                metadata_keys=metadata_keys,
                input_data_index=input_data_index,
            )
        except Exception:
            logger.warning(f"input_data_id='{input_data_id}' :: 入力データのメタデータのキーを削除するのに失敗しました。", exc_info=True)
            return False

    def delete_metadata_keys_for_input_data_list(self, input_data_id_list: list[str], metadata_keys: Collection[str], *, parallelism: Optional[int] = None) -> None:
        logger.info(f"{len(input_data_id_list)} 件の入力データのメタデータから、キー'{metadata_keys}'を削除します。")

        success_count = 0
        if parallelism is not None:
            assert self.all_yes
            partial_func = partial(
                self.delete_metadata_keys_for_one_input_data_wrapper,
                metadata_keys=metadata_keys,
            )
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(partial_func, enumerate(input_data_id_list))
                success_count = len([e for e in result_bool_list if e])

        else:
            # 逐次処理
            for input_data_index, input_data_id in enumerate(input_data_id_list):
                try:
                    result = self.delete_metadata_keys_for_one_input_data(
                        input_data_id,
                        metadata_keys=metadata_keys,
                        input_data_index=input_data_index,
                    )
                    if result:
                        success_count += 1
                except Exception:
                    logger.warning(f"input_data_id='{input_data_id}' :: 入力データのメタデータのキーを削除するのに失敗しました。", exc_info=True)
                    continue

        logger.info(f"{success_count} / {len(input_data_id_list)} 件の入力データのメタデータから、キー'{metadata_keys}'を削除しました。")


class DeleteMetadataKeyOfInputData(CommandLine):
    COMMON_MESSAGE = "annofabcli input_data delete_metadata_key: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism' を指定するときは、 '--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        input_data_id_list = annofabcli.common.cli.get_list_from_args(args.input_data_id)
        metadata_keys = annofabcli.common.cli.get_list_from_args(args.metadata_key)

        super().validate_project(args.project_id, [ProjectMemberRole.OWNER])
        main_obj = DeleteMetadataKeyOfInputDataMain(self.service, project_id=args.project_id, all_yes=args.yes)
        main_obj.delete_metadata_keys_for_input_data_list(
            input_data_id_list=input_data_id_list,
            metadata_keys=metadata_keys,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteMetadataKeyOfInputData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    argument_parser.add_input_data_id(required=True)

    parser.add_argument("--metadata_key", type=str, nargs="+", required=True, help="削除するメタデータのキーを指定します。")

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定します。指定する場合は ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "delete_metadata_key"
    subcommand_help = "入力データのメタデータのキーを削除します。"
    epilog = "オーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
