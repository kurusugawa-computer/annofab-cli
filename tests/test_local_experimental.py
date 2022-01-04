import os
from pathlib import Path

import pandas


# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

data_dir = Path("./tests/data/experimental")
out_dir = Path("./tests/out/experimental")

