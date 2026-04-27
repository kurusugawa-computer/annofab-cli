from __future__ import annotations

import pytest

from annofabcli.annotation_specs import change_attribute_type


class TestCreateConfirmMessageForChangeAttributeType:
    def test_used_label(self) -> None:
        actual = change_attribute_type.create_confirm_message_for_change_attribute_type(
            attribute_name_en="type",
            attribute_id="attr1",
            current_type="select",
            target_type="choice",
            has_annotation_with_label_having_attribute=True,
        )

        assert "この属性を含むラベルがアノテーションで使われています。" in actual
        assert "3次元エディタでは属性値が消えてしまう恐れがあります。" in actual

    def test_unused_label(self) -> None:
        actual = change_attribute_type.create_confirm_message_for_change_attribute_type(
            attribute_name_en="type",
            attribute_id="attr1",
            current_type="select",
            target_type="choice",
            has_annotation_with_label_having_attribute=False,
        )

        assert "この属性を含むラベルがアノテーションで使われていることは確認できませんでした。" in actual
        assert "3次元エディタでは属性値が消えてしまう恐れがあります。" not in actual


class TestValidateAttributeTypeConversion:
    def test_validate_attribute_type_conversion__unsupported(self) -> None:
        with pytest.raises(ValueError):
            change_attribute_type.validate_attribute_type_conversion(current_type="flag", target_type="text")

    def test_validate_attribute_type_conversion__same_type(self) -> None:
        with pytest.raises(ValueError):
            change_attribute_type.validate_attribute_type_conversion(current_type="text", target_type="text")
