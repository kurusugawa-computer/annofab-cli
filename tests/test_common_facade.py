import configparser
import os
from pathlib import Path

import annofabapi

from annofabcli.common.facade import AdditionalDataForCli, AnnofabApiFacade, AnnotationQuery, AnnotationQueryForCli

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]

service = annofabapi.build_from_netrc()
facade = AnnofabApiFacade(service)
out_path = Path("./tests/out/facade")
data_path = Path("./tests/data/facade")


def test_get_annotation_list_for_task():
    task_id = "20190317_3"
    query = AnnotationQuery(label_id="728931a1-d0a2-442c-8e60-36c65ee7b878")
    result = facade.get_annotation_list_for_task(project_id, task_id, query=query)
    print(len(result))
    print(result)


class Test_to_annotation_query_from_cli:
    def test_exists_label_name(self):
        query = AnnotationQueryForCli(label_name_en="car")
        print(facade.to_annotation_query_from_cli(project_id, query))

    def test_exists_label_id(self):
        query = AnnotationQueryForCli(label_id="728931a1-d0a2-442c-8e60-36c65ee7b878")
        print(facade.to_annotation_query_from_cli(project_id, query))

    def test_exists_choice_name(self):
        attributes = [AdditionalDataForCli(additional_data_definition_name_en="category", choice_name_en="bike")]
        query = AnnotationQueryForCli(label_name_en="whole", attributes=attributes)
        print(facade.to_annotation_query_from_cli(project_id, query))

    def test_exists_choice_id(self):
        attributes = [
            AdditionalDataForCli(
                additional_data_definition_id="550a8d24-f5ae-496e-9d11-20f308a93b94",
                choice="2701e187-b2b4-43ab-9426-568c574e508a",
            )
        ]
        query = AnnotationQueryForCli(label_name_en="whole", attributes=attributes)
        print(facade.to_annotation_query_from_cli(project_id, query))
