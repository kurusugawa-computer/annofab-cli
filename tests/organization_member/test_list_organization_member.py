from argparse import Namespace

import pandas
import pytest

from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.organization_member.list_organization_member import ListOrganizationMember


@pytest.mark.parametrize("organizations", [["org1"], ["org1", "org2"]])
def test_結果が空でもCSVのヘッダを出力する(service, tmp_path, organizations):
    service.wrapper.get_all_organization_members.return_value = []
    output = tmp_path / "members.csv"
    args = Namespace(organization=organizations, format="csv", output=output, yes=True)

    ListOrganizationMember(service, AnnofabApiFacade(service), args).main()

    df = pandas.read_csv(output)
    assert list(df.columns) == ListOrganizationMember.PRIOR_COLUMNS
    assert df.empty


def test_CSVに組織名とAPIの追加フィールドを出力する(service, tmp_path):
    service.wrapper.get_all_organization_members.return_value = [{"user_id": "user1", "created_datetime": "2026-10-05T12:00:00+09:00"}]
    output = tmp_path / "members.csv"
    args = Namespace(organization=["org1"], format="csv", output=output, yes=True)

    ListOrganizationMember(service, AnnofabApiFacade(service), args).main()

    df = pandas.read_csv(output)
    assert df.to_dict("records") == [{"organization_name": "org1", "user_id": "user1", "created_datetime": "2026-10-05T12:00:00+09:00"}]
