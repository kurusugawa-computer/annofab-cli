import csv
import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from annofabcli.organization.list_usage_detail import CSV_COLUMNS, ListUsageDetail


@pytest.fixture
def service() -> Mock:
    service = Mock()
    service.api.get_organization_usage_status_detail.return_value = ({"url": "https://example.com/usage.csv"}, Mock())
    service.api.get_organization.return_value = ({"organization_id": "org-id"}, Mock())
    service.wrapper.get_all_organization_members.return_value = [{"account_id": "0001", "user_id": "alice", "username": "利用者A"}]
    service.wrapper.get_all_projects_of_organization.return_value = [{"project_id": "001", "title": "プロジェクトA"}]
    return service


@pytest.mark.parametrize("output_format", ["csv", "json", "pretty_json"])
def test_normalized_usage_detail(tmp_path: Path, service: Mock, output_format: str) -> None:
    content = "\ufeffdate,editorName,projectId,accountId,editorUsageTime\r\n2026-09-01,image_editor,001,0001,1.5\r\n2026-09-02,video_editor,deleted,former,0\r\n2026-09-03,3d_editor,NA,NA,\r\n"
    service.wrapper.download.side_effect = lambda _url, destination: destination.write_text(content, encoding="utf-8")
    output = tmp_path / "nested" / "usage.txt"
    args = Namespace(organization="org", month="2026-09", format=output_format, output=output, yes=True)

    ListUsageDetail(service, Mock(), args).main()

    expected: list[dict[str, str | float | None]] = [
        {
            "organization_id": "org-id",
            "organization_name": "org",
            "date": "2026-09-01",
            "editor_name": "image_editor",
            "project_id": "001",
            "project_title": "プロジェクトA",
            "account_id": "0001",
            "user_id": "alice",
            "username": "利用者A",
            "editor_usage_hour": 1.5,
        },
        {
            "organization_id": "org-id",
            "organization_name": "org",
            "date": "2026-09-02",
            "editor_name": "video_editor",
            "project_id": "deleted",
            "project_title": None,
            "account_id": "former",
            "user_id": None,
            "username": None,
            "editor_usage_hour": 0.0,
        },
        {
            "organization_id": "org-id",
            "organization_name": "org",
            "date": "2026-09-03",
            "editor_name": "3d_editor",
            "project_id": "NA",
            "project_title": None,
            "account_id": "NA",
            "user_id": None,
            "username": None,
            "editor_usage_hour": None,
        },
    ]
    if output_format == "csv":
        with output.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            assert reader.fieldnames == list(CSV_COLUMNS)
            rows = list(reader)
        assert rows == [{key: "" if value is None else str(value) for key, value in row.items()} for row in expected]
    else:
        rows = json.loads(output.read_text())
        assert rows == expected
        assert list(rows[0]) == list(CSV_COLUMNS)


@pytest.mark.parametrize("content", ["", "date,editorName,projectId,accountId,editorUsageTime\n"])
@pytest.mark.parametrize("output_format", ["csv", "json"])
def test_empty_detail(tmp_path: Path, service: Mock, content: str, output_format: str) -> None:
    service.wrapper.download.side_effect = lambda _url, destination: destination.write_text(content)
    output = tmp_path / "usage.txt"
    args = Namespace(organization="org", month="2026-09", format=output_format, output=output, yes=True)

    ListUsageDetail(service, Mock(), args).main()

    if output_format == "csv":
        assert output.read_text(encoding="utf-8-sig").strip() == ",".join(CSV_COLUMNS)
    else:
        assert json.loads(output.read_text()) == []
    service.api.get_organization.assert_not_called()
    service.wrapper.get_all_projects_of_organization.assert_not_called()


@pytest.mark.parametrize("existing", [False, True])
def test_download_failure_does_not_leave_partial_output(tmp_path: Path, service: Mock, *, existing: bool) -> None:
    def download(_url: str, destination: Path) -> None:
        destination.write_bytes(b"partial")
        raise requests.HTTPError

    service.wrapper.download.side_effect = download
    output = tmp_path / "usage.csv"
    if existing:
        output.write_bytes(b"original")
    args = Namespace(organization="org", month="2026-09", format="csv", output=output, yes=True)

    with pytest.raises(requests.HTTPError):
        ListUsageDetail(service, Mock(), args).main()

    if existing:
        assert output.read_bytes() == b"original"
    else:
        assert not output.exists()


def test_project_lookup_failure_preserves_existing_output(tmp_path: Path, service: Mock) -> None:
    content = "date,editorName,projectId,accountId,editorUsageTime\n2026-09-01,image_editor,001,0001,1.5\n"
    service.wrapper.download.side_effect = lambda _url, destination: destination.write_text(content)
    service.wrapper.get_all_projects_of_organization.side_effect = requests.HTTPError()
    output = tmp_path / "usage.csv"
    output.write_bytes(b"original")
    args = Namespace(organization="org", month="2026-09", format="csv", output=output, yes=True)

    with pytest.raises(requests.HTTPError):
        ListUsageDetail(service, Mock(), args).main()

    assert output.read_bytes() == b"original"
