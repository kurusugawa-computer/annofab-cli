from pathlib import Path

import pandas


out_path = Path("./tests/out/labor")
data_path = Path("./tests/data/labor")
(out_path / "labor").mkdir(exist_ok=True, parents=True)

