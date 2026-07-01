==================================================
annotation_zip count_annotation_attribute_filled
==================================================

Description
=================================

値が入力されている属性の個数を、タスクごとまたは入力データごとに集計します。



Examples
=================================

デフォルトではタスク単位で属性の個数を集計します。
出力結果の ``filled`` キーは、値が入力されている属性の個数、 ``empty`` キーは値が入力されていない属性の個数を表します。
属性値が ``null`` または空文字列の場合は ``empty`` 、それ以外の場合は ``filled`` として集計されます。


.. code-block::

    $ annofabcli annotation_zip count_annotation_attribute_filled --project_id p1 \
      --output out_by_task.json --format pretty_json

.. code-block:: json
    :caption: out_by_task.json

    [
        {
            "project_id": "project1",
            "task_id": "task--02",
            "task_status": "break",
            "task_phase": "annotation",
            "task_phase_stage": 1,
            "input_data_count": 1,
            "annotation_attribute_counts": {
                "car": {
                    "occlusion": {
                        "empty": 10,
                        "filled": 20
                    },
                    "type": {
                        "empty": 10,
                        "filled": 20
                    }
                },
                "bike": {
                    "occlusion": {
                        "empty": 10,
                        "filled": 20
                    }
                }
            }
        }
    ]


``--group_by input_data_id`` オプションを指定すると、入力データ単位で属性の個数を集計します。

.. code-block::

    $ annofabcli annotation_zip count_annotation_attribute_filled --project_id p1 \
      --group_by input_data_id --output out_by_input_data.json --format pretty_json


.. code-block:: json
    :caption: out_by_input_data.json

    [
        {
            "project_id": "project1",
            "task_id": "task--02",
            "task_status": "break",
            "task_phase": "annotation",
            "task_phase_stage": 1,
            "input_data_id": "input1",
            "input_data_name": "input1",
            "updated_datetime": "2023-10-01T12:00:00.000+09:00",
            "annotation_attribute_counts": {
                "car": {
                    "occlusion": {
                        "empty": 10,
                        "filled": 20
                    },
                    "type": {
                        "empty": 10,
                        "filled": 20
                    }
                },
                "bike": {
                    "occlusion": {
                        "empty": 10,
                        "filled": 20
                    }
                }
            },
            "frame_no": 1
        }
    ]


``--project_id`` を指定した場合、デフォルトではOn/Off属性（チェックボックス）は集計対象外です。On/Off属性は基本的に常に「入力されている」と判定されるためです。
``--include_flag_attribute`` を指定すると、On/Off属性も集計対象にします。
``--annotation`` のみを指定した場合はアノテーション仕様を参照できないため、On/Off属性も集計対象になります。


出力結果
=================================
    
CSVの属性の列は3行のヘッダーで表します。1行目がラベル名、2行目が属性名、3行目が ``filled`` または ``empty`` です。


タスクごとに集計した結果をCSVで出力
----------------------------------------------------

.. code-block::

    $ annofabcli annotation_zip count_annotation_attribute_filled --project_id prj1 \
     --group_by task_id --format csv --output out_by_task.csv


.. csv-table:: out_by_task.csv
    :header-rows: 3
    :file: count_annotation_attribute_filled/out_by_task.csv


入力データごとに集計した結果をCSVで出力
----------------------------------------------------

.. code-block::

    $ annofabcli annotation_zip count_annotation_attribute_filled --project_id prj1 \
     --group_by input_data_id --format csv --output out_by_input_data.csv


.. csv-table:: out_by_input_data.csv
    :header-rows: 3
    :file: count_annotation_attribute_filled/out_by_input_data.csv



Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_zip.count_annotation_attribute_filled.add_parser
   :prog: annofabcli annotation_zip count_annotation_attribute_filled
   :nosubcommands:
   :nodefaultconst:
