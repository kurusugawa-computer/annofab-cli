from __future__ import annotations

import json
import logging
import multiprocessing
from dataclasses import dataclass
from functools import partial
from typing import Any

import annofabapi

from annofabcli.common.annofab.input_data import BULK_REQUEST_SIZE, get_input_data_dict_in_bulk
from annofabcli.common.cli import (
    CommandLineWithConfirm,
)
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


def validate_metadata(metadata: Metadata) -> bool:
    """
    メタデータの値を検証します。
    * メタデータの値がstr型であること
    """
    return all(isinstance(value, str) for value in metadata.values())
