from collections.abc import Collection
from typing import Any

import annofabapi

from annofabcli.common.annofab.input_data import BULK_REQUEST_SIZE


def get_supplementary_data_dict_in_bulk(service: annofabapi.Resource, project_id: str, input_data_id_list: Collection[str]) -> dict[str, list[dict[str, Any]]]:
    """補助情報をバルク取得し、入力データIDごとの辞書で返す。"""
    input_data_id_list = list(dict.fromkeys(input_data_id_list))
    supplementary_data_dict: dict[str, list[dict[str, Any]]] = {input_data_id: [] for input_data_id in input_data_id_list}
    for initial_index in range(0, len(input_data_id_list), BULK_REQUEST_SIZE):
        batch_input_data_id_list = input_data_id_list[initial_index : initial_index + BULK_REQUEST_SIZE]
        response, _ = service.api.get_supplementary_data_in_bulk(project_id, query_params={"input_data_id": ",".join(batch_input_data_id_list)})
        for supplementary_data in response["success"]:
            supplementary_data_dict.setdefault(supplementary_data["input_data_id"], []).append(supplementary_data)
    return supplementary_data_dict
