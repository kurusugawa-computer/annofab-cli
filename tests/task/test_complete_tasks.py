from annofabcli.task.complete_tasks import CompleteTasksMain


def test_inspection_list_to_dict():
    inspection_list = [
        {"task_id": "task0", "input_data_id": "input0", "inspection_id": "inspection0"},
        {"task_id": "task1", "input_data_id": "input0", "inspection_id": "inspection1"},
        {"task_id": "task0", "input_data_id": "input1", "inspection_id": "inspection2"},
        {"task_id": "task0", "input_data_id": "input0", "inspection_id": "inspection3"},
    ]

    expected = {
        "task1": {"input0": [{"task_id": "task1", "input_data_id": "input0", "inspection_id": "inspection1"}]},
        "task0": {
            "input1": [{"task_id": "task0", "input_data_id": "input1", "inspection_id": "inspection2"}],
            "input0": [
                {"task_id": "task0", "input_data_id": "input0", "inspection_id": "inspection0"},
                {"task_id": "task0", "input_data_id": "input0", "inspection_id": "inspection3"},
            ],
        },
    }

    assert CompleteTasksMain.inspection_list_to_dict(inspection_list) == expected
