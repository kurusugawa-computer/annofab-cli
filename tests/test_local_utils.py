from annofabcli.common.utils import get_file_scheme_path, is_file_scheme


def test_is_file_scheme():
    assert is_file_scheme("file://sample.jpg") == True
    assert is_file_scheme("https://localhost/sample.jpg") == False


def test_get_file_scheme_path():
    assert get_file_scheme_path("file://sample.jpg") == "sample.jpg"
    assert get_file_scheme_path("https://localhost/sample.jpg") is None
