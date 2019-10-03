"""

"""
import configparser
import datetime
import os
from pathlib import Path

import annofabapi

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
data_path = Path('./tests/data')

# def test_complete_tasks():
#     #main(['complete_tasks', '--project_id', project_id, '--task_id', task_id, '--yes' ])


class TestInputData:
    command_name = "input_data"

    def test_put_input_data(self):
        csv_file = str(data_path / "input_data2.csv")
        # スキップするバージョン
        main([self.command_name, 'put', '--project_id', project_id, '--csv', csv_file, '--yes'])
        # 上書きするバージョン
        # main([self.command_name, 'put', '--project_id', project_id, '--csv', csv_file, '--overwrite', '--yes'])


def get_organization_name(project_id: str) -> str:
    organization, _ = service.api.get_organization_of_project(project_id)
    return organization["organization_name"]


class TestTask:
    command_name = "task"

    def test_list(self):
        main([
            self.command_name, 'list', '--project_id', project_id, '--task_query',
            f'{{"user_id": "{user_id}", "phase":"acceptance", "status": "complete"}}', '--format', 'csv'
        ])

    def test_cancel_acceptance(self):
        main([self.command_name, 'cancel_acceptance', '--project_id', project_id, '--task_id', task_id, '--yes'])

    def test_reject_task(self):
        inspection_comment = datetime.datetime.now().isoformat()
        main([
            self.command_name, 'reject', '--project_id', project_id, '--task_id', task_id, '--comment',
            inspection_comment, '--yes'
        ])

    def test_change_operator(self):
        # user指定
        main([
            self.command_name, 'change_operator', '--project_id', project_id, '--task_id', task_id, '--user_id',
            user_id, '--yes'
        ])

        # 未割り当て
        main([
            self.command_name, 'change_operator', '--project_id', project_id, '--task_id', task_id, '--not_assign',
            '--yes'
        ])


def test_project():
    main(['project', 'diff', project_id, project_id])

    out_file = str(out_path / 'tasks.json')
    main(['project', 'download', 'task', '--project_id', project_id, '--output', out_file])


def test_inspection_comment():
    main(['inspection_comment', 'list', '--project_id', project_id, '--task_id', task_id])
    main(['inspection_comment', 'list_unprocessed', '--project_id', project_id, '--task_id', task_id])


def test_annotation():
    main([
        'annotation', 'list_count', '--project_id', project_id, '--annotation_query', '{"label_name_en": "car"}',
        '--output',
        str(out_path / 'annotation_count.csv')
    ])


class TestAnnotationSpecs:
    command_name = "annotation_specs"

    def test_annotation_specs_list_label(self):
        out_file = str(out_path / 'anotation_specs_list_label.csv')
        main([self.command_name, 'list_label', '--project_id', project_id, '--format', 'csv', '--output', out_file])

    def test_annotation_specs_list_label_color(self):
        out_file = str(out_path / 'anotation_specs_list_label_color.csv')
        main([
            self.command_name, 'list_label_color', '--project_id', project_id, '--format', 'json', '--output', out_file
        ])

    def test_annotation_specs_histories(self):
        out_file = str(out_path / 'anotaton_specs_histories.csv')
        main([self.command_name, 'history', '--project_id', project_id, '--format', 'csv', '--output', out_file])


def test_project_member():
    main(['project_member', 'invite', '--user_id', user_id, '--role', 'owner', '--project_id', project_id])

    main(['project_member', 'list', '--project_id', project_id])
    organization_name = get_organization_name(project_id)
    main(['project_member', 'list', '--organization', organization_name])

    main(['project_member', 'copy', project_id, project_id, '--yes'])

    csv_file = str(data_path / "project_members.csv")
    main(['project_member', 'put', '--project_id', project_id, '--csv', csv_file, '--yes'])


def test_filesystem():
    zip_path = data_path / "simple-annotation.zip"
    output_image_dir = out_path / "annotation-image"
    label_color_file = data_path / "label_color.json"

    main([
        'filesystem', 'write_annotation_image', '--annotation',
        str(zip_path), '--output_dir',
        str(output_image_dir), '--image_size', '64x64', '--label_color', f"file://{str(label_color_file)}",
        '--image_extension', 'jpg'
    ])


def test_input_data():
    out_file = str(out_path / 'input_data.json')
    main([
        'input_data', 'list', '--project_id', project_id, '--input_data_query', '{"input_data_name": "abcdefg"}',
        '--add_details', '--output', out_file
    ])


def test_instruction():
    html_file = str(data_path / 'instruction.html')
    print(html_file)
    main(['instruction', 'upload', '--project_id', project_id, '--html', html_file])
