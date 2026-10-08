from argparse import Namespace
from unittest.mock import Mock

import pytest

from annofabcli.project.diff_projects import DiffProjects


@pytest.mark.parametrize(("left", "right", "expected"), [("before", "after", "('before', 'after')"), ("after", "before", "('after', 'before')")])
def test_diff_main_reports_settings_from_left_to_right(capsys, left, right, expected):
    service = Mock()
    projects = {"before": {"configuration": {"value": "before"}}, "after": {"configuration": {"value": "after"}}}
    service.api.get_project.side_effect = lambda project_id: (projects[project_id], None)
    facade = Mock()
    facade.get_project_title.side_effect = lambda project_id: project_id
    args = Namespace(yes=False, left_project_id=left, right_project_id=right, target=["settings"])

    DiffProjects(service, facade, args).main()

    output = capsys.readouterr().out
    assert f"{left}({left}) と {right}({right})" in output
    assert expected in output
