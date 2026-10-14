import json
import logging
from pathlib import Path
from unittest.mock import Mock

import annofabapi
import pandas
import pytest
from annofabapi.credentials import IdPass
from pandas.testing import assert_frame_equal

from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE
from annofabcli.common.user_info_mask import UserInfoMasker, create_masked_name
from annofabcli.common.utils import read_multiheader_csv
from annofabcli.statistics.visualization.annotation_count_api import AnnotationCountSource
from annofabcli.statistics.visualization.dataframe.actual_worktime import ActualWorktime
from annofabcli.statistics.visualization.dataframe.annotation_count import AnnotationCount
from annofabcli.statistics.visualization.filtering_query import FilteringQuery
from annofabcli.statistics.visualization.project_dir import ProjectDir, TaskCompletionCriteria
from annofabcli.statistics.visualization.visualization_source_files import VisualizationSourceFiles
from annofabcli.statistics.visualize_statistics import VisualizingStatisticsMain, WriteCsvGraph, read_actual_worktime


@pytest.fixture
def annotation_count_sources(tmp_path):
    service = Mock()
    source = VisualizationSourceFiles(service, "prj1", tmp_path)
    tasks = [
        {"task_id": "selected", "phase": "acceptance", "status": "complete"},
        {"task_id": "ignored", "phase": "acceptance", "status": "complete"},
        {"task_id": "old", "phase": "acceptance", "status": "complete"},
        {"task_id": "unfinished", "phase": "annotation", "status": "not_started"},
    ]
    source.task_json_path.write_text(json.dumps(tasks), encoding="utf-8")
    histories = {
        task["task_id"]: [
            {
                "phase": "annotation",
                "account_id": "account1",
                "accumulated_labor_time_milliseconds": "PT1H",
                "started_datetime": "2020-01-01T00:00:00+09:00" if task["task_id"] == "old" else "2026-10-01T00:00:00+09:00",
            }
        ]
        for task in tasks
    }
    source.task_history_json_path.write_text(json.dumps(histories), encoding="utf-8")
    main = VisualizingStatisticsMain(
        service,
        temp_dir=tmp_path,
        task_completion_criteria=TaskCompletionCriteria.ACCEPTANCE_COMPLETED,
        filtering_query=FilteringQuery(start_date="2026-01-01", ignored_task_ids={"ignored"}),
    )
    return main, source, service


def test_api_count_only_requests_selected_tasks(annotation_count_sources):
    main, source, service = annotation_count_sources
    service.wrapper.get_all_annotation_list.return_value = [{}] * 7
    actual = main._prepare_annotation_count(source, None, AnnotationCountSource.API)
    assert actual.df.to_dict("records") == [{"project_id": "prj1", "task_id": "selected", "annotation_count": 7}]
    queries = [call.kwargs["query_params"]["query"] for call in service.wrapper.get_all_annotation_list.call_args_list]
    assert [query["task_id"] for query in queries] == ["selected"]


def test_csv_count_does_not_require_excluded_tasks_or_call_api(annotation_count_sources):
    main, source, service = annotation_count_sources
    counts = AnnotationCount(pandas.DataFrame([("prj1", "selected", 0)], columns=AnnotationCount.columns()))
    assert main._prepare_annotation_count(source, counts, AnnotationCountSource.AUTO).df["annotation_count"].tolist() == [0]
    service.wrapper.get_all_annotation_list.assert_not_called()
    service.api.get_annotation_specs.assert_not_called()


def test_csv_missing_selected_tasks_fails_without_api_fallback(annotation_count_sources):
    main, source, service = annotation_count_sources
    with pytest.raises(ValueError):
        main._prepare_annotation_count(source, AnnotationCount.empty(), AnnotationCountSource.AUTO)
    service.wrapper.get_all_annotation_list.assert_not_called()


def test_zip_count_does_not_call_api(annotation_count_sources):
    main, source, service = annotation_count_sources
    source.annotation_zip_path.touch()
    assert main._prepare_annotation_count(source, None, AnnotationCountSource.ZIP) is None
    service.wrapper.get_all_annotation_list.assert_not_called()


def test_api_source_files_cannot_be_reused_as_zip_without_archive(annotation_count_sources):
    main, source, service = annotation_count_sources
    service.wrapper.get_all_annotation_list.return_value = [{}] * 7
    assert main._prepare_annotation_count(source, None, AnnotationCountSource.API).df["annotation_count"].tolist() == [7]
    assert not source.annotation_zip_path.exists()

    service.wrapper.get_all_annotation_list.reset_mock()
    with pytest.raises(FileNotFoundError):
        main._prepare_annotation_count(source, None, AnnotationCountSource.ZIP)
    service.wrapper.get_all_annotation_list.assert_not_called()


@pytest.mark.parametrize("option_name", ["actual_worktime_csv", "labor_csv"])
def test_read_actual_worktime(option_name: str, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    csv_path = tmp_path / "actual_worktime.csv"
    csv_path.write_text("project_id,date,account_id,actual_worktime_hour\n001,2026-10-05,002,1.5\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        actual = read_actual_worktime(
            actual_worktime_csv=csv_path if option_name == "actual_worktime_csv" else None,
            labor_csv=csv_path if option_name == "labor_csv" else None,
        )

    assert actual.df.to_dict("records") == [{"project_id": "001", "date": "2026-10-05", "account_id": "002", "actual_worktime_hour": 1.5}]
    if option_name == "labor_csv":
        assert "非推奨" in caplog.text
        assert "--actual_worktime_csv" in caplog.text
        assert "2027/01/01以降に廃止予定" in caplog.text
    else:
        assert not caplog.records


def test_read_actual_worktime_without_csv(caplog: pytest.LogCaptureFixture) -> None:
    actual = read_actual_worktime(actual_worktime_csv=None, labor_csv=None)

    assert actual.is_empty()
    assert "--actual_worktime_csv" in caplog.text


@pytest.mark.parametrize("option_name", ["actual_worktime_csv", "labor_csv"])
def test_read_actual_worktime_missing_columns(option_name: str, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    csv_path = tmp_path / "actual_worktime.csv"
    csv_path.write_text("project_id,date,account_id\n001,2026-10-05,002\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        read_actual_worktime(
            actual_worktime_csv=csv_path if option_name == "actual_worktime_csv" else None,
            labor_csv=csv_path if option_name == "labor_csv" else None,
        )

    assert exc_info.value.code == COMMAND_LINE_ERROR_STATUS_CODE
    error_messages = [record.message for record in caplog.records if record.levelno == logging.ERROR]
    assert len(error_messages) == 1
    assert f"--{option_name}" in error_messages[0]
    assert "actual_worktime_hour" in error_messages[0]


@pytest.mark.parametrize("excluded", [False, True])
def test_visualization_masks_csv_and_graphs_before_writing(tmp_path: Path, *, excluded: bool) -> None:
    source = ProjectDir(Path("tests/data/stat_visualization/mask_visualization_dir/visualization1"), TaskCompletionCriteria.ACCEPTANCE_COMPLETED)
    service = annofabapi.Resource(IdPass("test", "test"))
    masker = UserInfoMasker(
        not_masked_user_ids=frozenset({"chris"}) if excluded else frozenset(),
        not_masked_biographies=frozenset({"Japan"}) if excluded else frozenset(),
    )
    for masked in (False, True):
        writer = WriteCsvGraph(
            service,
            "prj1",
            task_completion_criteria=TaskCompletionCriteria.ACCEPTANCE_COMPLETED,
            filtering_query=FilteringQuery(),
            visualization_source_files=VisualizationSourceFiles(service, "prj1", tmp_path / "source"),
            project_dir=ProjectDir(tmp_path / ("masked" if masked else "original"), TaskCompletionCriteria.ACCEPTANCE_COMPLETED),
            actual_worktime=ActualWorktime.empty(),
            user_info_masker=masker if masked else None,
        )
        writer.task = source.read_task_list()
        writer.task_worktime_obj = source.read_task_worktime_list()
        writer.worktime_per_date = source.read_worktime_per_date_user()
        original_task = writer.task.df.copy()
        original_worktime = writer.worktime_per_date.df.copy()
        original_task_worktime = writer.task_worktime_obj.df.copy()
        writer.prepare_user_info_mask()
        writer.write_user_performance()
        writer.write_task_info()
        writer.write_worktime_per_date(["bob"])
        writer.write_cumulative_linegraph_by_user(["bob"])
        writer.write_user_productivity_per_date(["bob"])
        assert_frame_equal(writer.task.df, original_task)
        assert_frame_equal(writer.worktime_per_date.df, original_worktime)
        assert_frame_equal(writer.task_worktime_obj.df, original_task_worktime)

    masked_ids = ["bob"] if excluded else ["alice", "bob", "chris"]
    replacement = {create_masked_name(user_id): user_id for user_id in masked_ids}
    replacement.update({create_masked_name(value, prefix="category"): value for value in ("Japan", "U.S.", "Germany")})
    for original_csv in (tmp_path / "original").glob("*.csv"):
        masked_csv = tmp_path / "masked" / original_csv.name
        assert masked_csv.exists()
        if original_csv.name in {ProjectDir.FILENAME_USER_PERFORMANCE, ProjectDir.FILENAME_WHOLE_PERFORMANCE}:
            original_df = read_multiheader_csv(str(original_csv), header_row_count=2)
            masked_df = read_multiheader_csv(str(masked_csv), header_row_count=2)
        else:
            original_df = pandas.read_csv(original_csv)
            masked_df = pandas.read_csv(masked_csv)
        # マスクを戻して比較し、全ファイルの集計値と行の対応関係を検証する。
        restored_df = masked_df.replace(replacement)
        columns = list(original_df.columns)
        assert_frame_equal(
            restored_df.sort_values(columns).reset_index(drop=True),
            original_df.sort_values(columns).reset_index(drop=True),
            check_dtype=False,
        )
        for user_id in masked_ids:
            assert f",{user_id}," not in masked_csv.read_text(encoding="utf-8-sig")

    graphs = list((tmp_path / "masked").rglob("*.html"))
    assert graphs
    for graph in graphs:
        text = graph.read_text(encoding="utf-8")
        for user_id in masked_ids:
            assert f'"{user_id}"' not in text
    selected_graph = tmp_path / "masked/line-graph/教師付者用/累積折れ線-横軸_生産量-教師付者用.html"
    assert create_masked_name("bob") in selected_graph.read_text(encoding="utf-8")
