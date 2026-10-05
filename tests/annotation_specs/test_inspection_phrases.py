import copy
import json
from argparse import Namespace
from unittest.mock import Mock

import pytest

from annofabcli.annotation_specs.inspection_phrases import (
    EditInspectionPhrases,
    InspectionPhraseInput,
    build_request_body_for_inspection_phrases,
    read_inspection_phrases_csv,
    read_inspection_phrases_json,
)
from annofabcli.annotation_specs.list_annotation_specs_inspection_phrase import create_inspection_phrase_list


@pytest.fixture
def annotation_specs():
    return {
        "inspection_phrases": [
            {
                "id": "wrong_label",
                "text": {
                    "default_lang": "en-US",
                    "messages": [
                        {"lang": "en-US", "message": "Wrong label"},
                        {"lang": "ja-JP", "message": "ラベルが間違っています"},
                        {"lang": "fr-FR", "message": "Mauvaise etiquette"},
                    ],
                },
            },
            {"id": "position", "text": {"default_lang": "ja-JP", "messages": [{"lang": "ja-JP", "message": "位置がずれています"}]}},
        ],
        "labels": [{"label_id": "label1"}],
        "additionals": [],
        "restrictions": [],
        "metadata": {"sample": "value"},
        "updated_datetime": "2026-10-05T00:00:00+09:00",
    }


@pytest.mark.parametrize(("field", "lang"), [("inspection_phrase_text_ja", "ja-JP"), ("inspection_phrase_text_en", "en-US"), ("inspection_phrase_text_vi", "vi-VN")])
def test_どの言語でも単独で追加でき他言語に補完しない(annotation_specs, field, lang):
    original = copy.deepcopy(annotation_specs)
    item = InspectionPhraseInput.model_validate({"inspection_phrase_id": "new", field: "本文"})
    actual = build_request_body_for_inspection_phrases(annotation_specs, operation="add", phrase_inputs=[item])
    assert actual["inspection_phrases"][-1] == {"id": "new", "text": {"default_lang": lang, "messages": [{"lang": lang, "message": "本文"}]}}
    assert actual["labels"] == original["labels"]
    assert actual["metadata"] == original["metadata"]
    assert actual["last_updated_datetime"] == original["updated_datetime"]
    assert annotation_specs == original


@pytest.mark.parametrize(
    "data",
    [
        {"inspection_phrase_id": "id"},
        {"inspection_phrase_id": "id", "inspection_phrase_text_ja": "", "inspection_phrase_text_en": None, "inspection_phrase_text_vi": "  "},
        {"inspection_phrase_id": "invalid id", "inspection_phrase_text_en": "text"},
        {"inspection_phrase_id": "", "inspection_phrase_text_en": "text"},
        {"inspection_phrase_id": 123, "inspection_phrase_text_en": "text"},
        {"inspection_phrase_id": "id", "inspection_phrase_text_en": 123},
        {"inspection_phrase_id": "id", "inspection_phrase_text_en": "text", "unknown": "value"},
    ],
)
def test_不正な入力を拒否する(data):
    with pytest.raises(ValueError):
        InspectionPhraseInput.model_validate(data)


def test_更新は指定言語だけ変更し既定言語と未知の言語も保持する(annotation_specs):
    original = copy.deepcopy(annotation_specs)
    item = InspectionPhraseInput(inspection_phrase_id="wrong_label", inspection_phrase_text_ja="修正してください", inspection_phrase_text_en="", inspection_phrase_text_vi="sua")
    actual = build_request_body_for_inspection_phrases(annotation_specs, operation="update", phrase_inputs=[item], comment="変更理由")
    assert actual["inspection_phrases"][0]["text"] == {
        "default_lang": "en-US",
        "messages": [
            {"lang": "en-US", "message": "Wrong label"},
            {"lang": "ja-JP", "message": "修正してください"},
            {"lang": "fr-FR", "message": "Mauvaise etiquette"},
            {"lang": "vi-VN", "message": "sua"},
        ],
    }
    assert actual["inspection_phrases"][1] == original["inspection_phrases"][1]
    assert actual["comment"] == "変更理由"
    assert annotation_specs == original


def test_指定したIDだけ削除する(annotation_specs):
    actual = build_request_body_for_inspection_phrases(annotation_specs, operation="delete", phrase_ids=["wrong_label", "position"])
    assert actual["inspection_phrases"] == []
    assert len(annotation_specs["inspection_phrases"]) == 2
    assert actual["labels"] == annotation_specs["labels"]


@pytest.mark.parametrize(
    ("operation", "ids"),
    [
        ("add", ["wrong_label"]),
        ("add", ["new", "new"]),
        ("update", ["position", "missing"]),
        ("delete", ["position", "missing"]),
        ("delete", ["position", "position"]),
        ("add", []),
        ("update", []),
        ("delete", []),
    ],
)
def test_衝突や存在しないIDや重複や空の入力を拒否する(annotation_specs, operation, ids):
    original = copy.deepcopy(annotation_specs)
    inputs = [InspectionPhraseInput(inspection_phrase_id=phrase_id, inspection_phrase_text_en="text") for phrase_id in ids]
    with pytest.raises(ValueError):
        build_request_body_for_inspection_phrases(annotation_specs, operation=operation, phrase_inputs=inputs, phrase_ids=ids)
    assert annotation_specs == original


def test_JSON文字列とファイルを読み込む(tmp_path):
    data = [{"inspection_phrase_id": "1", "inspection_phrase_text_vi": "sua"}]
    source = json.dumps(data)
    path = tmp_path / "phrases.json"
    path.write_text(source, encoding="utf-8")
    assert read_inspection_phrases_json(source) == read_inspection_phrases_json(f"file://{path}")


@pytest.mark.parametrize("data", [{"inspection_phrase_id": "id"}, [None], ["text"]])
def test_JSON配列以外や不正な要素を拒否する(data):
    with pytest.raises((TypeError, ValueError)):
        read_inspection_phrases_json(json.dumps(data))


def test_CSVは数値に見えるIDとNAを文字列として保持する(tmp_path):
    path = tmp_path / "phrases.csv"
    path.write_text("inspection_phrase_id,inspection_phrase_text_ja,inspection_phrase_text_en\n001,日本語,\nNA,,NA\n", encoding="utf-8")
    assert read_inspection_phrases_csv(path) == [
        InspectionPhraseInput(inspection_phrase_id="001", inspection_phrase_text_ja="日本語"),
        InspectionPhraseInput(inspection_phrase_id="NA", inspection_phrase_text_en="NA"),
    ]


@pytest.mark.parametrize("csv_text", ["inspection_phrase_text_en\ntext\n", "inspection_phrase_id,unknown\nid,text\n", "inspection_phrase_id,inspection_phrase_text_en\nid,\n"])
def test_CSVの必須列や本文不足や未知の列を拒否する(tmp_path, csv_text):
    path = tmp_path / "phrases.csv"
    path.write_text(csv_text, encoding="utf-8")
    with pytest.raises(ValueError):
        read_inspection_phrases_csv(path)


def test_一覧のJSON出力をそのまま読み込める(annotation_specs):
    data = [item.to_dict() for item in create_inspection_phrase_list(annotation_specs["inspection_phrases"])]
    inputs = read_inspection_phrases_json(json.dumps(data))
    actual = build_request_body_for_inspection_phrases(annotation_specs, operation="update", phrase_inputs=inputs)
    assert actual["inspection_phrases"] == annotation_specs["inspection_phrases"]


def make_command(annotation_specs, operation, *, phrase_json=None, phrase_csv=None, ids=None, yes=True) -> tuple[EditInspectionPhrases, Mock]:
    service = Mock()
    service.api.get_annotation_specs.return_value = (annotation_specs, None)
    args = Namespace(project_id="project", inspection_phrase_operation=operation, inspection_phrase_json=phrase_json, inspection_phrase_csv=phrase_csv, inspection_phrase_id=ids, comment=None, yes=yes)
    return EditInspectionPhrases(service, Mock(), args), service


def test_複数件を検証して一度だけ保存する(annotation_specs):
    source = json.dumps([{"inspection_phrase_id": phrase_id, "inspection_phrase_text_en": "text"} for phrase_id in ["new1", "new2"]])
    command, service = make_command(annotation_specs, "add", phrase_json=source)
    command.main()
    service.api.put_annotation_specs.assert_called_once()
    request = service.api.put_annotation_specs.call_args.kwargs["request_body"]
    assert [item["id"] for item in request["inspection_phrases"]] == ["wrong_label", "position", "new1", "new2"]
    assert request["last_updated_datetime"] == annotation_specs["updated_datetime"]


def test_途中の対象が存在しなければ保存しない(annotation_specs):
    command, service = make_command(annotation_specs, "delete", ids=["position", "missing"])
    with pytest.raises(ValueError):
        command.main()
    service.api.put_annotation_specs.assert_not_called()


def test_同じ本文への更新は保存しない(annotation_specs):
    command, service = make_command(annotation_specs, "update", phrase_json='[{"inspection_phrase_id":"position","inspection_phrase_text_ja":"位置がずれています"}]')
    command.main()
    service.api.put_annotation_specs.assert_not_called()


def test_確認で中止したら保存しない(annotation_specs, monkeypatch):
    monkeypatch.setattr("annofabcli.common.cli.prompt_yesnoall", lambda _message: (False, False))
    command, service = make_command(annotation_specs, "delete", ids=["position"], yes=False)
    command.main()
    service.api.put_annotation_specs.assert_not_called()


def test_更新コマンドでCSVを処理する(annotation_specs, tmp_path):
    path = tmp_path / "phrases.csv"
    path.write_text("inspection_phrase_id,inspection_phrase_text_vi\nposition,sua\n", encoding="utf-8")
    command, service = make_command(annotation_specs, "update", phrase_csv=path)
    command.main()
    request = service.api.put_annotation_specs.call_args.kwargs["request_body"]
    assert request["inspection_phrases"][1]["text"]["messages"] == [{"lang": "ja-JP", "message": "位置がずれています"}, {"lang": "vi-VN", "message": "sua"}]


def test_削除対象を一覧ファイルから読み込む(annotation_specs, tmp_path):
    path = tmp_path / "ids.txt"
    path.write_text("position\n", encoding="utf-8")
    command, service = make_command(annotation_specs, "delete", ids=[f"file://{path}"])
    command.main()
    request = service.api.put_annotation_specs.call_args.kwargs["request_body"]
    assert [item["id"] for item in request["inspection_phrases"]] == ["wrong_label"]
