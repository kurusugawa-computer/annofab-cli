from unittest.mock import Mock

import pytest


@pytest.fixture
def service():
    service = Mock()
    service.wrapper.get_all_my_organizations.return_value = [{"name": "org1", "my_role": "owner"}]
    service.wrapper.get_all_organization_members.return_value = [
        {"user_id": user_id, "username": user_id, "role": "contributor", "updated_datetime": "2026-10-05T12:00:00+09:00"} for user_id in ["user1", "user2"]
    ]
    return service
