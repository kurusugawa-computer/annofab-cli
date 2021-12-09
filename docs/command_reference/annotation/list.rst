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

以下のコマンドは、すべてのアノテーションの一覧を出力します。 ただし10,000件までしか出力できません。

.. code-block::

    $ annofabcli annotation list --project_id prj1 


.. warning::
    
    WebAPIの都合上、集計対象のアノテーションは10,000個までしか検索できません。


``--annotation_query`` で、アノテーションを検索するする条件を指定することができます。。フォーマットは https://annofab.com/docs/api/#section/AnnotationQuery とほとんど同じです。
さらに追加で ``label_name_en`` , ``additional_data_definition_name_en`` , ``choice_name_en`` キーも指定できます。``label_id`` または ``label_name_en`` のいずれかは必ず指定してください。

``--annotation_query`` のサンプルは、`Command line options <../../user_guide/command_line_options.html#annotation-query-aq>`_ を参照してください。


以下のコマンドは、ラベル名（英語)が"car"であるアノテーションの一覧を出力します。

.. code-block::

    $ annofabcli annotation list --project_id prj1 \
    --annotation_query '{"label_name_en": "car"}' 



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
                "annotation_id": "annotation1",
                "account_id": "account1",
                "label_id": "label1",
                "data_holding_type": "inner",
                "data": {
                    "left_top": {
                    "x": 10,
                    "y": 7
                    },
                    "right_bottom": {
                    "x": 36,
                    "y": 36
                    },
                    "_type": "BoundingBox"
                },
                "etag": null,
                "url": null,
                "additional_data_list": [],
                "created_datetime": "2019-08-22T12:04:19.256+09:00",
                "updated_datetime": "2019-08-22T14:12:45.555+09:00",
                "label_name_en": "car",
                "user_id": "user1",
                "username": "user1"
            },
            "updated_datetime": "2019-08-22T14:14:11.084+09:00"
        },

        ...
    ]


CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli annotation list --format csv --output out.csv

`out.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/master/docs/command_reference/annotation/list/out.csv>`_

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.list_annotation.add_parser
    :prog: annofabcli annotation list
    :nosubcommands:
    :nodefaultconst:
