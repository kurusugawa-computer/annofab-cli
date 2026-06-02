=================================
annotation_zip merge
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

    $ annofabcli annotation_zip merge \
        --annotation annotation-A.zip annotation-B.zip \
        --output_dir out/


マージ仕様
--------------------------

このコマンドは、アノテーションZIP内のアノテーションJSONを、タスクと入力データごとのJSONファイル単位でマージします。
たとえば ``task1/input1.json`` は、同じパスの ``task1/input1.json`` とマージされます。

同じJSONファイルが両方のアノテーションZIPに存在する場合は、アノテーションJSONの ``details`` 配下にある各アノテーション情報を ``annotation_id`` 単位でマージします。
同じ ``annotation_id`` が存在する場合は、2個目に指定したアノテーションZIPの情報を優先します。
片方のアノテーションZIPにしか存在しないJSONファイルや ``annotation_id`` は、そのまま出力されます。

``Segmentation`` または ``SegmentationV2`` のアノテーションに紐づく外部ファイルも、出力先にコピーされます。


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
                // annotation-B 配下の情報
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
マージ対象のタスクを指定する場合は、``--task_id`` にマージ対象タスクのtask_idを指定してください。


.. code-block::

    $ annofabcli annotation_zip merge \
        --annotation annotation-A.zip annotation-B.zip \
        --output_dir out/ \
        --task_id task1 task2

Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_zip.merge.add_parser
   :prog: annofabcli annotation_zip merge
   :nosubcommands:
   :nodefaultconst:
    
