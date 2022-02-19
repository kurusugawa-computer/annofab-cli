==========================================
statistics list_annotation_count
==========================================

Description
=================================

各ラベルまたは各属性値のアノテーション数を出力します。



Examples
=================================

基本的な使い方
--------------------------

ラベルごと/属性値ごとのアノテーション数が記載されたファイルを出力します。
アノテーション数は、ダウンロードしたアノテーションZIPから算出します。

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
        "task_id": "task1",
        "status": "complete",
        "phase": "acceptance",
        "phase_stage": 1,
        "input_data_count": 10
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

CSVを出力する場合は、``--type`` でラベルごとのアノテーション数（``--type label``）か、属性値ごとのアノテーション数（``--type attribute``）かを指定してください。
デフォルトでは、ラベルごとのアノテーション数が出力されます。



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
        "task_id": "task1",
        "status": "complete",
        "phase": "acceptance",
        "phase_stage": 1,
        "input_data_count": 10
    }
    ]  


入力データごとのアノテーション数
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


.. code-block::

    $ annofabcli statistics list_annotation_count --project_id prj1 --group_by input_data_id \
    --format pretty_json --output out_by_input_data.json 


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

    task_id,task_status,task_phase,task_phase_stage,input_data_count,annotation_count,car,bike
    task1,break,annotation,1,5,100,20,10...
    task2,complete,acceptance,1,5,80,12,5...


タスクごと属性ごとのアノテーション数
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block::

    $ annofabcli statistics list_annotation_count --project_id prj1 --group_by task_id \
    --format csv --type attribute --output out_by_task_attribute.csv 


.. csv-table:: out_by_input_data_attribute.csv 
    :header-rows: 1

    task_id,status,phase,phase_stage,input_data_count,annotation_count,car,car
    ,,,,,,occlusion,occlusion
    ,,,,,,true,false



入力データごとラベルごとのアノテーション数
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


.. code-block::

    $ annofabcli statistics list_annotation_count --project_id prj1 --group_by input_data_id \
    --format csv --type label --output out_by_input_data_label.csv 


.. csv-table:: out_by_input_data_label.csv 
    :header-rows: 1

    task_id,task_status,task_phase,task_phase_stage,input_data_id,input_data_name,annotation_count,car,bike
    task1,break,annotation,1,input1,input1,100,20,10...
    task2,complete,acceptance,1,input2,input2,80,12,5...


入力データごと属性ごとのアノテーション数
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block::

    $ annofabcli statistics list_annotation_count --project_id prj1 --group_by input_data_id \
    --format csv --type attribute --output out_by_input_data_attribute.csv 


.. csv-table:: out_by_input_data_attribute.csv 
    :header-rows: 1

    task_id,status,phase,phase_stage,input_data_id,input_data_name,annotation_count,car,car
    ,,,,,,,occlusion,occlusion
    ,,,,,,,true,false




Usage Details
=================================

.. argparse::
   :ref: annofabcli.statistics.list_annotation_count.add_parser
   :prog: annofabcli statistics list_annotation_count
   :nosubcommands:
   :nodefaultconst:
