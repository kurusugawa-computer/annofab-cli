"""移行元・移行先コマンドが独立してインポートできることを確認する。"""

import json
import subprocess
import sys

import pytest

COMMAND_PAIRS = [
    ("statistics.summarize_task_count_by_user", "task_count.list_by_user"),
    ("statistics.summarize_task_count_by_task_id_group", "task_count.list_by_task_id_group"),
    ("statistics.list_worktime", "task_history_event.summarize_worktime_by_user_and_date"),
    ("statistics.list_video_duration", "task.list_video_duration"),
    ("statistics.visualize_video_duration", "task.visualize_video_duration"),
    ("statistics.list_annotation_count", "annotation_zip.count_annotation_by_label"),
    ("statistics.list_annotation_count", "annotation_zip.count_annotation_by_attribute_value"),
    ("statistics.visualize_annotation_count", "annotation_zip.visualize_annotation_count_by_label"),
    ("statistics.visualize_annotation_count", "annotation_zip.visualize_annotation_count_by_attribute_value"),
    ("statistics.list_annotation_duration", "annotation_zip.sum_annotation_duration_by_label"),
    ("statistics.list_annotation_duration", "annotation_zip.sum_annotation_duration_by_attribute_value"),
    ("statistics.visualize_annotation_duration", "annotation_zip.visualize_annotation_duration_by_label"),
    ("statistics.visualize_annotation_duration", "annotation_zip.visualize_annotation_duration_by_attribute_value"),
    ("filesystem.draw_annotation", "annotation_zip.render"),
    ("task.update_metadata_of_task", "task.update_metadata_per_task"),
    ("input_data.update_metadata_of_input_data", "input_data.update_metadata_per_input_data"),
]


NEW_IMPLEMENTATION_MODULES = {
    "annotation_zip.annotation_count",
    "task_count.output",
    "task_history_event.list_worktime",
    "annotation_zip.visualize_annotation_count",
}


@pytest.mark.parametrize(("old_module", "new_module"), COMMAND_PAIRS)
@pytest.mark.parametrize("import_old", [False, True])
def test_commands_can_be_imported_independently(old_module, new_module, import_old):
    module = old_module if import_old else new_module
    # 各コマンドを新しいプロセスで読み込み、間接的な依存も確認する。
    script = f"""
import importlib
import json
import sys

importlib.import_module('annofabcli.{module}')
print(json.dumps(sorted(sys.modules)))
"""
    result = subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True)
    imported_modules = json.loads(result.stdout)

    if import_old:
        forbidden_modules = {new for _, new in COMMAND_PAIRS} | NEW_IMPLEMENTATION_MODULES
    else:
        forbidden_modules = {old for old, _ in COMMAND_PAIRS}
    assert not {f"annofabcli.{name}" for name in forbidden_modules}.intersection(imported_modules)
