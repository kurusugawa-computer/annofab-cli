from __future__ import annotations

import json
from pathlib import Path

from annofabcli.annotation_specs.list_annotation_specs_choice import create_flatten_choice_list_from_additionals

DATA_DIR = Path("./tests/data/annotation_specs")


def test_create_flatten_choice_list_from_additionalsはキーバインド未設定時にkeybind_textをNoneにする() -> None:
    with (DATA_DIR / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)

    actual = create_flatten_choice_list_from_additionals(annotation_specs["additionals"])

    choice = next(e for e in actual if e.choice_id == "08ec927c-18e6-4bba-837a-b16de7061580")
    assert choice.keybind is None
    assert choice.keybind_text is None
