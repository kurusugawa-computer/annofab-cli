import pandas

from annofabcli.organization.list_organization_plugin import create_organization_plugin_dataframe


def test__create_organization_plugin_dataframe__JSON文字列に変換する():
    plugin_list = [
        {
            "organization_id": "org1",
            "plugin_id": "plugin1",
            "plugin_name": "プラグイン1",
            "description": "説明",
            "is_builtin": False,
            "project_extra_data_kinds": ["kind1"],
            "detail": {"type": "AnnotationEditor", "url": "https://example.com"},
            "created_datetime": "2026-01-23T03:02:56.478+09:00",
            "updated_datetime": "2026-01-23T03:02:56.478+09:00",
        }
    ]

    actual = create_organization_plugin_dataframe(plugin_list)

    expected = pandas.DataFrame(
        [
            {
                "organization_id": "org1",
                "plugin_id": "plugin1",
                "plugin_name": "プラグイン1",
                "description": "説明",
                "is_builtin": False,
                "project_extra_data_kinds": '["kind1"]',
                "detail": '{"type": "AnnotationEditor", "url": "https://example.com"}',
                "created_datetime": "2026-01-23T03:02:56.478+09:00",
                "updated_datetime": "2026-01-23T03:02:56.478+09:00",
            }
        ]
    )
    pandas.testing.assert_frame_equal(actual, expected)


def test__create_organization_plugin_dataframe__空の場合はヘッダ行相当の列を返す():
    actual = create_organization_plugin_dataframe([])

    assert list(actual.columns) == [
        "organization_id",
        "plugin_id",
        "plugin_name",
        "description",
        "is_builtin",
        "project_extra_data_kinds",
        "detail",
        "created_datetime",
        "updated_datetime",
    ]
    assert len(actual) == 0
