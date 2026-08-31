import argparse
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock, call

import annofabapi

from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.input_data.delete_input_data import DeleteInputData


def test_delete_input_data_calls_only_delete_input_data_api() -> None:
    api = Mock()
    wrapper = Mock()
    wrapper.get_input_data_or_none.return_value = {"input_data_id": "input1", "input_data_name": "input1.bin"}
    wrapper.get_all_tasks.return_value = []
    service = cast(annofabapi.Resource, SimpleNamespace(api=api, wrapper=wrapper))
    main_obj = DeleteInputData(service, Mock(spec=AnnofabApiFacade), argparse.Namespace(yes=True))

    result = main_obj.delete_input_data("project1", "input1", input_data_index=0, delete_input_data_used_by_task=False)

    assert result is True
    assert api.method_calls == [call.delete_input_data("project1", "input1")]
