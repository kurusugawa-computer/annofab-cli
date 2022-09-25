==========================================
annotation import
==========================================

Description
=================================
アノテーションをプロジェクトにインポートします。
アノテーシンzipまたはzipを展開したディレクトリをインポートできます。
作業中または完了状態のタスクに対してはインポートできません。



Examples
=================================


インポート対象のアノテーションのフォーマット
----------------------------------------------------

インポート対象のアノテーションのフォーマットは、アノテーションzipまたはzipを展開したディレクトリと同じディレクトリ構成です。


.. code-block::
    :caption: annotation.zip

    ルートディレクトリ/
    ├── {task_id}/
    │   ├── {input_data_id}.json
    │   ├── {input_data_id}/
    │          ├── {annotation_id}............ 塗りつぶしPNG画像


``{input_data_id}.json`` のサンプルをは以下の通りです。各キーの詳細は https://annofab.com/docs/api/#section/Simple-Annotation-ZIP を参照してください。

.. code-block::
    :caption: {input_data_id}.json

    {
        "details": [
            {
                "label": "car",
                "data": {
                    "left_top": {
                        "x": 878,
                        "y": 566
                    },
                    "right_bottom": {
                        "x": 1065,
                        "y": 701
                    },
                    "_type": "BoundingBox"
                },
                "attributes": {}
            },
            {
                "label": "road",
                "data": {
                    "data_uri": "b803193f-827f-4755-8228-e2c67d0786d9",
                    "_type": "SegmentationV2"
                },
                "attributes": {}
            },
            {
                "label": "weather",
                "data": {
                    "_type": "Classification"
                },
                "attributes": {
                    "sunny": true
                }
            }
        ]
    }




以下のように ``annotation_id`` が指定されている場合、``annotation_id`` もインポートされます。


.. code-block::
    :caption: {input_data_id}.json

    {
        "details": [
            {
                "label": "car",
                "annotation_id": "12345678-abcd-1234-abcd-1234abcd5678",
                "data": {
                    "left_top": {
                        "x": 878,
                        "y": 566
                    },
                    "right_bottom": {
                        "x": 1065,
                        "y": 701
                    },
                    "_type": "BoundingBox"
                },
                "attributes": {}
            },
            ...
        ]
    }


基本的な使い方
----------------------------------------------------

``--annotation`` に、アノテーションzipまたはzipを展開したディレクトリのパスを指定してください。

.. code-block::

    $ annofabcli annotation import --project_id prj1 --annotation annotation.zip 


インポート対象のタスクを指定する場合は、``--task_id`` にインポート対象のタスクのtask_idを指定してください。

.. code-block::

    $ annofabcli annotation import --project_id prj1 --annotation annotation.zip \
    --task_id file://task_id.txt


デフォルトでは、すでにアノテーションが存在する場合はスキップします。
既存のアノテーションを残してインポートする場合は、 ``--merge`` を指定してください。
インポート対象のアノテーションのannotation_idが、既存のアノテーションのannotation_idに一致すればアノテーションを上書きします。一致しなければアノテーションを追加します。


.. code-block::

    $ annofabcli annotation import --project_id prj1 --annotation annotation.zip \
    --merge


既存のアノテーションを削除してからインポートする場合は、 ``--overwrite`` を指定してください。

.. code-block::

    $ annofabcli annotation import --project_id prj1 --annotation annotation.zip \
    --overwrite



デフォルトでは「担当者が自分自身でない AND 担当者が割れ当てられたことがある」タスクは、アノテーションのインポートをスキップします。
``--force`` を指定すると、担当者を一時的に自分自身に変更して、アノテーションをインポートすることができます。

.. code-block::

    $ annofabcli annotation import --project_id prj1 --annotation annotation.zip \
    --force

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.import_annotation.add_parser
    :prog: annofabcli annotation import
    :nosubcommands:
    :nodefaultconst:



