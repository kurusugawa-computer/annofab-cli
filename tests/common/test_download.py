import asyncio
import configparser
from pathlib import Path

import annofabapi
import pytest

from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.download import DownloadingFile

# webapiにアクセスするテストモジュール
pytestmark = pytest.mark.access_webapi

inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]

service = annofabapi.build()

out_path = Path("./tests/out/download")
data_path = Path("./tests/data")

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)


def test_download_all_file_with_async():
    downloading_obj = DownloadingFile(service)
    is_latest = False
    wait_options = WaitOptions(interval=60, max_tries=360)
    loop = asyncio.get_event_loop()
    gather = asyncio.gather(
        downloading_obj.download_input_data_json_with_async(
            project_id,
            dest_path=str(out_path / "input_data.json"),
            is_latest=is_latest,
            wait_options=wait_options,
        ),
        downloading_obj.download_task_json_with_async(project_id, dest_path=str(out_path / "task.json"), is_latest=is_latest, wait_options=wait_options),
        downloading_obj.download_annotation_zip_with_async(project_id, dest_path=str(out_path / "annotation.zip"), is_latest=is_latest, wait_options=wait_options),
        return_exceptions=True,
    )
    loop.run_until_complete(gather)
