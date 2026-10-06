from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock

import pandas
import pytest

from annofabcli.common.utils import print_csv
from annofabcli.project.list_project import ListProject, create_project_dataframe


@pytest.mark.parametrize("project_list", [[], [{"project_id": "project1", "summary": {"last_tasks_updated_datetime": "2026-10-01T00:00:00+09:00"}, "extra": "value"}]])
def test_create_project_dataframe(project_list, tmp_path: Path) -> None:

    df = create_project_dataframe(project_list)
    output = tmp_path / "projects.csv"
    print_csv(df, output)
    actual = pandas.read_csv(output)
    assert len(actual) == len(project_list)
    if project_list:
        assert actual.loc[0, "last_tasks_updated_datetime"] == "2026-10-01T00:00:00+09:00"
        assert actual.loc[0, "extra"] == "value"
        assert "summary" in actual.columns
    else:
        assert actual.columns.to_list() == ListProject.PRIOR_COLUMNS


def test_empty_list_outputs_csv_header(tmp_path: Path) -> None:
    service = Mock()
    service.wrapper.get_all_projects_of_organization.return_value = []
    output = tmp_path / "projects.csv"
    args = Namespace(project_id=None, organization="org1", project_query=None, include_not_joined_project=True, format="csv", output=output, yes=True)

    ListProject(service, Mock(), args).main()

    df = pandas.read_csv(output)
    assert len(df) == 0
    assert df.columns.to_list() == ListProject.PRIOR_COLUMNS
