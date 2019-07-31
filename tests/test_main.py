"""

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


def test_task():
    main([
        'task', 'list', '--project_id', project_id, '--task_query',
        f'{{"user_id": "{user_id}", "phase":"acceptance", "status": "complete"}}', '--format', 'csv'
    ])

    main(['task', 'cancel_acceptance', '--project_id', project_id, '--task_id', task_id, '--yes'])

    inspection_comment = datetime.datetime.now().isoformat()
    main([
        'task', 'reject', '--project_id', project_id, '--task_id', task_id, '--comment', inspection_comment,
        '--assign_last_annotator', '--yes'
    ])


def test_project():
    main(['project', 'diff', project_id, project_id])


def test_inspection_comment():
    main(['inspection_comment', 'list', '--project_id', project_id, '--task_id', task_id])
    main(['inspection_comment', 'list_unprocessed', '--project_id', project_id, '--task_id', task_id])


def test_annotation():
    main([
        'annotation', 'list_count', '--project_id', project_id, '--annotation_query', '{"label_name_en": "car"}',
        '--output',
        str(out_path / 'annotation_count.csv')
    ])


def test_annotation_specs():
    main(['annotation_specs', 'list_label', '--project_id', project_id])
    main(['annotation_specs', 'list_label_color', '--project_id', project_id])


def test_project_member():
    main(['project_member', 'invite', '--user_id', user_id, '--role', 'owner', '--project_id', project_id])

    main(['project_member', 'list', '--project_id', project_id])

    main(['project_member', 'copy', project_id, project_id, '--yes'])


#
# def test_print_label_color():
#     main(['print_label_color', project_id])


def test_download():
    out_file = str(out_path / 'tasks.json')
    main(['download', 'task', '--project_id', project_id, '--output', out_file])
