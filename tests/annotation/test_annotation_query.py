import pytest
from annofabapi.dataclass.annotation import AdditionalDataV1

from annofabcli.annotation.annotation_query import AnnotationQueryForCLI


class TestAnnotationQueryForCLI:
    ANNOTATION_SPECS = {  # noqa: RUF012
        "labels": [
            {
                "label_id": "9d6cca8d-3f5a-4808-a6c9-0ae18a478176",
                "label_name": {
                    "messages": [{"lang": "ja-JP", "message": "自動車"}, {"lang": "en-US", "message": "car"}],
                    "default_lang": "ja-JP",
                },
                "annotation_type": "bounding_box",
                "additional_data_definitions": [
                    "cbb0155f-1631-48e1-8fc3-43c5f254b6f2",
                    "d349e76d-b59a-44cd-94b4-713a00b2e84d",
                    "ec27de5d-122c-40e7-89bc-5500e37bae6a",
                ],
            },
            {
                "label_id": "39d05700-7c12-4732-bc35-02d65367cc3e",
                "label_name": {
                    "messages": [{"lang": "ja-JP", "message": "歩行者"}, {"lang": "en-US", "message": "pedestrian"}],
                    "default_lang": "ja-JP",
                },
                "annotation_type": "bounding_box",
                "additional_data_definitions": [
                    "69a20a12-ef5f-446f-a03e-0c4ab487ff90",
                ],
            },
        ],
        "additionals": [
            {
                "additional_data_definition_id": "d349e76d-b59a-44cd-94b4-713a00b2e84d",
                "name": {
                    "messages": [{"lang": "ja-JP", "message": "トラッキングID"}, {"lang": "en-US", "message": "tracking_id"}],
                    "default_lang": "ja-JP",
                },
                "type": "tracking",
                "choices": [],
            },
            {
                "additional_data_definition_id": "cbb0155f-1631-48e1-8fc3-43c5f254b6f2",
                "name": {
                    "messages": [{"lang": "ja-JP", "message": "種別"}, {"lang": "en-US", "message": "car_kind"}],
                    "default_lang": "ja-JP",
                },
                "type": "choice",
                "choices": [
                    {
                        "choice_id": "7512ee39-8073-4e24-9b8c-93d99b76b7d2",
                        "name": {
                            "messages": [
                                {"lang": "ja-JP", "message": "車両一般"},
                                {"lang": "en-US", "message": "general_car"},
                            ],
                            "default_lang": "ja-JP",
                        },
                    },
                    {
                        "choice_id": "c07f9702-4760-4e7c-824d-b87bac356a80",
                        "name": {
                            "messages": [
                                {"lang": "ja-JP", "message": "緊急車両"},
                                {"lang": "en-US", "message": "emergency_vehicle"},
                            ],
                            "default_lang": "ja-JP",
                        },
                    },
                    {
                        "choice_id": "75e848f81a-ce06-4669-bd07-4af96306de56",
                        "name": {
                            "messages": [
                                {"lang": "ja-JP", "message": "重機"},
                                {"lang": "en-US", "message": "construction_vehicle"},
                            ],
                            "default_lang": "ja-JP",
                        },
                    },
                ],
            },
            {
                "additional_data_definition_id": "ec27de5d-122c-40e7-89bc-5500e37bae6a",
                "name": {
                    "messages": [{"lang": "ja-JP", "message": "車線"}, {"lang": "en-US", "message": "traffic_lane"}],
                    "default_lang": "ja-JP",
                },
                "type": "integer",
                "choices": [],
            },
            {
                "additional_data_definition_id": "69a20a12-ef5f-446f-a03e-0c4ab487ff90",
                "name": {
                    "messages": [{"lang": "ja-JP", "message": "隠れ"}, {"lang": "en-US", "message": "occlusion"}],
                    "default_lang": "ja-JP",
                },
                "type": "flag",
                "choices": [],
            },
        ],
    }

    def test_normal(self):
        query = AnnotationQueryForCLI(label="car", attributes={"car_kind": "emergency_vehicle", "traffic_lane": 1, "tracking_id": "foo"})
        actual = query.to_query_for_api(self.ANNOTATION_SPECS)
        assert actual.label_id == "9d6cca8d-3f5a-4808-a6c9-0ae18a478176"

        expected_attributes = [
            AdditionalDataV1(
                additional_data_definition_id="cbb0155f-1631-48e1-8fc3-43c5f254b6f2",
                flag=None,
                comment=None,
                integer=None,
                choice="c07f9702-4760-4e7c-824d-b87bac356a80",
            ),
            AdditionalDataV1(
                additional_data_definition_id="ec27de5d-122c-40e7-89bc-5500e37bae6a",
                flag=None,
                comment=None,
                integer=1,
                choice=None,
            ),
            AdditionalDataV1(
                additional_data_definition_id="d349e76d-b59a-44cd-94b4-713a00b2e84d",
                flag=None,
                comment="foo",
                integer=None,
                choice=None,
            ),
        ]
        assert actual.attributes == expected_attributes

    def test_normal2(self):
        query = AnnotationQueryForCLI(label="pedestrian", attributes={"occlusion": True})
        actual = query.to_query_for_api(self.ANNOTATION_SPECS)
        assert actual.label_id == "39d05700-7c12-4732-bc35-02d65367cc3e"

        expected_attributes = [
            AdditionalDataV1(
                additional_data_definition_id="69a20a12-ef5f-446f-a03e-0c4ab487ff90",
                flag=True,
                comment=None,
                integer=None,
                choice=None,
            )
        ]
        assert actual.attributes == expected_attributes

    def test_normal3(self):
        # 属性を未指定
        query = AnnotationQueryForCLI(label="car", attributes={"car_kind": None})
        actual = query.to_query_for_api(self.ANNOTATION_SPECS)
        assert actual.label_id == "9d6cca8d-3f5a-4808-a6c9-0ae18a478176"

        expected_attributes = [
            AdditionalDataV1(
                additional_data_definition_id="cbb0155f-1631-48e1-8fc3-43c5f254b6f2",
                flag=None,
                comment=None,
                integer=None,
                choice=None,
            )
        ]
        assert actual.attributes == expected_attributes

    def test_normal4(self):
        # ラベルだけ指定する
        query = AnnotationQueryForCLI(label="car")
        actual = query.to_query_for_api(self.ANNOTATION_SPECS)
        assert actual.label_id == "9d6cca8d-3f5a-4808-a6c9-0ae18a478176"
        assert actual.attributes is None

    def test_exception_not_exists(self):
        query1 = AnnotationQueryForCLI(label="car__")
        with pytest.raises(ValueError):
            # 存在しないラベル名を指定している
            query1.to_query_for_api(self.ANNOTATION_SPECS)

        query2 = AnnotationQueryForCLI(label="car", attributes={"traffic_lane__": 1})
        with pytest.raises(ValueError):
            # 存在しない属性名を指定している
            query2.to_query_for_api(self.ANNOTATION_SPECS)

        query3 = AnnotationQueryForCLI(label="car", attributes={"car_kind": "emergency_vehicle__"})
        with pytest.raises(ValueError):
            # 存在しない選択肢名を指定している
            query3.to_query_for_api(self.ANNOTATION_SPECS)

    def test_exception_multiple_label(self):
        multiple_label_specs = {
            "labels": [
                {
                    "label_id": "9d6cca8d-3f5a-4808-a6c9-0ae18a478176",
                    "label_name": {
                        "messages": [{"lang": "ja-JP", "message": "自動車"}, {"lang": "en-US", "message": "car"}],
                        "default_lang": "ja-JP",
                    },
                    "annotation_type": "bounding_box",
                    "additional_data_definitions": [
                        "cbb0155f-1631-48e1-8fc3-43c5f254b6f2",
                        "d349e76d-b59a-44cd-94b4-713a00b2e84d",
                        "ec27de5d-122c-40e7-89bc-5500e37bae6a",
                    ],
                },
                {
                    "label_id": "39d05700-7c12-4732-bc35-02d65367cc3e",
                    "label_name": {
                        "messages": [{"lang": "ja-JP", "message": "自動車"}, {"lang": "en-US", "message": "car"}],
                        "default_lang": "ja-JP",
                    },
                    "annotation_type": "bounding_box",
                    "additional_data_definitions": [
                        "69a20a12-ef5f-446f-a03e-0c4ab487ff90",
                    ],
                },
            ]
        }
        query = AnnotationQueryForCLI(label="car")
        with pytest.raises(ValueError):
            query.to_query_for_api(multiple_label_specs)

    def test_exception_multiple_attribute(self):
        annotation_specs = {
            "labels": [
                {
                    "label_id": "9d6cca8d-3f5a-4808-a6c9-0ae18a478176",
                    "label_name": {
                        "messages": [{"lang": "ja-JP", "message": "自動車"}, {"lang": "en-US", "message": "car"}],
                        "default_lang": "ja-JP",
                    },
                    "annotation_type": "bounding_box",
                    "additional_data_definitions": [
                        "d349e76d-b59a-44cd-94b4-713a00b2e84d",
                        "ec27de5d-122c-40e7-89bc-5500e37bae6a",
                    ],
                }
            ],
            "additionals": [
                {
                    "additional_data_definition_id": "d349e76d-b59a-44cd-94b4-713a00b2e84d",
                    "name": {
                        "messages": [
                            {"lang": "ja-JP", "message": "トラッキングID"},
                            {"lang": "en-US", "message": "tracking_id"},
                        ],
                        "default_lang": "ja-JP",
                    },
                    "type": "tracking",
                    "choices": [],
                },
                {
                    "additional_data_definition_id": "ec27de5d-122c-40e7-89bc-5500e37bae6a",
                    "name": {
                        "messages": [
                            {"lang": "ja-JP", "message": "トラッキングID"},
                            {"lang": "en-US", "message": "tracking_id"},
                        ],
                        "default_lang": "ja-JP",
                    },
                    "type": "tracking",
                    "choices": [],
                },
            ],
        }

        query = AnnotationQueryForCLI(label="car", attributes={"tracking_id": "foo"})
        with pytest.raises(ValueError):
            query.to_query_for_api(annotation_specs)

    def test_exception_multiple_choice(self):
        annotation_specs = {
            "labels": [
                {
                    "label_id": "9d6cca8d-3f5a-4808-a6c9-0ae18a478176",
                    "label_name": {
                        "messages": [{"lang": "ja-JP", "message": "自動車"}, {"lang": "en-US", "message": "car"}],
                        "default_lang": "ja-JP",
                    },
                    "annotation_type": "bounding_box",
                    "additional_data_definitions": [
                        "cbb0155f-1631-48e1-8fc3-43c5f254b6f2",
                    ],
                }
            ],
            "additionals": [
                {
                    "additional_data_definition_id": "cbb0155f-1631-48e1-8fc3-43c5f254b6f2",
                    "name": {
                        "messages": [{"lang": "ja-JP", "message": "種別"}, {"lang": "en-US", "message": "car_kind"}],
                        "default_lang": "ja-JP",
                    },
                    "type": "choice",
                    "choices": [
                        {
                            "choice_id": "7512ee39-8073-4e24-9b8c-93d99b76b7d2",
                            "name": {
                                "messages": [
                                    {"lang": "ja-JP", "message": "車両一般"},
                                    {"lang": "en-US", "message": "general_car"},
                                ],
                                "default_lang": "ja-JP",
                            },
                        },
                        {
                            "choice_id": "c07f9702-4760-4e7c-824d-b87bac356a80",
                            "name": {
                                "messages": [
                                    {"lang": "ja-JP", "message": "車両一般"},
                                    {"lang": "en-US", "message": "general_car"},
                                ],
                                "default_lang": "ja-JP",
                            },
                        },
                    ],
                }
            ],
        }

        query = AnnotationQueryForCLI(label="car", attributes={"car_kind": "general_car"})
        with pytest.raises(ValueError):
            query.to_query_for_api(annotation_specs)
