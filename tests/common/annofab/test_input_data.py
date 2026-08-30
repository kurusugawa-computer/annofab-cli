from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import annofabapi

from annofabcli.common.annofab.input_data import get_input_data_dict_in_bulk


def test_get_input_data_dict_in_bulk() -> None:
    api = Mock()
    api.get_input_data_in_bulk.side_effect = [
        (
            {
                "success": [{"input_data_id": f"input{i}"} for i in range(1, 101)],
                "failure": [],
            },
            Mock(),
        ),
        (
            {
                "success": [{"input_data_id": "input101"}],
                "failure": [{"input_data_id": "missing"}],
            },
            Mock(),
        ),
    ]
    service = cast(annofabapi.Resource, SimpleNamespace(api=api))

    result = get_input_data_dict_in_bulk(service, "project1", [*(f"input{i}" for i in range(1, 102)), "input1", "missing"])

    assert result == {f"input{i}": {"input_data_id": f"input{i}"} for i in range(1, 102)}
    assert api.get_input_data_in_bulk.call_args_list == [
        (("project1",), {"query_params": {"input_data_id": ",".join(f"input{i}" for i in range(1, 101))}}),
        (("project1",), {"query_params": {"input_data_id": "input101,missing"}}),
    ]
