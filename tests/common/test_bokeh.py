from annofabcli.common.bokeh import create_pretext_from_metadata


def test__create_pretext_from_metadata() -> None:
    metadata = {
        "project_id": "id1",
        "project_title": "title1",
    }
    pretext = create_pretext_from_metadata(metadata)
    assert pretext.text == 'project_id = "id1"\nproject_title = "title1"'
