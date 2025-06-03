==========================================
statistics list_annotation_count
==========================================

Description
=================================

ラベルごとまたは属性値ごとにアノテーション数を出力します。

アノテーション数は、ダウンロードしたアノテーションZIPから算出します。
 
 
Examples
=================================

基本的な使い方
--------------------------


.. code-block::

    $ annofabcli statistics list_annotation_count --project_id prj1 --output out.json --format pretty_json


.. code-block:: json
    :caption: out.json

    [
    {
        "annotation_count": 130,
        "annotation_count_by_label": {
            "car": 60,
            "bike": 10,
        },
        "annotation_count_by_attribute": {
            "car": {
                "occlusion": {
                    "false": 10,
                    "true": 20
                },
                "type": {
                    "normal": 10,
                    "bus":20
                }
            },
            "bike": {
                "occlusion": {
                    "false": 10,
                    "true": 20
                }
            }
        },
        "project_id": "project1",
        "task_id": "task1",
        "task_status": "complete",
        "task_phase": "acceptance",
        "task_phase_stage": 1,
        "input_data_count": 10,
    }
    ]  


* ``annotation_count_by_label`` : ラベルごとのアノテーション数（ ``{label_name: annotation_count}``）
* ``annotation_count_by_attribute`` : 属性値ごとのアノテーション数（ ``{label_name: {attribute_name: {attribute_value: annotation_count}}}``）


集計対象の属性の種類は以下の通りです。

* ドロップダウン
* ラジオボタン
* チェックボックス


デフォルトではタスク単位でアノテーション数を集計します。入力データ単位に集計する場合は、 ``--group_by input_data_id`` を指定してください。

``--annotation`` にアノテーションzipまたはzipを展開したディレクトリを指定できます。

.. code-block::

    $ annofabcli statistics list_annotation_count --project_id prj1 --output_dir out_dir/ \
    --annotation annotation.zip


CSV出力
--------------------------

CSVを出力する場合は、``--type`` で列名をラベル( ``label`` )にするか属性値( ``attribute`` )にするかを指定してください。
デフォルトは ``label`` です。



出力結果
=================================


JSON出力
----------------------------------------------

タスクごとのアノテーション数
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block::

    $ annofabcli statistics list_annotation_count --project_id prj1 --group_by task_id \
    --format pretty_json --output out_by_task.json 


.. code-block:: json
    :caption: out_by_task.json

    [
    {
        "annotation_count": 130,
        "annotation_count_by_label": {
            "car": 60,
            "bike": 10,
        },
        "annotation_count_by_attribute": {
            "car": {
                "occlusion": {
                    "false": 10,
                    "true": 20
                },
                "type": {
                    "normal": 10,
                    "bus":20
                }
            },
            "bike": {
                "occlusion": {
                    "false": 10,
                    "true": 20
                }
            }
        },
        "project_id": "project1",
        "task_id": "task1",
        "task_status": "complete",
        "task_phase": "acceptance",
        "task_phase_stage": 1,
        "input_data_count": 10,
        "frame_no": 1        
    }
    ]  


入力データごとのアノテーション数
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


.. code-block::

    $ annofabcli statistics list_annotation_count --project_id prj1 --group_by input_data_id \
    --format pretty_json --output out_by_input_data.json 


.. code-block:: json
    :caption: out_by_input_data.json

    [
    {
        "annotation_count": 130,
        "annotation_count_by_label": {
            "car": 60,
            "bike": 10,
        },
        "annotation_count_by_attribute": {
            "car": {
                "occlusion": {
                    "false": 10,
                    "true": 20
                },
                "type": {
                    "normal": 10,
                    "bus":20
                }
            },
            "bike": {
                "occlusion": {
                    "false": 10,
                    "true": 20
                }
            }
        },
        "project_id": "project1",
        "task_id": "task1",
        "status": "complete",
        "phase": "acceptance",
        "phase_stage": 1,
        "input_data_id": "input1",
        "input_data_name": "input1"
    }
    ]  


CSV出力
----------------------------------------------

タスクごとラベルごとのアノテーション数
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


.. code-block::

    $ annofabcli statistics list_annotation_count --project_id prj1 --group_by task_id \
    --format csv --type label --output out_by_task_label.csv 


.. csv-table:: out_by_task_label.csv 
    :header-rows: 1
    :file: list_annotation_count/out_by_task_label.csv


タスクごと属性ごとのアノテーション数
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block::

    $ annofabcli statistics list_annotation_count --project_id prj1 --group_by task_id \
    --format csv --type attribute --output out_by_task_attribute.csv 


.. csv-table:: out_by_task_attribute.csv 
    :header-rows: 1
    :file: list_annotation_count/out_by_task_attribute.csv


入力データごとラベルごとのアノテーション数
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


.. code-block::

    $ annofabcli statistics list_annotation_count --project_id prj1 --group_by input_data_id \
    --format csv --type label --output out_by_input_data_label.csv 


.. csv-table:: out_by_input_data_label.csv 
    :header-rows: 1
    :file: list_annotation_count/out_by_input_data_label.csv


入力データごと属性ごとのアノテーション数
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block::

    $ annofabcli statistics list_annotation_count --project_id prj1 --group_by input_data_id \
    --format csv --type attribute --output out_by_input_data_attribute.csv 


.. csv-table:: out_by_input_data_attribute.csv
    :header-rows: 1
    :file: list_annotation_count/out_by_input_data_attribute.csv





Usage Details
=================================

.. argparse::
   :ref: annofabcli.statistics.list_annotation_count.add_parser
   :prog: annofabcli statistics list_annotation_count
   :nosubcommands:
   :nodefaultconst:
