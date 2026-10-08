from argparse import Namespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from annofabcli.project.copy_project import CopyProject


@pytest.mark.parametrize("dest_project_id", ["destination", None])
def test_copy_uses_source_project_and_preserves_destination_id_generation(dest_project_id):
    service = Mock()
    args = Namespace(yes=True, src_project_id="source", dest_project_id=dest_project_id, dest_title="コピー先", dest_overview=None, copied_target=None)

    CopyProject(service, Mock(), args).main()

    source = service.api.initiate_project_copy.call_args.args[0]
    body = service.api.initiate_project_copy.call_args.kwargs["request_body"]
    assert source == "source"
    assert body["dest_title"] == "コピー先"
    if dest_project_id is None:
        assert UUID(body["dest_project_id"]).version == 4
    else:
        assert body["dest_project_id"] == dest_project_id
