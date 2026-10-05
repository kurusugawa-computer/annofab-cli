import json
from argparse import Namespace
from copy import deepcopy
from unittest.mock import Mock

import pandas
import pytest

from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.organization_idp.list_organization_idp import ListOrganizationIdp


@pytest.mark.parametrize("output_format", ["csv", "json", "pretty_json"])
@pytest.mark.parametrize("empty", [False, True])
def test_一覧を出力しシークレットを除外する(tmp_path, output_format, empty):
    idp_list = (
        []
        if empty
        else [
            {
                "organization_name": "org1",
                "id": "idp1",
                "client_id": "client1",
                "client_secret": "secret-for-test",
                "attributes_request_method": "GET",
                "endpoints": {"issuer": "https://example.com"},
                "attribute_mapping": {"email": "email", "name": "name"},
            }
        ]
    )
    original = deepcopy(idp_list)
    service = Mock()
    service.api.get_organization_idp_list.return_value = (idp_list, None)
    output = tmp_path / "idps.txt"
    args = Namespace(organization="org1", format=output_format, output=output, yes=True)

    ListOrganizationIdp(service, AnnofabApiFacade(service), args).main()

    service.api.get_organization_idp_list.assert_called_once_with("org1")
    assert idp_list == original
    assert "client_secret" not in output.read_text()
    assert "secret-for-test" not in output.read_text()
    if output_format == "csv":
        df = pandas.read_csv(output)
        if empty:
            assert df.empty
            assert list(df.columns) == ListOrganizationIdp.PRIOR_COLUMNS
        else:
            assert df.loc[0, "id"] == "idp1"
            assert df.loc[0, "endpoints.issuer"] == "https://example.com"
            assert df.loc[0, "attribute_mapping.email"] == "email"
    else:
        expected = [{key: value for key, value in idp.items() if key != "client_secret"} for idp in original]
        assert json.loads(output.read_text()) == expected
