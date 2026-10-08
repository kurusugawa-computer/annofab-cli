from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from annofabcli.organization.download_usage_status_detail import DownloadUsageStatusDetail


def test_download_csv_preserves_bytes(tmp_path: Path) -> None:
    service = Mock()
    url = "https://example.com/signed-usage.csv"
    service.api.get_organization_usage_status_detail.return_value = ({"url": url}, Mock())
    csv_content = b"\xef\xbb\xbfdate,value\r\n2026-09-01,1.5\r\n"

    def download(download_url: str, destination: Path) -> None:
        assert download_url == url
        destination.write_bytes(csv_content)

    service.wrapper.download.side_effect = download
    output = tmp_path / "nested" / "usage.csv"
    args = Namespace(organization="org", year_month="2026-09", output=output, yes=True)

    DownloadUsageStatusDetail(service, Mock(), args).main()

    service.api.get_organization_usage_status_detail.assert_called_once_with("org", "2026-09")
    assert output.read_bytes() == csv_content
    assert list(output.parent.iterdir()) == [output]


@pytest.mark.parametrize("existing", [False, True])
def test_download_failure_does_not_leave_partial_output(tmp_path: Path, *, existing: bool) -> None:
    service = Mock()
    service.api.get_organization_usage_status_detail.return_value = ({"url": "https://example.com/usage.csv"}, Mock())

    def download(_url: str, destination: Path) -> None:
        destination.write_bytes(b"partial")
        raise requests.HTTPError

    service.wrapper.download.side_effect = download
    output = tmp_path / "usage.csv"
    if existing:
        output.write_bytes(b"original")
    args = Namespace(organization="org", year_month="2026-09", output=output, yes=True)

    with pytest.raises(requests.HTTPError):
        DownloadUsageStatusDetail(service, Mock(), args).main()

    if existing:
        assert output.read_bytes() == b"original"
    else:
        assert not output.exists()
    assert list(tmp_path.iterdir()) == ([output] if existing else [])


def test_api_failure_preserves_existing_output(tmp_path: Path) -> None:
    service = Mock()
    service.api.get_organization_usage_status_detail.side_effect = requests.HTTPError()
    output = tmp_path / "usage.csv"
    output.write_bytes(b"original")
    args = Namespace(organization="org", year_month="2026-09", output=output, yes=True)

    with pytest.raises(requests.HTTPError):
        DownloadUsageStatusDetail(service, Mock(), args).main()

    assert output.read_bytes() == b"original"
    service.wrapper.download.assert_not_called()
