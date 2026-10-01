from annofabcli.annotation.list_annotation import get_label_name_ja


def test_get_label_name_ja() -> None:
    label = {
        "label_name": {
            "messages": [
                {"lang": "en-US", "message": "car"},
                {"lang": "ja-JP", "message": "車"},
            ]
        }
    }

    assert get_label_name_ja(label) == "車"
