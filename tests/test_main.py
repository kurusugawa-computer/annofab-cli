"""

"""
import configparser
import datetime
import json
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


def get_organization_name(project_id: str) -> str:
    organization, _ = service.api.get_organization_of_project(project_id)
    return organization["organization_name"]


def test_task():
    main([
        'task', 'list', '--project_id', project_id, '--task_query',
        f'{{"user_id": "{user_id}", "phase":"acceptance", "status": "complete"}}', '--format', 'csv'
    ])

    main(['task', 'cancel_acceptance', '--project_id', project_id, '--task_id', task_id, '--yes'])

    inspection_comment = datetime.datetime.now().isoformat()
    main(['task', 'reject', '--project_id', project_id, '--task_id', task_id, '--comment', inspection_comment, '--yes'])


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


def test_annotation_specs():
    main(['annotation_specs', 'list_label', '--project_id', project_id])
    main(['annotation_specs', 'list_label_color', '--project_id', project_id])


def test_project_member():
    main(['project_member', 'invite', '--user_id', user_id, '--role', 'owner', '--project_id', project_id])

    main(['project_member', 'list', '--project_id', project_id])
    organization_name = get_organization_name(project_id)
    main(['project_member', 'list', '--organization', organization_name])

    main(['project_member', 'copy', project_id, project_id, '--yes'])

    csv_file = str(data_path / "project_members.csv")
    main(['project_member', 'put', '--project_id', project_id, '--csv', csv_file, '--yes'])


def test_filesystem():
    zip_path = test_dir / "simple-annotation.zip"
    output_image_dir = out_dir / "annotation-image"

    with (test_dir / "label_color.json").open(encoding="utf-8") as f:
        label_color_json = json.load(f)
        label_color_dict = {label_name: tuple(rgb) for label_name, rgb in label_color_json.items()}

    main([
        'filesystem', 'write_annotation_image', '--annotation',
        str(zip_path), '--output_dir',
        str(output_image_dir), '--image_size', '64x64', '--label_color_file'
        '--add_details', '--output', out_file
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


test_dir = Path('./tests/data')
out_dir = Path('./tests/out')

with (test_dir / "label_color.json").open(encoding="utf-8") as f:
    label_color_json = json.load(f)
    label_color_dict = {label_name: tuple(rgb) for label_name, rgb in label_color_json.items()}


def test_write_image():
    zip_path = test_dir / "simple-annotation.zip"
    output_image_file = out_dir / "annotation.png"

    with zipfile.ZipFile(zip_path) as zip_file:
        parser = SimpleAnnotationZipParser(zip_file, "sample_1/.__tests__data__lenna.png.json")

        write_annotation_image(parser=parser, image_size=(64, 64), label_color_dict=label_color_dict,
                               output_image_file=output_image_file, background_color=(64, 64, 64))


def test_write_image_wihtout_outer_file():
    output_image_file = out_dir / "annotation_without_painting.png"

    # 外部ファイルが見つからない状態で画像を生成する。
    parser = SimpleAnnotationDirParser(test_dir / "simple-annotation.json")
    write_annotation_image(parser=parser, image_size=(64, 64), label_color_dict=label_color_dict,
                           output_image_file=output_image_file, background_color=(64, 64, 64))


def test_write_annotation_images_from_path():
    zip_path = test_dir / "simple-annotation.zip"
    output_image_dir = out_dir / "annotation-image"

    def is_target_parser_func(parser: SimpleAnnotationParser) -> bool:
        return parser.task_id == "sample_1"

    write_annotation_images_from_path(annotation_path=zip_path, image_size=(64, 64), label_color_dict=label_color_dict,
                                      output_dir_path=output_image_dir, background_color=(64, 64, 64),
                                      is_target_parser_func=is_target_parser_func)
