import logging
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

import annofabapi

from annofabcli.common.annofab.input_data import BULK_REQUEST_SIZE

logger = logging.getLogger(__name__)


@dataclass
class SupplementaryDataBulkResult:
    """補助情報のバルク取得結果。"""

    supplementary_data_by_input_data_id: dict[str, list[dict[str, Any]]]
    failed_input_data_id_set: set[str]


def get_supplementary_data_dict_in_bulk(service: annofabapi.Resource, project_id: str, input_data_id_list: Collection[str]) -> SupplementaryDataBulkResult:
    """補助情報をバルク取得する。

    Args:
        service: Annofab APIのリソース。
        project_id: プロジェクトID。
        input_data_id_list: 取得対象の入力データID。

    Returns:
        入力データIDごとの補助情報と、取得に失敗した入力データID。
    """
    input_data_id_list = list(dict.fromkeys(input_data_id_list))
    supplementary_data_dict: dict[str, list[dict[str, Any]]] = {input_data_id: [] for input_data_id in input_data_id_list}
    failed_input_data_id_set: set[str] = set()
    for initial_index in range(0, len(input_data_id_list), BULK_REQUEST_SIZE):
        batch_input_data_id_list = input_data_id_list[initial_index : initial_index + BULK_REQUEST_SIZE]
        response, _ = service.api.get_supplementary_data_in_bulk(project_id, query_params={"input_data_id": ",".join(batch_input_data_id_list)})
        for supplementary_data in response["success"]:
            supplementary_data_dict.setdefault(supplementary_data["input_data_id"], []).append(supplementary_data)
        for failure_info in response["failure"]:
            failed_input_data_id_set.add(failure_info["input_data_id"])
            logger.warning(f"input_data_id='{failure_info['input_data_id']}': 補助情報の取得に失敗しました。")
    return SupplementaryDataBulkResult(supplementary_data_by_input_data_id=supplementary_data_dict, failed_input_data_id_set=failed_input_data_id_set)
