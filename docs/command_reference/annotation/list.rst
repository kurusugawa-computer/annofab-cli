==========================================
annotation list
==========================================

Description
=================================
アノテーション一覧を出力します。






Examples
=================================


基本的な使い方
--------------------------

以下のコマンドは、すべてのアノテーションの一覧を出力します。 

.. code-block::

    $ annofabcli annotation list --project_id prj1 


.. warning::
    
    WebAPIの都合上、1回のWebAPI( ``getAnnotationList`` API)のアクセスで取得できるアノテーションは最大10,000件です。
    したがって、 ``--task_id`` または ``--input_data_id`` を指定しない場合は、10,000件までしかアノテーション情報は出力されません。
    ``--task_id`` または ``--input_data_id`` を指定した場合は、task_idまたはinput_data_idごとにWebAPIにアクセスするため、10,000件以上のアノテーション情報が出力されることがあります。
    

``--annotation_query`` で、アノテーションを検索するする条件を指定することができます。
``--annotation_query`` のサンプルは、`Command line options <../../user_guide/command_line_options.html#annotation-query-aq>`_ を参照してください。


以下のコマンドは、ラベル名（英語)が"car"であるアノテーションの一覧を出力します。

.. code-block::

    $ annofabcli annotation list --project_id prj1 \
    --annotation_query '{"label": "car"}' 



``--task_id`` で出力対象のタスクを絞り込むこともできます。

.. code-block::

    $ annofabcli annotation list --project_id prj1 \
    --task_id file://task.txt




出力結果
=================================


JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli annotation list --format pretty_json --output out.json



.. code-block::
    :caption: out.json

    [
    {
        "project_id": "prj1",
        "task_id": "task1",
        "input_data_id": "input1",
        "detail": {
        "annotation_id": "anno1",
        "account_id": "account1",
        "label_id": "label1",
        "body": {
            "data": {
            "points": [
                {
                "x": 663,
                "y": 376
                },
                {
                "x": 664,
                "y": 432
                },
            ],
            "_type": "Points"
            },
            "_type": "Inner"
        },
        "additional_data_list": [],
        "created_datetime": "2024-07-11T15:27:29.436+09:00",
        "updated_datetime": "2024-07-11T15:27:29.436+09:00",
        "label_name_en": "human",
        "user_id": "alice",
        "username": "ALICE"
        },
        "updated_datetime": "2024-07-12T11:39:57.478+09:00"
    },
    ...
    ]



CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli annotation list --format csv --output out.csv



.. csv-table:: out.csv 
    :header-rows: 1
    :file: list/out.csv



Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.list_annotation.add_parser
    :prog: annofabcli annotation list
    :nosubcommands:
    :nodefaultconst:
