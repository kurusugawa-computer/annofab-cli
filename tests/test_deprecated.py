"""
廃止予定のサブコマンドをテストする
"""

import configparser
import datetime
import os
from pathlib import Path

import annofabapi

import annofabcli
from annofabcli.__main__ import main

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read('./pytest.ini', 'UTF-8')
annofab_config = dict(inifile.items('annofab'))

project_id = annofab_config['project_id']
task_id = annofab_config['task_id']

service = annofabapi.build_from_netrc()
user_id = service.api.login_user_id

out_path = Path('./tests/out')

# def test_complete_tasks():
#     #main(['complete_tasks', '--project_id', project_id, '--task_id', task_id, '--yes' ])


def test_cancel_acceptance():
    main(['cancel_acceptance', '--project_id', project_id, '--task_id', task_id, '--yes'])


def test_reject_tasks():
    inspection_comment = datetime.datetime.now().isoformat()
    main([
        'reject_tasks', '--project_id', project_id, '--task_id', task_id, '--comment', inspection_comment,
        '--assign_last_annotator', '--yes'
    ])


def test_diff_projects():
    main(['diff_projects', project_id, project_id])


def test_invite_users():
    main(['invite_users', '--user_id', user_id, '--role', 'owner', '--project_id', project_id])


def test_print_inspections():
    main(['print_inspections', '--project_id', project_id, '--task_id', task_id])


def test_print_label_color():
    main(['print_label_color', '--project_id', project_id])
