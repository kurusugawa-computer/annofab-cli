import json
import os
from pathlib import Path

from annofabcli.annotation_specs.list_attribute_restriction import ListAttributeRestrictionMain

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

data_dir = Path("./tests/data/annotation_specs")
out_dir = Path("./tests/out/annotation_specs")
out_dir.mkdir(exist_ok=True, parents=True)

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")


class TestListAttributeRestrictionMain:
    @classmethod
    def setup_class(cls):
        with (data_dir / "annotation_specs.json").open() as f:
            annotation_specs = json.load(f)

        cls.obj = ListAttributeRestrictionMain(
            labels=annotation_specs["labels"], additionals=annotation_specs["additionals"]
        )
        cls.annotation_specs = annotation_specs

    def test_get_restriction_text(self):
        for restriction in self.annotation_specs["restrictions"]:
            actual = self.obj.get_restriction_text(
                restriction["additional_data_definition_id"], restriction["condition"]
            )
            print(actual)
