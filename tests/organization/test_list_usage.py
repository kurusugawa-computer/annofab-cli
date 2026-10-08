import copy
import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock

import pandas
import pytest

from annofabcli.common.exceptions import AnnofabCliException
from annofabcli.organization.list_usage import CSV_COLUMNS, DAILY_CSV_COLUMNS, ListUsage
from annofabcli.organization.usage_status import validate_period


def make_usage_status(*, daily: bool) -> dict:
    result = {
        "organization_id": "org-id",
        "aggregation_period_from": "2026-09-01T00:00:00+09:00",
        "aggregation_period_to": "2026-09-02T00:00:00+09:00",
        "storage_usage": 48.5,
        "editor_usage": [{"editor_name": "image_editor", "value": 1.5}, {"editor_name": "video_editor", "value": 0}],
    }
    if daily:
        result.update(date="2026-09-01", created_datetime="2026-09-02T03:00:00+09:00")
    else:
        result["year_month"] = "2026-09"
    return result


@pytest.mark.parametrize("daily", [False, True])
@pytest.mark.parametrize("output_format", ["csv", "json", "pretty_json"])
@pytest.mark.parametrize("empty", [False, True])
def test_usage_status_output(tmp_path: Path, *, daily: bool, output_format: str, empty: bool) -> None:
    service = Mock()
    data = [] if empty else [make_usage_status(daily=daily)]
    original_data = copy.deepcopy(data)
    service.api.get_organization_usage_status_list.return_value = (data, Mock())
    service.api.get_organization_usage_status.return_value = (data, Mock())
    output = tmp_path / "usage.txt"
    args = Namespace(
        organization="org",
        start_month="2026-08" if not daily else None,
        end_month="2026-09" if not daily else None,
        month="2026-09" if daily else None,
        format=output_format,
        output=output,
        yes=True,
    )

    ListUsage(service, Mock(), args).main()

    if daily:
        service.api.get_organization_usage_status.assert_called_once_with("org", "2026-09")
        service.api.get_organization_usage_status_list.assert_not_called()
    else:
        service.api.get_organization_usage_status_list.assert_called_once_with("org", query_params={"from": "2026-08", "to": "2026-09"})
        service.api.get_organization_usage_status.assert_not_called()
    if output_format == "csv":
        df = pandas.read_csv(output)
        assert df.columns.to_list() == list(DAILY_CSV_COLUMNS if daily else CSV_COLUMNS)
        assert len(df) == len(data)
        if not empty:
            assert df.loc[0, "organization_name"] == "org"
            assert df.loc[0, "storage_usage_gb_hour"] == 48.5
            assert df.loc[0, "image_editor_usage_hour"] == 1.5
            assert df.loc[0, "video_editor_usage_hour"] == 0
            assert pandas.isna(df.loc[0, "3d_editor_usage_hour"])
            assert df.loc[0, "date" if daily else "month"] == ("2026-09-01" if daily else "2026-09")
    else:
        expected = []
        if not empty:
            row = {
                "organization_id": "org-id",
                "organization_name": "org",
                "aggregation_period_from": data[0]["aggregation_period_from"],
                "aggregation_period_to": data[0]["aggregation_period_to"],
                "storage_usage_gb_hour": 48.5,
                "image_editor_usage_hour": 1.5,
                "video_editor_usage_hour": 0,
                "3d_editor_usage_hour": None,
            }
            if daily:
                row.update(date="2026-09-01", created_datetime="2026-09-02T03:00:00+09:00")
            else:
                row["month"] = "2026-09"
            expected.append(row)
        assert json.loads(output.read_text()) == expected
    assert data == original_data


@pytest.mark.parametrize("start_month,end_month,query_params", [(None, None, {}), ("2026-08", None, {"from": "2026-08"}), (None, "2026-09", {"to": "2026-09"})])
def test_optional_month_range(tmp_path: Path, start_month: str | None, end_month: str | None, query_params: dict) -> None:
    service = Mock()
    service.api.get_organization_usage_status_list.return_value = ([], Mock())
    args = Namespace(organization="org", start_month=start_month, end_month=end_month, month=None, format="json", output=tmp_path / "usage.json", yes=True)

    ListUsage(service, Mock(), args).main()

    service.api.get_organization_usage_status_list.assert_called_once_with("org", query_params=query_params)


@pytest.mark.parametrize("output_format", ["csv", "json", "pretty_json"])
def test_output_keeps_additional_editor(tmp_path: Path, output_format: str) -> None:
    service = Mock()
    data = make_usage_status(daily=False)
    data["editor_usage"].append({"editor_name": "custom_editor", "value": 2.5})
    service.api.get_organization_usage_status_list.return_value = ([data], Mock())
    output = tmp_path / "usage.csv"
    args = Namespace(organization="org", start_month=None, end_month=None, month=None, format=output_format, output=output, yes=True)

    ListUsage(service, Mock(), args).main()

    if output_format == "csv":
        assert pandas.read_csv(output).loc[0, "custom_editor_usage_hour"] == 2.5
    else:
        assert json.loads(output.read_text())[0]["custom_editor_usage_hour"] == 2.5


@pytest.mark.parametrize("start_month,end_month,daily_month", [("2026-10", "2026-09", None), ("2026-09", None, "2026-09"), (None, "2026-09", "2026-09")])
def test_conflicting_period(start_month: str | None, end_month: str | None, daily_month: str | None) -> None:
    with pytest.raises(AnnofabCliException):
        validate_period(start_month, end_month, daily_month)


def test_same_month_period() -> None:
    validate_period("2026-09", "2026-09", None)
