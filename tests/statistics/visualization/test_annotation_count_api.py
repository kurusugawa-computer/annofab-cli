from unittest.mock import Mock

import pytest

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


def test_counts_tasks_including_zero_without_fetching_all_pages_or_outer_files():
    service = Mock()
    service.api.get_annotation_list.side_effect = [
        ({"total_count": 5817, "list": [{"detail": {"body": {"_type": "Outer"}}}], "over_limit": False}, None),
        ({"total_count": 0, "list": [], "over_limit": False}, None),
    ]
    result = count_annotations_from_api(service, "prj1", [{"task_id": "task1"}, {"task_id": "task2"}])
    assert result.df.to_dict("records") == [
        {"project_id": "prj1", "task_id": "task1", "annotation_count": 5817},
        {"project_id": "prj1", "task_id": "task2", "annotation_count": 0},
    ]
    calls = service.api.get_annotation_list.call_args_list
    assert len(calls) == 2
    assert [call.kwargs["query_params"]["query"]["task_id"] for call in calls] == ["task1", "task2"]
    assert all(call.kwargs["query_params"]["query"]["exact_match_task_id"] for call in calls)
    assert all(call.kwargs["query_params"]["limit"] == 1 and call.kwargs["query_params"]["page"] == 1 for call in calls)
    assert all(call.kwargs["query_params"]["no_aggregate_label_and_input"] for call in calls)
    service.wrapper.get_all_annotation_list.assert_not_called()
    service.wrapper.download.assert_not_called()
    service.api.get_annotation.assert_not_called()


@pytest.mark.parametrize(
    ("include", "exclude", "expected", "queried_labels"),
    [
        (None, None, 5800, [None]),
        (["person"], None, 5700, ["p"]),
        (["person", "person", "background"], None, 5800, ["b", "p"]),
        (None, ["person"], 100, ["b"]),
        ([], None, 0, []),
        (["unknown"], None, 0, []),
        (None, ["person", "background"], 0, []),
    ],
)
def test_label_filters_are_applied_to_total_count(include, exclude, expected, queried_labels):
    service = Mock()
    service.api.get_annotation_specs.return_value = (
        {"labels": [{"label_id": label_id, "label_name": {"messages": [{"lang": "en-US", "message": name}]}} for label_id, name in [("p", "person"), ("b", "background")]]},
        None,
    )

    def get_annotation_list(_project_id, *, query_params):
        label_id = query_params["query"].get("label_id")
        return {"total_count": {None: 5800, "p": 5700, "b": 100}[label_id], "list": [{}], "over_limit": False}, None

    service.api.get_annotation_list.side_effect = get_annotation_list
    result = count_annotations_from_api(service, "prj1", [{"task_id": "task1"}], include_labels=include, exclude_labels=exclude)
    assert result.df["annotation_count"].tolist() == [expected]
    assert [call.kwargs["query_params"]["query"].get("label_id") for call in service.api.get_annotation_list.call_args_list] == queried_labels


@pytest.mark.parametrize(("total_count", "over_limit"), [(10_000, False), (13_000, True), (615_451, True)])
def test_large_counts_do_not_fetch_more_pages_or_split_inputs(total_count, over_limit):
    service = Mock()
    service.api.get_annotation_list.return_value = ({"total_count": total_count, "list": [{}], "over_limit": over_limit}, None)
    result = count_annotations_from_api(service, "prj1", [{"task_id": "task1", "input_data_id_list": ["input1", "input2"]}])
    assert result.df["annotation_count"].tolist() == [total_count]
    assert service.api.get_annotation_list.call_count == 1
    service.api.get_task.assert_not_called()


def test_label_filtered_total_count_can_exceed_limit():
    service = Mock()
    service.api.get_annotation_specs.return_value = (
        {"labels": [{"label_id": "p", "label_name": {"messages": [{"lang": "en-US", "message": "person"}]}}]},
        None,
    )
    service.api.get_annotation_list.return_value = ({"total_count": 13_000, "over_limit": True}, None)
    result = count_annotations_from_api(service, "prj1", [{"task_id": "task1"}], include_labels=["person"])
    assert result.df["annotation_count"].tolist() == [13_000]
    assert service.api.get_annotation_list.call_count == 1


def test_api_failure_does_not_return_partial_count():
    service = Mock()
    service.api.get_annotation_list.side_effect = [({"total_count": 1}, None), OSError()]
    with pytest.raises(OSError):
        count_annotations_from_api(service, "prj1", [{"task_id": "task1"}, {"task_id": "task2"}])
    service.wrapper.download_annotation_zip.assert_not_called()


def test_empty_tasks():
    service = Mock()
    result = count_annotations_from_api(service, "prj1", [])
    assert result.is_empty()
    assert list(result.df.columns) == ["project_id", "task_id", "annotation_count"]
    service.api.get_annotation_list.assert_not_called()
