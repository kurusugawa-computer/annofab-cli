from __future__ import annotations

import pytest

from annofabcli.annotation_specs import change_attribute_type


class TestValidateAttributeTypeConversion:
    def test_validate_attribute_type_conversion__unsupported(self) -> None:
        with pytest.raises(ValueError):
            change_attribute_type.validate_attribute_type_conversion(current_type="flag", target_type="text")

    def test_validate_attribute_type_conversion__same_type(self) -> None:
        with pytest.raises(ValueError):
            change_attribute_type.validate_attribute_type_conversion(current_type="text", target_type="text")
