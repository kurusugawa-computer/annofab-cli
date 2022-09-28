import os
from pathlib import Path

from annofabcli.__main__ import main

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

data_dir = Path("./tests/data/my_account")
out_dir = Path("./tests/out/my_account")
out_dir.mkdir(exist_ok=True, parents=True)


class TestCommandLine:
    def test_get(self):
        output_file = str(out_dir / "get-out.json")
        main(["my_account", "get", "--output", str(output_file)])
