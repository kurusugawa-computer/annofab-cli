from unittest.mock import Mock

import pytest

from annofabcli.common.exceptions import AnnofabCliException
from annofabcli.statistics.visualization.annotation_count_api import AnnotationCountSource, count_annotations_from_api, resolve_annotation_count_source


@pytest.mark.parametrize(
    ("types", "expected"),
    [
        (["user_instance_segment"], AnnotationCountSource.API),
        (["user_semantic_segment", "user_bounding_box"], AnnotationCountSource.API),
        (["user_bounding_box"], AnnotationCountSource.ZIP),
        (["segmentation", "segmentation_v2"], AnnotationCountSource.ZIP),
        ([], AnnotationCountSource.ZIP),
    ],
)
def test_auto_source(types, expected):
    service = Mock()
    service.api.get_annotation_specs.return_value = ({"labels": [{"annotation_type": value} for value in types]}, None)
    assert resolve_annotation_count_source(service, "prj1", AnnotationCountSource.AUTO) == expected


@pytest.mark.parametrize("source", [AnnotationCountSource.API, AnnotationCountSource.ZIP])
def test_explicit_source_does_not_fetch_specs(source):
    service = Mock()
    assert resolve_annotation_count_source(service, "prj1", source) == source
    service.api.get_annotation_specs.assert_not_called()


def test_counts_tasks_including_zero_without_fetching_outer_files():
    service = Mock()
    service.wrapper.get_all_annotation_list.side_effect = [[{"detail": {"body": {"_type": "Outer"}}}] * 3, []]
    result = count_annotations_from_api(service, "prj1", [{"task_id": "task1"}, {"task_id": "task2"}])
    assert result.df.to_dict("records") == [
        {"project_id": "prj1", "task_id": "task1", "annotation_count": 3},
        {"project_id": "prj1", "task_id": "task2", "annotation_count": 0},
    ]
    service.wrapper.download.assert_not_called()
    service.api.get_annotation.assert_not_called()


@pytest.mark.parametrize(
    ("include", "exclude", "expected"),
    [(None, None, 3), (["person"], None, 2), (None, ["person"], 1), ([], None, 0)],
)
def test_label_filters(include, exclude, expected):
    service = Mock()
    service.api.get_annotation_specs.return_value = (
        {"labels": [{"label_id": label_id, "label_name": {"messages": [{"lang": "en-US", "message": name}]}} for label_id, name in [("p", "person"), ("b", "background")]]},
        None,
    )
    service.wrapper.get_all_annotation_list.return_value = [{"detail": {"label_id": label_id}} for label_id in ["p", "b", "p"]]
    result = count_annotations_from_api(service, "prj1", [{"task_id": "task1"}], include_labels=include, exclude_labels=exclude)
    assert result.df["annotation_count"].tolist() == [expected]


def test_task_limit_retries_inputs_without_double_counting():
    service = Mock()
    service.wrapper.get_all_annotation_list.side_effect = [[{}] * 10_000, [{}] * 6_000, [{}] * 7_000]
    result = count_annotations_from_api(service, "prj1", [{"task_id": "task1", "input_data_id_list": ["input1", "input2"]}])
    assert result.df["annotation_count"].tolist() == [13_000]
    queries = [call.kwargs["query_params"]["query"] for call in service.wrapper.get_all_annotation_list.call_args_list]
    assert all(query["task_id"] == "task1" and query["exact_match_task_id"] for query in queries)
    assert [query.get("input_data_id") for query in queries] == [None, "input1", "input2"]
    assert all(query["exact_match_input_data_id"] for query in queries[1:])


def test_input_limit_fails_instead_of_returning_partial_count():
    service = Mock()
    service.wrapper.get_all_annotation_list.side_effect = [[{}] * 10_000, [{}] * 10_000]
    with pytest.raises(AnnofabCliException):
        count_annotations_from_api(service, "prj1", [{"task_id": "task1", "input_data_id_list": ["input1"]}])


def test_limit_is_checked_before_label_filter():
    service = Mock()
    service.api.get_annotation_specs.return_value = ({"labels": []}, None)
    service.wrapper.get_all_annotation_list.side_effect = [[{"detail": {"label_id": "excluded"}}] * 10_000, []]
    result = count_annotations_from_api(service, "prj1", [{"task_id": "task1", "input_data_id_list": ["input1"]}], include_labels=[])
    assert result.df["annotation_count"].tolist() == [0]
    assert service.wrapper.get_all_annotation_list.call_count == 2


def test_api_failure_does_not_return_partial_count():
    service = Mock()
    service.wrapper.get_all_annotation_list.side_effect = [[{}], OSError()]
    with pytest.raises(OSError):
        count_annotations_from_api(service, "prj1", [{"task_id": "task1"}, {"task_id": "task2"}])
    service.wrapper.download_annotation_archive.assert_not_called()


def test_empty_tasks():
    service = Mock()
    result = count_annotations_from_api(service, "prj1", [])
    assert result.is_empty()
    assert list(result.df.columns) == ["project_id", "task_id", "annotation_count"]
    service.wrapper.get_all_annotation_list.assert_not_called()
