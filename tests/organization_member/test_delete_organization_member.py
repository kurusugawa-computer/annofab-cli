import logging

import requests

from annofabcli.organization_member.delete_organization_member import DeleteOrganizationMemberMain


def test_成功とスキップと失敗の件数を出力して処理を継続する(service, caplog):
    service.api.delete_organization_member.side_effect = [requests.HTTPError("error"), ({}, None)]
    command = DeleteOrganizationMemberMain(service, all_yes=True)

    with caplog.at_level(logging.DEBUG):
        command.delete_organization_members_from_organization("org1", ["user1", "absent", "user2"])

    assert "成功: 1 件、スキップ: 1 件、失敗: 1 件、合計: 3 件" in caplog.text
    assert "3 / 3 件目を処理します。" in caplog.text
    assert service.api.delete_organization_member.call_count == 2
    assert any(record.exc_info for record in caplog.records if record.levelno == logging.WARNING)


def test_確認でnoを回答したユーザをスキップ件数に含める(service, caplog, monkeypatch):
    monkeypatch.setattr("annofabcli.common.cli.prompt_yesnoall", lambda _message: (False, False))
    command = DeleteOrganizationMemberMain(service)

    with caplog.at_level(logging.INFO):
        command.delete_organization_members_from_organization("org1", ["user1"])

    assert "成功: 0 件、スキップ: 1 件、失敗: 0 件、合計: 1 件" in caplog.text
    service.api.delete_organization_member.assert_not_called()


def test_100件ごとにinfoログで進捗を出力する(service, caplog):
    service.wrapper.get_all_organization_members.return_value = [
        {"user_id": f"user{index}", "username": f"user{index}", "role": "contributor", "updated_datetime": "2026-10-05T12:00:00+09:00"} for index in range(100)
    ]
    command = DeleteOrganizationMemberMain(service, all_yes=True)

    with caplog.at_level(logging.INFO):
        command.delete_organization_members_from_organization("org1", [f"user{index}" for index in range(100)])

    assert "100 / 100 件目を処理します。" in caplog.text
    assert "合計: 100 件" in caplog.text


def test_権限がない組織は全件をスキップとして出力する(service, caplog):
    service.wrapper.get_all_my_organizations.return_value = []
    command = DeleteOrganizationMemberMain(service, all_yes=True)

    with caplog.at_level(logging.INFO):
        command.delete_organization_members_from_organization("org1", ["user1", "user2"])

    assert "成功: 0 件、スキップ: 2 件、失敗: 0 件、合計: 2 件" in caplog.text
    service.api.delete_organization_member.assert_not_called()
