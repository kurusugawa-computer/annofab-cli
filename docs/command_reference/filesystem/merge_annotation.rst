=================================
filesystem merge_annotation
=================================

Description
=================================
2つのアノテーションzip、またはそれを展開したディレクトリに存在するアノテーション情報をマージします。


Examples
=================================


基本的な使い方
--------------------------

``--annotation`` には、Annofabからダウンロードしたアノテーションzip、またはアノテーションzipを展開したディレクトリを2つ指定してください。
アノテーションzipは、`annofabcli annotation download <../annotation/download.html>`_ コマンドでダウンロードできます。


.. code-block::

    $ annofabcli filesystem merge_annotation  \
    --annotation annotation-A.zip annotation-B.zip \
    --output_dir out/


アノテーションJSONは以下の通りマージされます。
``annotation-A.zip`` と ``annotation-B.zip`` の両方に同じannotation_idが存在する場合は、``annotation-B.zip`` の情報を優先します。


.. code-block::
    :caption: annotation-A/task1/input1.json

    {
        // ...
        "details": [
            {
                "label": "car",
                "annotation_id": "anno1",
                // ...
            },
            {
                "label": "car",
                "annotation_id": "anno2",
                // ...
            }
        ]
    }



.. code-block::
    :caption: annotation-B/task1/input1.json

    {
        // ...
        "details": [
            {
                "label": "car",
                "annotation_id": "anno2",
                // ...
            },
            {
                "label": "car",
                "annotation_id": "anno3",
                // ...
            }
        ]
    }


.. code-block::
    :caption: out/task1/input1.json

    {
        // ...
        "details": [
            {
                "label": "car",
                "annotation_id": "anno1",
                // ...
            },
            {
                "label": "car",
                "annotation_id": "anno2",
                // annotaion-B 配下の情報
                // ...
            },
            {
                "label": "car",
                "annotation_id": "anno3",
                // ...
            }
        ]
    }



タスクの絞り込み
--------------------------
マージ対象のタスクを指定する場合は、``--task_id`` に描画対象タスクのtask_idを指定してください。


.. code-block::

    $ annofabcli filesystem merge_annotation  \
    --annotation annotation-A.zip annotation-B.zip \
    --output_dir out/
    --task_id task1 task2

Usage Details
=================================

.. argparse::
   :ref: annofabcli.filesystem.merge_annotation.add_parser
   :prog: annofabcli filesystem merge_annotation
   :nosubcommands:
   :nodefaultconst:
    

See also
=================================

* `アノテーションzipの構造 <https://annofab.com/docs/api/#section/Simple-Annotation-ZIP>`_

