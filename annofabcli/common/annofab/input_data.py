import logging
from collections.abc import Collection
from typing import Any

import annofabapi

logger = logging.getLogger(__name__)

BULK_REQUEST_SIZE = 100
"""getInputDataInBulk APIに渡す入力データIDの最大件数。"""


def get_input_data_dict_in_bulk(service: annofabapi.Resource, project_id: str, input_data_id_list: Collection[str]) -> dict[str, dict[str, Any]]:
    """入力データをバルク取得し、IDをキーとする辞書で返す。

    存在しない入力データは戻り値に含めない。

    Args:
        service: Annofab APIのリソース。
        project_id: プロジェクトID。
        input_data_id_list: 取得対象の入力データID。

    Returns:
        入力データIDをキー、入力データを値とする辞書。
    """
    input_data_id_list = list(dict.fromkeys(input_data_id_list))
    input_data_dict: dict[str, dict[str, Any]] = {}

    for initial_index in range(0, len(input_data_id_list), BULK_REQUEST_SIZE):
        batch_input_data_id_list = input_data_id_list[initial_index : initial_index + BULK_REQUEST_SIZE]
        response, _ = service.api.get_input_data_in_bulk(
            project_id,
            query_params={"input_data_id": ",".join(batch_input_data_id_list)},
        )
        for input_data in response["success"]:
            input_data_dict[input_data["input_data_id"]] = input_data

        for failure_info in response["failure"]:
            logger.debug(f"input_data_id='{failure_info['input_data_id']}': 入力データは存在しません。")

    return input_data_dict
