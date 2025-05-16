==========================================
annotation delete
==========================================

Description
=================================
タスク配下のアノテーションを削除します。


Examples
=================================


基本的な使い方
--------------------------

``--task_id`` に削除対象のタスクのtask_idを指定してください。

.. code-block::

    $ annofabcli annotation delete --project_id prj1 --task_id file://task.txt \
    --backup backup


``--backup`` にディレクトリを指定すると、削除対象のタスクのアノテーション情報を、バックアップとしてディレクトリに保存します。
アノテーション情報の復元は、 `annofabcli annotation restore <../annotation/restore.html>`_ コマンドで実現できます。

.. note::

    間違えてアノテーションを削除したときに復元できるようにするため、``--backup`` を指定することを推奨します。



削除するアノテーションを絞り込む場合は、 ``--annotation_query`` を指定してください。
``--annotation_query`` のサンプルは、 `Command line options <../../user_guide/command_line_options.html#annotation-query-aq>`_ を参照してください。

以下のコマンドは、ラベル名（英語）の値が "car" で、属性名(英語)が "occluded" である値が ``false``（"occluded"チェックボックスをOFF）であるアノテーションを削除します。


.. code-block::

    $ annofabcli annotation delete --project_id prj1 --task_id file://task.txt \ 
    --annotation_query '{"label": "car", "attributes":{"occluded": false}}' \
    --backup backup_dir/


.. note::
    
    作業中状態のタスクに含まれるアノテーションは削除できません。
    完了状態のタスクのアノテーションは、デフォルトでは削除できません。 ``--force`` を指定すれば、完了状態のタスクに含まれるアノテーションも削除できます。


CSVに ``annotation_id`` を指定して削除する
----------------------------------------------------

CSVのフォーマットは以下の通りです。

* カンマ区切り
* ヘッダ行あり


.. csv-table::
   :header: 列名,必須,備考

    task_id,Yes,
    input_data_id,Yes,
    annotation_id,Yes,
    

以下はCSVファイルのサンプルです。

.. code-block::
    :caption: annotation.csv

    task_id,input_data_id,annotation_id
    t1,i1,a1
    t1,i1,a2
    t2,i2,a3



.. code-block::

    $ annofabcli annotation delete --project_id p1 --csv annotation.csv



``annotation_id`` をJSON形式で指定して削除する
----------------------------------------------------

以下は、JSONファイルのサンプルです。


.. code-block::
    :caption: annotation.json

    [
        {
            "task_id": "t1",
            "input_data_id":"i1",
            "annotation_id": "a1"
        }
    ]


JSONのキーは、 ``--csv`` に指定するCSVファイルの列に対応します。
``--json`` にJSON形式の文字列、またはJSONファイルのパスを指定できます。

.. code-block::

    $ annofabcli annotation delete --project_id p1 --json file://annotation.json






Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.delete_annotation.add_parser
    :prog: annofabcli annotation delete
    :nosubcommands:
    :nodefaultconst:

See also
=================================
*  `annofabcli annotation restore <../annotation/restore.html>`_
