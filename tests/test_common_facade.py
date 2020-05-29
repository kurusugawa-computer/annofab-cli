import asyncio
import configparser
import os
from pathlib import Path

import annofabapi

from annofabcli.common.facade import AnnofabApiFacade, AnnotationQuery
from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.download import DownloadingFile

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


def test_delete_annotation_for_task():
    task_id = "20190317_3"
    query = AnnotationQuery(label_id="728931a1-d0a2-442c-8e60-36c65ee7b878")
    facade.delete_annotation_for_task(project_id, task_id, query=None)

