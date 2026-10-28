from __future__ import annotations

import argparse
import json
import logging
import multiprocessing
import sys
from dataclasses import dataclass
from functools import partial
from typing import Any

import annofabapi
from annofabapi.models import ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.annofab.input_data import BULK_REQUEST_SIZE, get_input_data_dict_in_bulk
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.input_data.utils import validate_metadata
from annofabcli.utils.iterables import batched

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
    def __init__(self, service: annofabapi.Resource, *, all_yes: bool = False) -> None:
        self.service = service
        CommandLineWithConfirm.__init__(self, all_yes)

    def set_metadata_to_input_data(
        self,
        project_id: str,
        input_data_id: str,
        metadata: Metadata,
        *,
        overwrite_metadata: bool = False,
        input_data_index: int | None = None,
        existing_input_data_dict: dict[str, dict[str, Any]] | None = None,
    ) -> bool:
        def get_confirm_message() -> str:
            if overwrite_metadata:
                return f"入力データ(input_data_id='{input_data_id}')のメタデータを'{json.dumps(metadata)}'に変更しますか？ "
            else:
                return f"入力データ(input_data_id='{input_data_id}')のメタデータに'{json.dumps(metadata)}'を追加しますか？ "

        logging_prefix = f"{input_data_index + 1} 件目" if input_data_index is not None else ""

        input_data = existing_input_data_dict.get(input_data_id) if existing_input_data_dict is not None else self.service.wrapper.get_input_data_or_none(project_id, input_data_id)
        if input_data is None:
            logger.warning(f"{logging_prefix} 入力データは存在しないのでスキップします。 :: input_data_id='{input_data_id}'")
            return False

        logger.debug(f"{logging_prefix} input_data_id='{input_data['input_data_id']}', input_data_name='{input_data['input_data_name']}', metadata='{json.dumps(input_data['metadata'])}'")
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
        self, tpl: tuple[int, InputDataMetadataInfo], project_id: str, *, overwrite_metadata: bool = False, existing_input_data_dict: dict[str, dict[str, Any]] | None = None
    ) -> bool:
        input_data_index, info = tpl
        return self.set_metadata_to_input_data(
            project_id,
            info.input_data_id,
            metadata=info.metadata,
            overwrite_metadata=overwrite_metadata,
            input_data_index=input_data_index,
            existing_input_data_dict=existing_input_data_dict,
        )

    def update_metadata_of_input_data(
        self,
        project_id: str,
        metadata_by_input_data_id: dict[str, Metadata],
        *,
        overwrite_metadata: bool = False,
        parallelism: int | None = None,
    ) -> None:
        metadata_info_list = [InputDataMetadataInfo(input_data_id, metadata) for input_data_id, metadata in metadata_by_input_data_id.items()]
        if overwrite_metadata:
            logger.info(f"{len(metadata_info_list)} 件の入力データのメタデータを変更します（上書き）。")
        else:
            logger.info(f"{len(metadata_info_list)} 件の入力データのメタデータを変更します（追記）。")

        success_count = 0
        if parallelism is not None:
            with multiprocessing.Pool(parallelism) as pool:
                for initial_index, batch_metadata_info_list in enumerate(batched(metadata_info_list, BULK_REQUEST_SIZE)):
                    existing_input_data_dict = get_input_data_dict_in_bulk(self.service, project_id, [e.input_data_id for e in batch_metadata_info_list])
                    partial_func = partial(
                        self.set_metadata_to_input_data_wrapper,
                        project_id=project_id,
                        overwrite_metadata=overwrite_metadata,
                        existing_input_data_dict=existing_input_data_dict,
                    )
                    result_bool_list = pool.map(partial_func, enumerate(batch_metadata_info_list, start=initial_index * BULK_REQUEST_SIZE))
                    success_count += len([e for e in result_bool_list if e])

        else:
            # 逐次処理
            for initial_index, batch_metadata_info_list in enumerate(batched(metadata_info_list, BULK_REQUEST_SIZE)):
                existing_input_data_dict = get_input_data_dict_in_bulk(self.service, project_id, [e.input_data_id for e in batch_metadata_info_list])
                for input_data_index, info in enumerate(batch_metadata_info_list, start=initial_index * BULK_REQUEST_SIZE):
                    result = self.set_metadata_to_input_data(
                        project_id,
                        info.input_data_id,
                        metadata=info.metadata,
                        overwrite_metadata=overwrite_metadata,
                        input_data_index=input_data_index,
                        existing_input_data_dict=existing_input_data_dict,
                    )
                    if result:
                        success_count += 1

        logger.info(f"{success_count} / {len(metadata_info_list)} 件の入力データのmetadataを変更しました。")


def get_input_data_metadata_info_list_from_json_args(json_value: str) -> list[InputDataMetadataInfo]:
    """JSON引数から入力データごとのメタデータ更新情報を取得します。

    Args:
        json_value: ``input_data list --format json`` と同じ形式のJSON文字列、またはJSONファイルのパス

    Returns:
        入力データごとのメタデータ更新情報

    Raises:
        TypeError: JSONの形式が不正な場合
        ValueError: input_data_idが重複している場合
    """

    input_data_list = annofabcli.common.cli.get_json_from_args(json_value)
    if not isinstance(input_data_list, list):
        raise TypeError("配列を指定してください。")

    result: list[InputDataMetadataInfo] = []
    input_data_id_set: set[str] = set()
    for index, input_data in enumerate(input_data_list, start=1):
        if not isinstance(input_data, dict):
            raise TypeError(f"{index}番目の要素にはオブジェクトを指定してください。")

        try:
            input_data_id = input_data["input_data_id"]
            metadata = input_data["metadata"]
        except KeyError as e:
            raise TypeError(f"{index}番目の要素には 'input_data_id' と 'metadata' キーを指定してください。") from e

        if not isinstance(input_data_id, str):
            raise TypeError(f"{index}番目の要素の'input_data_id'には文字列を指定してください。")
        if not isinstance(metadata, dict):
            raise TypeError(f"{index}番目の要素の'metadata'にはオブジェクトを指定してください。")
        if input_data_id in input_data_id_set:
            raise ValueError(f"{index}番目の要素の'input_data_id'が重複しています。 :: input_data_id='{input_data_id}'")

        input_data_id_set.add(input_data_id)
        result.append(InputDataMetadataInfo(input_data_id=input_data_id, metadata=metadata))

    return result


class UpdateMetadataPerInputData(CommandLine):
    """入力データごとに指定したメタデータを更新する。"""

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                "annofabcli input_data update_metadata_per_input_data: error: argument --parallelism: '--parallelism' を指定するときは、 '--yes' が必須です。",
                file=sys.stderr,
            )
            return False
        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        metadata_info_list = get_input_data_metadata_info_list_from_json_args(args.json)
        metadata_by_input_data_id = {info.input_data_id: info.metadata for info in metadata_info_list}
        input_data_ids_containing_invalid_metadata = [input_data_id for input_data_id, metadata in metadata_by_input_data_id.items() if not validate_metadata(metadata)]
        if input_data_ids_containing_invalid_metadata:
            print(  # noqa: T201
                "annofabcli input_data update_metadata_per_input_data: error: argument --json: "
                "以下の入力データIDに対応するメタデータは不正な形式です。"
                "メタデータの値は文字列である必要があります。 :: "
                f"{input_data_ids_containing_invalid_metadata}",
                file=sys.stderr,
            )
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        super().require_project_access(args.project_id, [ProjectMemberRole.OWNER])
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
    UpdateMetadataPerInputData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    sample_json = [{"input_data_id": "input_data1", "metadata": {"country": "japan"}}]
    parser.add_argument(
        "--json",
        type=str,
        required=True,
        help=(
            "``input_data list --format json`` と同じ形式のJSON配列を指定してください。"
            "各要素の ``input_data_id`` と ``metadata`` キーを参照し、それ以外のキーは無視します。"
            "メタデータの値は文字列です。\n"
            f"(ex) '{json.dumps(sample_json)}'\n"
            "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="指定した場合、メタデータを上書きして更新します（すでに設定されているメタデータは削除されます）。指定しない場合、JSONに指定されたキーのみ更新されます。",
    )
    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )
    parser.set_defaults(subcommand_func=main)


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "update_metadata_per_input_data"
    subcommand_help = "入力データごとにメタデータを更新します。"
    description = "入力データごとに指定したメタデータを更新します。"
    epilog = "オーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.create_parser(subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog)
    parse_args(parser)
    return parser
