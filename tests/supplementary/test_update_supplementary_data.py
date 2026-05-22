from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import annofabapi
import pytest

from annofabcli.supplementary.update_supplementary_data import (
    UpdateResult,
    UpdateSupplementaryDataMain,
    create_updated_supplementary_data_list_from_csv,
)


def create_old_supplementary_data() -> dict[str, str | int]:
    return {
        "input_data_id": "input1",
        "supplementary_data_id": "supplementary1",
        "supplementary_data_name": "old_name",
        "supplementary_data_path": "s3://bucket/old_image.jpg",
        "supplementary_data_type": "image",
        "supplementary_data_number": 1,
        "updated_datetime": "2026-01-01T00:00:00.000+09:00",
    }


def create_service() -> tuple[annofabapi.Resource, Mock, Mock]:
    api = Mock()
    wrapper = Mock()
    wrapper.get_supplementary_data_list_or_none.return_value = [create_old_supplementary_data()]
    service = cast(annofabapi.Resource, SimpleNamespace(api=api, wrapper=wrapper))
    return service, api, wrapper


def test_update_supplementary_data_with_url_path() -> None:
    service, api, wrapper = create_service()
    main_obj = UpdateSupplementaryDataMain(service, all_yes=True)

    result = main_obj.update_supplementary_data(
        "project1",
        "input1",
        "supplementary1",
        new_supplementary_data_path="s3://bucket/new_image.jpg",
        new_supplementary_data_number=2,
    )

    assert result == UpdateResult.SUCCESS
    api.put_supplementary_data.assert_called_once_with(
        "project1",
        "input1",
        "supplementary1",
        request_body={
            "input_data_id": "input1",
            "supplementary_data_id": "supplementary1",
            "supplementary_data_name": "old_name",
            "supplementary_data_path": "s3://bucket/new_image.jpg",
            "supplementary_data_type": "image",
            "supplementary_data_number": 2,
            "updated_datetime": "2026-01-01T00:00:00.000+09:00",
            "last_updated_datetime": "2026-01-01T00:00:00.000+09:00",
        },
    )
    wrapper.put_supplementary_data_from_file.assert_not_called()


def test_update_supplementary_data_with_file_scheme_path(tmp_path: Path) -> None:
    supplementary_data_file = tmp_path / "new_image.jpg"
    supplementary_data_file.write_bytes(b"image")
    service, api, wrapper = create_service()
    main_obj = UpdateSupplementaryDataMain(service, all_yes=True)

    result = main_obj.update_supplementary_data(
        "project1",
        "input1",
        "supplementary1",
        new_supplementary_data_name="new_name",
        new_supplementary_data_path=f"file://{supplementary_data_file}",
    )

    assert result == UpdateResult.SUCCESS
    wrapper.put_supplementary_data_from_file.assert_called_once_with(
        "project1",
        input_data_id="input1",
        supplementary_data_id="supplementary1",
        file_path=str(supplementary_data_file),
        request_body={
            "input_data_id": "input1",
            "supplementary_data_id": "supplementary1",
            "supplementary_data_name": "new_name",
            "supplementary_data_path": "s3://bucket/old_image.jpg",
            "supplementary_data_type": "image",
            "supplementary_data_number": 1,
            "updated_datetime": "2026-01-01T00:00:00.000+09:00",
            "last_updated_datetime": "2026-01-01T00:00:00.000+09:00",
        },
    )
    api.put_supplementary_data.assert_not_called()


def test_update_supplementary_data_with_missing_file_scheme_path(tmp_path: Path) -> None:
    service, api, wrapper = create_service()
    main_obj = UpdateSupplementaryDataMain(service, all_yes=True)

    result = main_obj.update_supplementary_data("project1", "input1", "supplementary1", new_supplementary_data_path=f"file://{tmp_path / 'missing.jpg'}")

    assert result == UpdateResult.SKIPPED
    wrapper.put_supplementary_data_from_file.assert_not_called()
    api.put_supplementary_data.assert_not_called()


def test_update_supplementary_data_without_changes() -> None:
    service, api, wrapper = create_service()
    main_obj = UpdateSupplementaryDataMain(service, all_yes=True)

    result = main_obj.update_supplementary_data("project1", "input1", "supplementary1")

    assert result == UpdateResult.SKIPPED
    wrapper.put_supplementary_data_from_file.assert_not_called()
    api.put_supplementary_data.assert_not_called()


def test_create_updated_supplementary_data_list_from_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "supplementary_data.csv"
    csv_path.write_text(
        "input_data_id,supplementary_data_id,supplementary_data_name,supplementary_data_path,supplementary_data_type,supplementary_data_number\ninput1,supplementary1,new_name,,text,2\n"
    )

    supplementary_data_list = create_updated_supplementary_data_list_from_csv(csv_path)

    assert len(supplementary_data_list) == 1
    assert supplementary_data_list[0].input_data_id == "input1"
    assert supplementary_data_list[0].supplementary_data_id == "supplementary1"
    assert supplementary_data_list[0].supplementary_data_name == "new_name"
    assert supplementary_data_list[0].supplementary_data_path is None
    assert supplementary_data_list[0].supplementary_data_type == "text"
    assert supplementary_data_list[0].supplementary_data_number == 2


def test_create_updated_supplementary_data_list_from_csv_without_required_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "supplementary_data.csv"
    csv_path.write_text("input_data_id,supplementary_data_name\ninput1,new_name\n")

    with pytest.raises(ValueError):
        create_updated_supplementary_data_list_from_csv(csv_path)
