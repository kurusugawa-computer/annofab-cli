from pathlib import Path

import pytest

from annofabcli.__main__ import main

# webapiにアクセスするテストモジュール
pytestmark = pytest.mark.access_webapi

data_dir = Path("./tests/data/organization")
out_dir = Path("./tests/out/organization")
out_dir.mkdir(exist_ok=True, parents=True)


class TestCommandLine:
    def test_get(self):
        output_file = str(out_dir / "list-out.json")
        main(["organization", "list", "--output", str(output_file)])
