from dataclasses import dataclass

from annofabcli.annotation_zip.annotation_name import AnnotationNameTranslator


@dataclass(frozen=True)
class AnnotationInfo:
    project_id: str
    label: str
    attributes: dict[str, str | int]


def test_annotation_name_translator() -> None:
    annotation_specs = {
        "labels": [
            {
                "label_name": {"messages": [{"lang": "en-US", "message": "car"}, {"lang": "ja-JP", "message": "車"}]},
                "additional_data_definitions": ["type-id", "memo-id"],
            },
            {
                "label_name": {"messages": [{"lang": "en-US", "message": "person"}]},
                "additional_data_definitions": [],
            },
        ],
        "additionals": [
            {
                "additional_data_definition_id": "type-id",
                "name": {"messages": [{"lang": "en-US", "message": "type"}, {"lang": "ja-JP", "message": "種類"}]},
                "choices": [{"name": {"messages": [{"lang": "en-US", "message": "sedan"}, {"lang": "ja-JP", "message": "セダン"}]}}],
            },
            {
                "additional_data_definition_id": "memo-id",
                "name": {"messages": [{"lang": "en-US", "message": "memo"}]},
                "choices": [],
            },
        ],
    }
    translator = AnnotationNameTranslator(annotation_specs)

    assert translator.label_name("car") == "車"
    assert translator.label_name("person") == "person"
    assert translator.attribute_value_key(("car", "type", "sedan")) == ("車", "種類", "セダン")
    assert translator.annotation_info(AnnotationInfo(project_id="project1", label="car", attributes={"type": "sedan", "memo": "free text", "score": 1})) == AnnotationInfo(
        project_id="project1", label="車", attributes={"種類": "セダン", "memo": "free text", "score": 1}
    )
