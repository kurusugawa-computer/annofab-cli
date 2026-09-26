import pandas

from annofabcli.my_account.list_personal_access_token import create_personal_access_token_dataframe


def test__create_personal_access_token_dataframe__permissionsをJSON文字列に変換する():
    personal_access_token_list = [
        {
            "id": "pat1",
            "account_id": "account1",
            "note": "連携用",
            "expired_datetime": "2026-12-31T00:00:00+09:00",
            "permissions": [{"type": "all"}],
            "created_datetime": "2026-01-01T00:00:00+09:00",
            "last_used_datetime": None,
        }
    ]

    actual = create_personal_access_token_dataframe(personal_access_token_list)

    expected = pandas.DataFrame(
        [
            {
                "id": "pat1",
                "note": "連携用",
                "expired_datetime": "2026-12-31T00:00:00+09:00",
                "last_used_datetime": None,
                "created_datetime": "2026-01-01T00:00:00+09:00",
                "permissions": '[{"type": "all"}]',
                "account_id": "account1",
            }
        ]
    )
    pandas.testing.assert_frame_equal(actual, expected)


def test__create_personal_access_token_dataframe__空の場合はヘッダ行相当の列を返す():
    actual = create_personal_access_token_dataframe([])

    assert list(actual.columns) == [
        "id",
        "note",
        "expired_datetime",
        "last_used_datetime",
        "created_datetime",
        "permissions",
        "account_id",
    ]
    assert len(actual) == 0
