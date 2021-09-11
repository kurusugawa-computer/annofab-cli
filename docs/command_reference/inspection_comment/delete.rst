==========================================
inspection_comment delete
==========================================

Description
=================================
検査コメントを削除します。



Examples
=================================

基本的な使い方
--------------------------

``--json`` に削除する検査コメントのinspection_idをJSON形式で指定してください。

.. code-block::
    :caption: inspection_id.json

    {
        "task1":{
            "input_data1": ["inspection1","inspection2"],
            "input_data2":[{},{}, ...]
        },
        "task2": {
            "input_data3":[{},{}, ...]
        }
    }



.. code-block::

    $ annofabcli inspection_comment delete --project_id prj1 --json file://inspection_id.json


並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $  annofabcli inspection_comment delete --project_id prj1 --json file://inspection_id.json \
    --parallelism 4 --yes

Usage Details
=================================

.. argparse::
   :ref: annofabcli.inspection_comment.delete_inspection_comments.add_parser
   :prog: annofabcli inspection_comment delete
   :nosubcommands:
