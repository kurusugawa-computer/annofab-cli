from annofabcli.common.cli import get_json_from_args, get_list_from_args


def test_get_json_from_args():
    expected = {"foo": 1}
    assert get_json_from_args('{"foo": 1}') == expected
    assert get_json_from_args("file://tests/data/arg.json") == expected
    assert get_json_from_args(None) is None


def test_get_list_from_args():
    expected = ["id1", "id2", "id3"]

    actual = get_list_from_args(["id1", "id2", "id3"])
    assert all(a == b for a, b in zip(actual, expected))

    actual = get_list_from_args(["file://tests/data/arg_id_list.txt"])
    assert all(a == b for a, b in zip(actual, expected))

    actual = get_list_from_args(None)
    assert len(actual) == 0
