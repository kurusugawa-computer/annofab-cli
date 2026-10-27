import json
import shutil
from pathlib import Path

import pandas
import pytest

from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE
from annofabcli.stat_visualization.merge_visualization_dir import create_parser, main


@pytest.mark.parametrize("use_file", [False, True])
def test_main_merges_directories(tmp_path: Path, *, use_file: bool) -> None:
    source = Path("tests/data/stat_visualization/merge_visualization_dir/visualization1")
    directories = [tmp_path / "project 1", tmp_path / "project 2"]
    for directory in directories:
        shutil.copytree(source, directory)
    directory_list = tmp_path / "ディレクトリ一覧.txt"
    directory_list.write_text("\n\n".join(str(directory) for directory in directories) + "\n", encoding="utf-8")
    values = [f"file://{directory_list}"] if use_file else [str(directory) for directory in directories]
    output = tmp_path / "merged"
    args = create_parser().parse_args(["--dir", *values, "--output_dir", str(output), "--minimal"])

    main(args)

    merge_info = json.loads((output / "merge_info.json").read_text(encoding="utf-8"))
    assert merge_info["target_dir_list"] == [str(directory) for directory in directories]
    original_tasks = pandas.read_csv(source / "タスクlist.csv", comment="#")
    merged_tasks = pandas.read_csv(output / "タスクlist.csv", comment="#")
    assert len(merged_tasks) == len(original_tasks) * 2


@pytest.mark.parametrize("contents", ["", "\n", "project1\n"])
def test_main_rejects_fewer_than_two_directories_in_file(tmp_path: Path, contents: str) -> None:
    directory_list = tmp_path / "directories.txt"
    directory_list.write_text(contents, encoding="utf-8")
    output = tmp_path / "merged"
    args = create_parser().parse_args(["--dir", f"file://{directory_list}", "--output_dir", str(output)])

    with pytest.raises(SystemExit) as exc_info:
        main(args)

    assert exc_info.value.code == COMMAND_LINE_ERROR_STATUS_CODE
    assert not output.exists()
