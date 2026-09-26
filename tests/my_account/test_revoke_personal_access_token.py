import argparse
from unittest.mock import Mock, call

from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.my_account.revoke_personal_access_token import RevokePersonalAccessToken


def test__main__パーソナルアクセストークンを無効化する():
    service = Mock()
    args = argparse.Namespace(personal_access_token_id="pat1", yes=True)
    command = RevokePersonalAccessToken(service, Mock(spec=AnnofabApiFacade), args)

    command.main()

    assert service.api.method_calls == [call.revoke_personal_access_token(request_body={"id": "pat1"})]
