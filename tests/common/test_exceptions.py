from annofabapi.models import OrganizationMemberRole, ProjectMemberRole

from annofabcli.common.exceptions import OrganizationAuthorizationError, ProjectAuthorizationError


def test_project_authorization_errorに操作と必要なロールが表示される() -> None:
    error = ProjectAuthorizationError("テストプロジェクト", [ProjectMemberRole.OWNER], operation="--cancel_acceptance による受入完了の取り消し")

    message = str(error)
    assert "テストプロジェクト" in message
    assert "--cancel_acceptance による受入完了の取り消し" in message
    assert "オーナーロール（owner）が必要" in message


def test_project_authorization_errorに複数のロールが表示される() -> None:
    error = ProjectAuthorizationError("テストプロジェクト", [ProjectMemberRole.ACCEPTER, ProjectMemberRole.OWNER])

    message = str(error)
    assert "チェッカーロール（accepter）" in message
    assert "オーナーロール（owner）のいずれか" in message


def test_organization_authorization_errorに操作が表示される() -> None:
    error = OrganizationAuthorizationError("テスト組織", [OrganizationMemberRole.OWNER], operation="メンバーの招待")

    message = str(error)
    assert "テスト組織" in message
    assert "メンバーの招待" in message
    assert "'owner'ロールが必要" in message
