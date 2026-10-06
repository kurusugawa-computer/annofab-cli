from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock

import pandas
import pytest

from annofabcli.instruction.list_instruction_history import CSV_COLUMNS, ListInstructionHistories


@pytest.mark.parametrize("output_format", ["csv", "json", "pretty_json"])
def test_empty_list_output(tmp_path: Path, output_format: str) -> None:
    service = Mock()
    service.api.get_instruction_history.return_value = ([], None)
    output = tmp_path / "output.txt"
    args = Namespace(project_id="project1", format=output_format, output=output, yes=True)

    ListInstructionHistories(service, Mock(), args).main()

    if output_format == "csv":
        df = pandas.read_csv(output)
        assert len(df) == 0
        assert df.columns.to_list() == list(CSV_COLUMNS)
    else:
        assert output.read_text() == "[]"
