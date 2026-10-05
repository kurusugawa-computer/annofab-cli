import logging

import requests

from annofabcli.organization_member.update_organization_member_role import UpdateOrganizationMemberRoleMain


def test_成功とスキップと失敗の件数を出力して処理を継続する(service, caplog):
    service.api.update_organization_member_role.side_effect = [requests.HTTPError("error"), ({}, None)]
    command = UpdateOrganizationMemberRoleMain(service, all_yes=True)

    with caplog.at_level(logging.DEBUG):
        command.main("org1", ["user1", "absent", "user2"], role="administrator")

    assert "成功: 1 件、スキップ: 1 件、失敗: 1 件、合計: 3 件" in caplog.text
    assert "3 / 3 件目を処理します。" in caplog.text
    assert service.api.update_organization_member_role.call_count == 2
    assert any(record.exc_info for record in caplog.records if record.levelno == logging.WARNING)


def test_確認でnoを回答したユーザをスキップ件数に含める(service, caplog, monkeypatch):
    monkeypatch.setattr("annofabcli.common.cli.prompt_yesnoall", lambda _message: (False, False))
    command = UpdateOrganizationMemberRoleMain(service)

    with caplog.at_level(logging.INFO):
        command.main("org1", ["user1"], role="administrator")

    assert "成功: 0 件、スキップ: 1 件、失敗: 0 件、合計: 1 件" in caplog.text
    service.api.update_organization_member_role.assert_not_called()


def test_100件ごとにinfoログで進捗を出力する(service, caplog):
    service.wrapper.get_all_organization_members.return_value = [
        {"user_id": f"user{index}", "username": f"user{index}", "role": "contributor", "updated_datetime": "2026-10-05T12:00:00+09:00"} for index in range(100)
    ]
    command = UpdateOrganizationMemberRoleMain(service, all_yes=True)

    with caplog.at_level(logging.INFO):
        command.main("org1", [f"user{index}" for index in range(100)], role="administrator")

    assert "100 / 100 件目を処理します。" in caplog.text
    assert "合計: 100 件" in caplog.text
