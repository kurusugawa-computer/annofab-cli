==========================================
statistics list_annotation_duration
==========================================

Description
=================================

ラベルごとまたは属性値ごとに区間アノテーションの長さ（秒）を出力します。
区間アノテーションは動画プロジェクト用のアノテーションです。

区間アノテーションの長さは、ダウンロードしたアノテーションZIPから算出します。


Examples
=================================


JSON出力
--------------------------


.. code-block::

    $ annofabcli statistics list_annotation_duration --project_id prj1 \
     --output out.json --format pretty_json


.. code-block:: json
    :caption: out.json

    [
    {
        "project_id": "project1",
        "task_id": "sample_task_00",
        "task_status": "not_started",
        "task_phase": "annotation",
        "task_phase_stage": 1,
        "input_data_id": "sample_video_00.mp4",
        "input_data_name": "sample_video_00.mp4",
        "video_duration_second": 30,
        "annotation_duration_second": 21.333,
        "annotation_duration_second_by_label": {
            "traffic_light": 21.333
        },
        "annotation_duration_second_by_attribute": {
            "traffic_light": {
                "color": {
                    "red": 13.2,
                    "green": 8.133,
                }
            }
        }
    }
    ]



* ``annotation_duration_second`` : 区間アノテーションの合計の長さ（秒）
* ``annotation_duration_second_by_label`` : ラベルごとの区間アノテーションの長さ（秒）（ ``{label_name: annotation_duration}``）
* ``annotation_duration_second_by_attribute`` : 属性値ごとの区間アノテーションの長さ（秒）（ ``{label_name: {attribute_name: {attribute_value: annotation_duration}}}``）


``annotation_duration_second_by_attribute`` に格納される属性の種類は以下の通りです。

* ドロップダウン
* ラジオボタン
* チェックボックス

※ ``--project_id`` を指定しない場合は、上記以外の属性の種類（たとえばトラッキングID）も集計されます。


CSV出力
--------------------------

CSVを出力する場合は、``--type`` で列名をラベル( ``label`` )にするか属性値( ``attribute`` )にするかを指定してください。
デフォルトは ``label`` です。


.. code-block::

    $ annofabcli statistics list_annotation_count --project_id prj1 \
    --format csv --type label --output out_by_label.csv 

.. csv-table:: out_by_label.csv 
    :header-rows: 1
    :file: list_annotation_duration/out_by_label.csv 


.. code-block::

    $ annofabcli statistics list_annotation_count --project_id prj1 \
    --format csv --type attribute --output out_by_attribute.csv 

.. csv-table:: out_by_attribute.csv 
    :header-rows: 3
    :file: list_annotation_duration/out_by_attribute.csv



Usage Details
=================================

.. argparse::
   :ref: annofabcli.statistics.list_annotation_duration.add_parser
   :prog: annofabcli statistics list_annotation_duration
   :nosubcommands:
   :nodefaultconst:
