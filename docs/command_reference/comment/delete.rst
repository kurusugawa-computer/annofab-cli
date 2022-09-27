==========================================
comment delete
==========================================

Description
=================================
コメントを削除します。

.. code-block::
    
    他人の付けたコメントや他のフェーズで付与されたコメントも削除できてしまいます。


Examples
=================================

基本的な使い方
--------------------------

``--json`` に削除するコメントのcomment_idをJSON形式で指定してください。

.. code-block::
    :caption: inspection_id.json

    {
        "task1":{
            "input_data1": ["comment_id1","comment_id2"],
            "input_data2":[...]
        },
        "task2": {
            "input_data3":[...]
        }
    }



.. code-block::

    $ annofabcli comment delete --project_id prj1 --json file://inspection_id.json



.. note::
    
    過去のフェーズ・ステージで付与されたコメントは削除できません。


並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $  annofabcli comment delete --project_id prj1 --json file://inspection_id.json \
    --parallelism 4 --yes

Usage Details
=================================

.. argparse::
   :ref: annofabcli.comment.delete_comment.add_parser
   :prog: annofabcli comment delete
   :nosubcommands:
   :nodefaultconst:

