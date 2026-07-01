import pandas

from annofabcli.webhook.list_webhook import create_webhook_dataframe


def test__create_webhook_dataframe__headersをJSON文字列に変換する():
    webhook_list = [
        {
            "project_id": "prj1",
            "webhook_id": "webhook1",
            "webhook_status": "active",
            "event_type": "task-completed",
            "method": "POST",
            "url": "https://example.com/webhook",
            "headers": [{"name": "X-Test", "value": "テスト"}],
            "body": '{"project_id":"{{PROJECT_ID}}"}',
            "created_datetime": "2026-01-23T03:02:56.478+09:00",
            "updated_datetime": "2026-01-23T03:02:56.478+09:00",
        }
    ]

    actual = create_webhook_dataframe(webhook_list)

    expected = pandas.DataFrame(
        [
            {
                "project_id": "prj1",
                "webhook_id": "webhook1",
                "webhook_status": "active",
                "event_type": "task-completed",
                "method": "POST",
                "url": "https://example.com/webhook",
                "headers": '[{"name": "X-Test", "value": "テスト"}]',
                "body": '{"project_id":"{{PROJECT_ID}}"}',
                "created_datetime": "2026-01-23T03:02:56.478+09:00",
                "updated_datetime": "2026-01-23T03:02:56.478+09:00",
            }
        ]
    )
    pandas.testing.assert_frame_equal(actual, expected)


def test__create_webhook_dataframe__空の場合はヘッダ行相当の列を返す():
    actual = create_webhook_dataframe([])

    assert list(actual.columns) == [
        "project_id",
        "webhook_id",
        "webhook_status",
        "event_type",
        "method",
        "url",
        "headers",
        "body",
        "created_datetime",
        "updated_datetime",
    ]
    assert len(actual) == 0
