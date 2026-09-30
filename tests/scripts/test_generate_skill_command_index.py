import pytest

from annofabcli.__main__ import create_parser
from scripts import generate_skill_command_index
from scripts.generate_skill_command_index import OUTPUT_PATH, build_command_index, collect_command_groups, is_command_index_current


def test_コマンド索引がargparseの定義と一致する() -> None:
    actual = OUTPUT_PATH.read_text(encoding="utf-8")
    expected = build_command_index(collect_command_groups(create_parser()))

    assert actual == expected


def test_is_command_index_current(tmp_path) -> None:
    output_path = tmp_path / "command-index.md"

    assert not is_command_index_current("expected", output_path)

    output_path.write_text("outdated", encoding="utf-8")
    assert not is_command_index_current("expected", output_path)

    output_path.write_text("expected", encoding="utf-8")
    assert is_command_index_current("expected", output_path)


def test_mainでcheckを指定したときにコマンド索引が古ければ終了する(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / "command-index.md"
    output_path.write_text("outdated", encoding="utf-8")
    monkeypatch.setattr(generate_skill_command_index, "OUTPUT_PATH", output_path)

    with pytest.raises(SystemExit):
        generate_skill_command_index.main(["--check"])
