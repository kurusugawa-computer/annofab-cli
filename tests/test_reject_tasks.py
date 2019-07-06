"""

"""
import annofabcli
import configparser
import os
import datetime

from annofabcli.__main__ import main

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read('./pytest.ini', 'UTF-8')
annofab_config = dict(inifile.items('annofab'))

project_id = annofab_config['project_id']
task_id = annofab_config['task_id']

subcommand = 'reject_tasks'

def test_main():
    inspection_comment = str_now = datetime.datetime.now().isoformat()
    main([subcommand, '--project_id', project_id, '--task_id', task_id, '--comment', inspection_comment, '--assign_last_annotator', '--yes' ])
